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

from app.ai.runtime.conversation_types import ConversationSession, ConversationTurn

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

    def size(self) -> int:
        with self._lock:
            return len(self._sessions)


# アプリ全体で1つのStoreを共有する(confirmation_store.pyと同じ、
# モジュールレベルSingleton)。
default_conversation_store = ConversationStore()
