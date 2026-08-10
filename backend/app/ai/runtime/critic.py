"""AI Runtime — Critic(FORGE-MILESTONE-003 PHASE6/7/8)。

**責務定義のみ。実装は含まない。**

`CriticResult`は`foundation/interfaces.py`に既に存在する型をそのまま再利用する
(重複定義しない。`planner.py`冒頭のコメントと同じ理由)。
"""

from __future__ import annotations

from typing import Protocol

from app.ai.foundation.interfaces import CriticResult
from app.ai.runtime.planner import Intent

__all__ = ["CriticResult", "AICritic", "StubAICritic"]


class AICritic(Protocol):
    """合格した文書に対する品質評価を行う契約(PHASE7の要求名)。
    既存の`Critic`(foundation/interfaces.py)と同一の責務を、
    `runtime/`パッケージの命名規則(`AI`接頭辞)に合わせて再定義したもの。
    """

    def evaluate(self, document: dict[str, object], intent: Intent) -> CriticResult:
        """文書とIntentから、構造化されたCriticResultを返す。"""
        ...


class StubAICritic:
    """`AICritic`の未実装スタブ。"""

    def evaluate(self, document: dict[str, object], intent: Intent) -> CriticResult:
        """未実装。"""
        raise NotImplementedError(
            "StubAICritic.evaluate() は未実装です(FORGE-MILESTONE-003 PHASE6/7は"
            "責務定義のみ)。実装にはCEO承認(Native AI接続)が必要です。"
        )
