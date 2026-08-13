"""Conversation Metrics(FORGE-CONVERSATION-READY-001、2026-08-12、指示書10章)。

会話の**質**を後から測れるようにするための、構造化メトリクス。

**Privacy方針(指示書10章)**: 生の会話本文をデフォルトで永続保存しない。
このモジュールが記録するのは、

* session_idのハッシュ(元のidへ戻せない)
* actionの種類(ask/confirm/build/update/build_failed など)
* readinessの種類
* 質問したUnknownの**key**("shared_usage"のような概念名であり、
  ユーザーの発話そのものではない)
* 件数・回数

だけである。ユーザーが何と言ったか、Forgeが何と答えたかという本文は
一切残さない。

**現時点の保存先はプロセス内メモリ**である(`ConversationStore`・
`ConfirmationStore`と同じ既知の制限、TD41)。指示書10章は「将来測れる
形だけでも準備する」ことを求めており、外部の分析基盤へ送る実装は
CEO判断(外部サービス利用)が要るため、ここでは行わない。
"""

from __future__ import annotations

import hashlib
from collections import Counter
from dataclasses import dataclass, field
from threading import Lock

__all__ = [
    "ConversationMetrics",
    "ConversationMetricsCollector",
    "default_conversation_metrics",
    "record_conversation_event",
]

# 1セッションあたりの保持イベント数の上限。無制限に貯めるとメモリを
# 圧迫するため(プロセス内メモリ実装であることを踏まえた保守的な上限)。
_MAX_EVENTS_PER_SESSION = 50


def _hash_session_id(session_id: str) -> str:
    """session_idを元へ戻せない短いハッシュへ変換する。

    メトリクス上「同じ会話の一連のイベント」をまとめるためだけに使う
    (誰の会話かを特定するためではない)。
    """
    return hashlib.sha256(session_id.encode("utf-8")).hexdigest()[:16]


@dataclass(frozen=True)
class ConversationMetrics:
    """指示書10章が列挙する測定項目。"""

    questions_before_build: int = 0
    blocking_unknowns_at_build: int = 0
    safe_assumptions_at_build: int = 0
    confirm_count: int = 0
    update_count: int = 0
    repeated_question_count: int = 0
    build_failure_count: int = 0
    build_to_ask_fallback_count: int = 0

    def to_dict(self) -> dict[str, int]:
        return {
            "questions_before_build": self.questions_before_build,
            "blocking_unknowns_at_build": self.blocking_unknowns_at_build,
            "safe_assumptions_at_build": self.safe_assumptions_at_build,
            "confirm_count": self.confirm_count,
            "update_count": self.update_count,
            "repeated_question_count": self.repeated_question_count,
            "build_failure_count": self.build_failure_count,
            "build_to_ask_fallback_count": self.build_to_ask_fallback_count,
        }


@dataclass
class _SessionRecord:
    asked_keys: list[tuple[str, str]] = field(default_factory=list)
    actions: Counter = field(default_factory=Counter)
    repeated_question_count: int = 0
    blocking_unknowns_at_build: int = 0
    safe_assumptions_at_build: int = 0
    event_count: int = 0


class ConversationMetricsCollector:
    """プロセス内メモリの集計器。スレッドセーフ。"""

    def __init__(self) -> None:
        self._lock = Lock()
        self._sessions: dict[str, _SessionRecord] = {}

    def record(
        self,
        session_id: str,
        action: str,
        *,
        readiness: str | None = None,
        question_key: str | None = None,
        strategy: str | None = None,
        blocking_unknowns: int = 0,
        safe_assumptions: int = 0,
    ) -> None:
        """1イベント記録する。**本文は受け取らない**(引数に無い)。"""
        key = _hash_session_id(session_id)
        with self._lock:
            record = self._sessions.setdefault(key, _SessionRecord())
            if record.event_count >= _MAX_EVENTS_PER_SESSION:
                return
            record.event_count += 1
            record.actions[action] += 1
            if readiness:
                record.actions[f"readiness:{readiness}"] += 1
            if question_key:
                # FORGE-QUALITY-AI-INDEPENDENCE-003 §15: Strategy
                # Escalationにより、同じUnknownへ段を変えて聞き直すのは
                # 正常な進行になった。「繰り返し質問」として数えるのは
                # **同じkeyを同じ段で**聞いた場合だけである。
                pair = (question_key, strategy or "ask")
                if pair in record.asked_keys:
                    record.repeated_question_count += 1
                record.asked_keys.append(pair)
            if action in ("build", "update"):
                record.blocking_unknowns_at_build = blocking_unknowns
                record.safe_assumptions_at_build = safe_assumptions

    def snapshot(self, session_id: str) -> ConversationMetrics:
        key = _hash_session_id(session_id)
        with self._lock:
            record = self._sessions.get(key)
            if record is None:
                return ConversationMetrics()
            return ConversationMetrics(
                questions_before_build=record.actions.get("ask", 0),
                blocking_unknowns_at_build=record.blocking_unknowns_at_build,
                safe_assumptions_at_build=record.safe_assumptions_at_build,
                confirm_count=record.actions.get("confirm", 0),
                update_count=record.actions.get("update", 0),
                repeated_question_count=record.repeated_question_count,
                build_failure_count=record.actions.get("build_failed", 0),
                build_to_ask_fallback_count=record.actions.get("build_to_ask_fallback", 0),
            )

    def reset(self) -> None:
        """テスト用。"""
        with self._lock:
            self._sessions.clear()

    def session_count(self) -> int:
        with self._lock:
            return len(self._sessions)


default_conversation_metrics = ConversationMetricsCollector()


def record_conversation_event(
    session_id: str,
    action: str,
    *,
    readiness: str | None = None,
    question_key: str | None = None,
    strategy: str | None = None,
    blocking_unknowns: int = 0,
    safe_assumptions: int = 0,
) -> None:
    """モジュールレベルのSingletonへ記録する簡易入口
    (`default_conversation_store`と同じパターン)。"""
    default_conversation_metrics.record(
        session_id, action, readiness=readiness, question_key=question_key,
        strategy=strategy,
        blocking_unknowns=blocking_unknowns, safe_assumptions=safe_assumptions,
    )
