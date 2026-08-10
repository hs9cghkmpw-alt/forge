"""Forge Native AI v0 — Rule Based Template Selector(`_03_template`)。

FORGE-MILESTONE-004で定義した`app.ai.runtime.template_selector.
TemplateSelector` Protocolの、**実際に動作する**実装。Milestone-004時点では
「Templateを選ぶ判断はAI推論に相当する」としてStubのままにしていたが、
Native AI v0では「ルールベースで選ぶ」という方針(指示書10章)のため、
IntentIR.output_type(`_01_intent`が既にルールで決定済み)をそのまま
`TemplateRegistry`のcategoryへ対応付けるだけの、決定的な実装が可能になった。

Template自体のカタログ(`Template`/`TemplateRegistry`)は
`app.ai.runtime.template_engine`(FORGE-MILESTONE-004)をそのまま再利用する
(重複定義しない)。
"""

from __future__ import annotations

from app.ai.foundation.interfaces import IntentIR, PlanIR
from app.ai.runtime.template_engine import Template, TemplateRegistry


class RuleBasedTemplateSelector:
    """`TemplateSelector` Protocolを満たす、決定的な実装。

    IntentIR.output_type(checklist/memo/form)を、TemplateRegistryの
    category(同名)へそのまま対応付ける。該当が無い場合はchecklistへ
    安全にフォールバックする(未知の入力でも例外を投げない)。
    """

    def select(self, intent: IntentIR, plan: PlanIR, registry: TemplateRegistry) -> Template:
        category = intent.output_type or plan.template_hint or "checklist"
        matches = registry.by_category(category)
        if matches:
            return matches[0]
        # 安全なフォールバック: checklistは必ず登録されている(TemplateRegistry
        # の組み込みTemplateのため)。
        fallback = registry.by_category("checklist")
        return fallback[0]
