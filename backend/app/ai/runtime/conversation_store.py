"""Conversation Session管理(FORGE-PRODUCT-VISION-002、2026-08-11)。

`confirmation_store.py`と全く同じ設計方針(プロセス内メモリのみ・TTL・
最大ターン数)を、複数ターンの会話セッションへ踏襲する。DBは追加しない
(共通指示書の既存方針を継続)。

**永続化についての既知の制限(confirmation_store.pyと同じ)**: プロセス
内メモリのみで完結する。サーバー再起動やマルチプロセス/マルチワーカー
構成では保持されない。将来複数ワーカーで運用する場合、Redis等の外部
ストアへの置き換えが必要になる(TECH_DEBT.md TD41参照)。
"""

from __future__ import annotations

import time
import uuid
from threading import Lock

from app.ai.runtime.conversation_types import (
    ConversationSession,
    ConversationTurn,
    CorrectionRecord,
)

# **FORGE-CONVERSATION-READY-001(2026-08-12)で意味が変わった定数**。
#
# 旧: 「ターン数がこれに達したら**強制的にBUILDへ倒す**」上限。
# 新: 「ターン数がこれに達したら**質問戦略を変える**」閾値。
#
# 変更理由(指示書1章): 「質問しすぎない」と「分からなくても作る」は
# 別である。旧実装では、解を左右する重要な未知が残っていても、3ターン
# 経過しただけでBUILDへ倒していた——これは製品の核心である「どこまで
# 聞いたら作るのか」の判断を、単なるカウンタへ委ねていたことになる。
#
# この閾値に達したときに変わるのは、以下の**質問の仕方**だけである
# (`conversation_policy._askable_impacts()`・
# `conversation_engine._NARROWED_QUESTION_GUIDANCE`参照):
#   * HIGH(構造は変わるが、答えなくても作れる)は質問をやめ、
#     理由付きのSafe Assumptionへ回す。
#   * 残る質問は自由回答ではなく短い二択にする。
# 一方、BLOCKING(これが分からないと何を作るか決まらない)は、この
# 閾値に達しても質問し続ける。BUILDの可否はあくまで
# `ConversationReadiness`が決める(指示書16章の完了条件)。
MAX_CONVERSATION_TURNS = 3

_TTL_SECONDS = 60 * 30  # 30分。confirmation_store.pyと同じ。


class ConversationNotFoundError(Exception):
    """`session_id`に対応するConversationSessionが存在しない
    (未発行・期限切れのいずれか)。"""


class ConversationStore:
    """プロセス内メモリのみで完結する、会話セッションの追跡ストア。"""

    def __init__(self) -> None:
        self._lock = Lock()
        self._sessions: dict[str, ConversationSession] = {}
        self._expiry: dict[str, float] = {}

    def create(self) -> ConversationSession:
        session = ConversationSession(session_id=str(uuid.uuid4()), created_at=time.time())
        with self._lock:
            self._sessions[session.session_id] = session
            self._expiry[session.session_id] = session.created_at
        return session

    def get(self, session_id: str) -> ConversationSession:
        with self._lock:
            session = self._sessions.get(session_id)
            created_at = self._expiry.get(session_id)
        if session is None or created_at is None:
            raise ConversationNotFoundError(session_id)
        if (time.time() - created_at) > _TTL_SECONDS:
            self.discard(session_id)
            raise ConversationNotFoundError(session_id)
        return session

    def save(self, session: ConversationSession) -> None:
        with self._lock:
            if session.session_id not in self._sessions:
                raise ConversationNotFoundError(session.session_id)
            self._sessions[session.session_id] = session

    def discard(self, session_id: str) -> None:
        with self._lock:
            self._sessions.pop(session_id, None)
            self._expiry.pop(session_id, None)

    def add_turn(self, session_id: str, turn: ConversationTurn) -> ConversationSession:
        session = self.get(session_id)
        updated = session.with_turn(turn)
        self.save(updated)
        return updated

    def mark_question_asked(self, session_id: str, key: str) -> ConversationSession:
        """FORGE-CONVERSATION-READY-001(2026-08-12)新設。今聞いた未知の
        keyを記録し、同じUnknownを繰り返し質問しないようにする
        (指示書5章)。`key`が空・既存の場合は何もしない。"""
        session = self.get(session_id)
        updated = session.with_asked_key(key)
        if updated is not session:
            self.save(updated)
        return updated

    def record_hypothesis_event(
        self, session_id: str, *, event: str | None, hypothesis: object | None,
        correction_target: str | None,
        experience_refs: tuple[int, ...] = (),
        experience_store: object | None = None,
    ) -> ConversationSession:
        """Stateful User Correctionの状態遷移を永続化する
        (FORGE-USER-GUIDED-SELF-EXTENSION-006 §13、2026-08-13)。

        **これが無いと、Engineがどれだけ正しく訂正を解釈しても、
        次のターンには忘れている**。Engineは純粋関数のままにしておきたい
        ので(`conversation_policy.py`と同じ方針)、状態を書くのは
        Store側のこの1メソッドに集約する。

        `event`が`None`(Capability層が何もしなかったターン)なら、
        既存の仮説状態には**一切触れない**。従来どおりの会話が仮説を
        壊さないようにするため。

        ---

        ## Experienceの評価もここで書く(FORGE-ROADMAP R0、2026-08-17)

        利用者が前の応答をどう扱ったかは、**このターンの出来事として
        しか現れない**。「それでいい」(accept)・「そこは違う」
        (clarify)・「そもそも違う」(rewind)は、いずれも直前のAI応答
        への評価である。

        書く場所をこのメソッドにしたのは、上と同じ理由である——
        「このターンで何が起きたかを状態へ書き下す」のはここ1箇所で
        あり、別の場所へ足すと、書き忘れる経路が増える。Forgeは
        `ExperienceStore`を作って本番から一度も呼ばないまま放置した
        (Product Direction §7)。同じ形にしないための配置である。

        `experience_store`を引数で受け取るのは、**Routerが記録した
        Storeとここで書き足すStoreを必ず一致させる**ためである。
        それぞれが既定Storeを自分で解決すると、テストが差し替えた
        ときに静かにずれる。
        """
        session = self.get(session_id)

        # 評価の書き足しは、仮説状態の遷移とは**独立に**行う。
        # `event`が`None`のターン(=仮説を触らない普通の会話)でも、
        # 前ターンの応答を評価する術が無いだけであって、今ターンの
        # 呼び出しを次ターンへ引き継ぐ必要はある。
        session = self._carry_experience(session, event, experience_refs, experience_store)
        if event is None:
            return session

        if event == "rewind":
            updated = session.rewound()
        elif event == "accept":
            updated = session.with_acceptance()
        elif event == "clarify":
            # 仮説は保持したまま、訂正があったことだけ記録する(§14)。
            updated = session.with_correction(
                CorrectionRecord(target=correction_target or "unclear"), None
            )
        elif event == "present" and hypothesis is not None:
            previous = session.current_hypothesis
            if previous is None:
                updated = session.with_hypothesis(hypothesis)
            else:
                updated = session.with_correction(
                    CorrectionRecord(
                        target=correction_target or "unknown",
                        from_missing=tuple(c.id for c in getattr(previous, "missing", ())),
                        to_missing=tuple(c.id for c in getattr(hypothesis, "missing", ())),
                    ),
                    hypothesis,
                ).with_hypothesis(hypothesis)
        else:
            return session

        self.save(updated)
        return updated

    def _carry_experience(
        self,
        session: ConversationSession,
        event: str | None,
        experience_refs: tuple[int, ...],
        experience_store: object | None,
    ) -> ConversationSession:
        """前ターンの応答へ評価を付け、今ターンの呼び出しを次へ渡す(R0)。"""
        from app.ai.gateway.learning_foundation import (  # noqa: PLC0415 — Conversation層→Gateway層の一方向依存に留める
            AcceptanceSignal,
            acceptance_from_turn_event,
        )

        signal = acceptance_from_turn_event(event) if event is not None else AcceptanceSignal.UNKNOWN
        if (
            signal is AcceptanceSignal.UNKNOWN
            and event == "present"
            and session.current_hypothesis is not None
        ):
            # 「提示」が2回目以降なら、それは**前の仮説が外れていた**
            # ということである(`record_hypothesis_event`が下で
            # `with_correction`を呼ぶのと同じ判定)。初回の提示は
            # 評価ではないので、ここで初めて`CORRECTED`になる。
            signal = AcceptanceSignal.CORRECTED

        if (
            experience_store is not None
            and session.pending_experience_refs
            and signal is not AcceptanceSignal.UNKNOWN
        ):
            experience_store.note_acceptance(session.pending_experience_refs, signal)

        if experience_refs == session.pending_experience_refs:
            return session
        updated = session.with_pending_experience_refs(experience_refs)
        self.save(updated)
        return updated

    def size(self) -> int:
        with self._lock:
            return len(self._sessions)


# アプリ全体で1つのStoreを共有する(confirmation_store.pyと同じ、
# モジュールレベルSingleton)。
default_conversation_store = ConversationStore()
