"""確認要求(needs_confirmation)の状態管理
(FORGE_v0.2_修正指示.md P1 7章、Final Gate P0.1・P0.7で改訂)。

**設計上の制約(正直な申告)**: forge_ai側のCognitive Pipeline
(`run_cognitive_pipeline()`)は、現時点で「途中の段階から再開する」
機能を持たない。`docs/spec/FORGE_M007_IMPLEMENTATION_BLUEPRINT.md`は
これを明示的にNon-Goalとしている(`resumable_from`は契約の形のみを
定義し、実際の再開処理はUI側同様に将来のTaskとしている)。

そのため、このStoreが実際に提供する「再開」は、forge_ai内部段階からの
真の再開では**ない**。`request_id`を介して、(1)元の自然言語入力、
(2)使用したEngine/Provider、(3)これまでの確認ラウンド数、
(4)前回到達時点のdiagnostics(ambiguity_report・domain_classification・
decision_trace)を追跡し、`POST /api/v1/ai/generate/confirm`が呼ばれた
際に、**ユーザーの回答を元の入力とは別の引数としてCognitive Pipelineへ
渡し、最初から再実行する**、という現実的な代替設計である。

**修正した重大バグ(Final Gate P0.1)**: 以前は`consume_and_advance()`が
`f"{original}\\n(補足回答: {answer})"`という、Forge内部の管理用ラベル
(「補足回答」)を自然言語へ直接埋め込んだ1本の文字列を返し、呼び出し側
(`app/routers/ai.py`)がこれをそのまま`PromptPipeline.run()`の
`natural_language`引数へ渡していた。この結果、「回答」という語が
`forge_ai/core/lexicon.py`のSurvey Domain概念("answer")と一致し、
本来無関係なはずのSurvey Domainが競合候補として浮上する、という実害を
実際に再現・確認した(`forge_ai.core.pipeline.run_cognitive_pipeline()`
のdocstring参照)。

**修正内容**: `consume_and_advance()`は文字列を結合せず、
`(record, original_natural_language, answer)`という3値タプルを返す
ように変更した。結合(ラベル無し)は`forge_ai.core.pipeline.
_combine_with_answer()`という、Forge内部で唯一の場所でのみ行う。

**永続化についての既知の制限**: プロセス内メモリのみで完結する
(共通指示書のDatabase追加禁止・早すぎるマイクロサービス化禁止の方針を
継続)。サーバー再起動やマルチプロセス/マルチワーカー構成では保持
されない。将来複数ワーカーで運用する場合、Redis等の外部ストアへの
置き換えが必要になる(TECH_DEBTとして記録する)。
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from threading import Lock
from typing import Any

# P0 2章「確認回数制御」対応: 同一件について確認を無限に繰り返さない。
MAX_CONFIRMATION_ROUNDS = 3

# 期限切れのPendingConfirmationは再利用不可とする(ユーザーが確認画面を
# 開いたまま長時間放置した場合、古いforge_aiの状態を前提に再実行しない
# ための安全策)。
_TTL_SECONDS = 60 * 30  # 30分


class ConfirmationRoundExceededError(Exception):
    """`MAX_CONFIRMATION_ROUNDS`を超えて確認を繰り返そうとした場合。"""

    def __init__(self, round_count: int) -> None:
        super().__init__(f"確認の往復回数が上限({MAX_CONFIRMATION_ROUNDS}回)に達しました(現在{round_count}回目)。")
        self.round_count = round_count


class ConfirmationNotFoundError(Exception):
    """`request_id`に対応するPendingConfirmationが存在しない
    (未発行・期限切れ・既に消費済みのいずれか)。"""


@dataclass(frozen=True)
class PendingConfirmation:
    request_id: str
    original_natural_language: str
    engine: str
    provider: str | None
    reached_stage: str
    reason: str
    round_count: int
    created_at: float = field(default_factory=time.time)
    # FORGE v0.2 Final Gate P0.7対応: 前回到達時点の診断情報を保持する。
    # 「再確認時に前回状態を追跡できる」ことの最低要件として、直前の
    # Ambiguity Report・Domain Classification・Decision Traceを、
    # dictへ変換済みの形(`prompt_pipeline.py`の`_ambiguity_report_to_
    # dict()`等と同じ形式)でそのまま保持する。
    previous_ambiguity_report: dict[str, Any] | None = None
    previous_domain_classification: dict[str, Any] | None = None
    previous_decision_trace: tuple[dict[str, Any], ...] = ()
    # このセッション内で今までにユーザーが送った回答の履歴
    # (再確認が複数回続いた場合、過去の回答も追跡できるようにする)。
    previous_answers: tuple[str, ...] = ()
    agent_mode: str = "off"
    """FORGE-020B。確認往復で opt-in Agent 設定を失わない。"""

    def is_expired(self, *, now: float | None = None) -> bool:
        current = now if now is not None else time.time()
        return (current - self.created_at) > _TTL_SECONDS


class ConfirmationStore:
    """プロセス内メモリのみで完結する、確認要求の追跡ストア。"""

    def __init__(self) -> None:
        self._lock = Lock()
        self._pending: dict[str, PendingConfirmation] = {}

    def create(
        self,
        *,
        original_natural_language: str,
        engine: str,
        provider: str | None,
        reached_stage: str,
        reason: str,
        round_count: int = 1,
        ambiguity_report: dict[str, Any] | None = None,
        domain_classification: dict[str, Any] | None = None,
        decision_trace: tuple[dict[str, Any], ...] = (),
        previous_answers: tuple[str, ...] = (),
        agent_mode: str = "off",
    ) -> PendingConfirmation:
        record = PendingConfirmation(
            request_id=str(uuid.uuid4()),
            original_natural_language=original_natural_language,
            engine=engine,
            provider=provider,
            reached_stage=reached_stage,
            reason=reason,
            round_count=round_count,
            previous_ambiguity_report=ambiguity_report,
            previous_domain_classification=domain_classification,
            previous_decision_trace=decision_trace,
            previous_answers=previous_answers,
            agent_mode=agent_mode,
        )
        with self._lock:
            self._pending[record.request_id] = record
        return record

    def get(self, request_id: str) -> PendingConfirmation:
        """存在しない、または期限切れの場合は`ConfirmationNotFoundError`を送出する。"""
        with self._lock:
            record = self._pending.get(request_id)
        if record is None:
            raise ConfirmationNotFoundError(request_id)
        if record.is_expired():
            self.discard(request_id)
            raise ConfirmationNotFoundError(request_id)
        return record

    def discard(self, request_id: str) -> None:
        with self._lock:
            self._pending.pop(request_id, None)

    def consume_and_advance(self, request_id: str, *, answer: str) -> tuple[PendingConfirmation, str, str]:
        """回答を受け取り、(1)元のrequest_idを無効化し、(2)元の自然言語
        入力と(3)回答を、**結合せず別々の値として**返す
        (`(record, original_natural_language, answer)`)。

        FORGE v0.2 Final Gate P0.1対応: 以前はここで文字列結合(内部
        ラベル付き)を行っていたが、それ自体がバグの原因だったため廃止
        した。呼び出し側(`app/routers/ai.py`)は、この2つの値を
        `PromptPipeline.run(natural_language=original, clarification_
        answer=answer)`のように、**別引数として**渡すこと。

        ラウンド数が上限を超える場合は`ConfirmationRoundExceededError`を
        送出する(呼び出し元でPendingは破棄済みなので、UIは新しい入力
        からやり直す必要がある)。
        """
        record = self.get(request_id)
        self.discard(request_id)
        if record.round_count >= MAX_CONFIRMATION_ROUNDS:
            raise ConfirmationRoundExceededError(record.round_count)
        return record, record.original_natural_language, answer

    def size(self) -> int:
        with self._lock:
            return len(self._pending)


# アプリ全体で1つのStoreを共有する(モジュールレベルSingleton、
# `app/routers/ai.py`から参照される)。
default_confirmation_store = ConfirmationStore()
