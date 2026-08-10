"""Planner。

Intentから Application Plan を生成する。まだJSON(Forge IR)は生成しない。
PlannerはRuntimeを一切知らない — `ScreenPlan.key_elements`は
「何を表示・操作したいか」を表す抽象的な語彙であり、Forge Widget種別
(text / button / checklist 等)を一切含まない。Widget種別への変換は
Compilerの責務である。
"""

from __future__ import annotations

from dataclasses import dataclass

from forge_ai.core.intent_model import Intent
from forge_ai.prompt.prompt_builder import PromptBuilder
from forge_ai.provider.provider_interface import AIProvider


@dataclass(frozen=True)
class ScreenPlan:
    """1画面分の抽象的な計画。Widget種別を含まない。

    FORGE-MILESTONE-007第一段階で、CEOが要求する出力項目
    (各画面の責務・必要データ・主な操作・Empty State・Validation)を
    満たすため、既定値付きでフィールドを追加した(既存の
    `ScreenPlan(name=..., purpose=..., key_elements=...)`という
    呼び出し方は無変更で動く)。
    """

    name: str
    purpose: str
    key_elements: tuple[str, ...]
    required_actions: tuple[str, ...] = ()
    empty_state_message: str = ""
    validation_rules: tuple[str, ...] = ()


@dataclass(frozen=True)
class ApplicationPlan:
    """アプリ全体の抽象的な計画。

    FORGE-MILESTONE-007第一段階で、`navigation_edges`
    (画面間遷移)・`unassigned_requirements`(どの画面にも割り当てら
    れなかった要件、既存`PlanIR.unassigned_actions`と同じ「捨てずに
    保持する」手法)を、既定値付きで追加した。
    """

    title: str
    screens: tuple[ScreenPlan, ...]
    data_entities: tuple[str, ...]
    primary_flow: tuple[str, ...]
    navigation_edges: tuple[tuple[str, str], ...] = ()  # (from_screen_name, to_screen_name)
    unassigned_requirements: tuple[str, ...] = ()


class Planner:
    """`AIProvider`を注入して使う。RuntimeやForge IRの語彙は一切importしない。"""

    def __init__(self, provider: AIProvider, prompt_builder: PromptBuilder | None = None) -> None:
        self._provider = provider
        self._prompt_builder = prompt_builder or PromptBuilder()

    def plan(self, intent: Intent) -> ApplicationPlan:
        """IntentからApplicationPlanを構築する。ScreenPlan.key_elementsは
        Forge Widget種別を含まない、抽象的な語彙のみで構成される。"""
        prompt = self._prompt_builder.build_planning_prompt(
            intent_summary={
                "goal": intent.goal,
                "required_concepts": list(intent.required_concepts),
                "required_actions": list(intent.required_actions),
                "constraints": list(intent.constraints),
            }
        )
        response = self._provider.complete(prompt)
        structured = response.structured

        raw_screens = structured.get("screens") or (
            {"name": "main", "purpose": intent.goal, "key_elements": list(intent.required_concepts)},
        )
        screens = tuple(
            ScreenPlan(
                name=str(s.get("name", "main")),
                purpose=str(s.get("purpose", intent.goal)),
                key_elements=tuple(s.get("key_elements", ())),
            )
            for s in raw_screens
        )

        return ApplicationPlan(
            title=str(structured.get("title", intent.goal)),
            screens=screens,
            data_entities=tuple(structured.get("data_entities", ())) or intent.required_concepts,
            primary_flow=tuple(structured.get("primary_flow", ())),
        )
