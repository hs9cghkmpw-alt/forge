"""AI Runtime — Template Selector(FORGE-MILESTONE-004 PHASE5)。

**責務定義のみ。実装は含まない。**

`ProviderRouter`(PHASE8、`provider_router.py`)のルーティングロジックは
「文字列キーの辞書引き」という非AI的な処理だったため実装済みだが、
Template Selectorは「PlanIR/IntentIRの内容を理解し、最も適切なTemplateを
選ぶ」という判断そのものがAI推論に相当するため、Stubとする
(禁止事項「AI実装したふり」を避けるための一貫した境界線。
docs/spec/AI_RUNTIME.md 4章と同じ考え方)。
"""

from __future__ import annotations

from typing import Protocol

from app.ai.foundation.interfaces import IntentIR, PlanIR
from app.ai.runtime.template_engine import Template, TemplateRegistry


class TemplateSelector(Protocol):
    """IntentIR・PlanIRから、TemplateRegistry内の最適なTemplateを選ぶ契約。"""

    def select(self, intent: IntentIR, plan: PlanIR, registry: TemplateRegistry) -> Template:
        """最も適切な`Template`を1つ返す。該当が無い場合の扱い(汎用
        Templateへのフォールバック等)は実装側の責務とする。"""
        ...


class StubTemplateSelector:
    """`TemplateSelector`の未実装スタブ。"""

    def select(self, intent: IntentIR, plan: PlanIR, registry: TemplateRegistry) -> Template:
        """未実装。"""
        raise NotImplementedError(
            "StubTemplateSelector.select() は未実装です(FORGE-MILESTONE-004 PHASE5は"
            "責務定義のみ)。実装にはCEO承認(Native AI接続)が必要です。"
        )
