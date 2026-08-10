"""Intent Model。

Meaningを、Forgeが処理可能な構造(Intent)へ変換する。
"""

from __future__ import annotations

from dataclasses import dataclass

from forge_ai.core.meaning_model import ExtractedMeaning
from forge_ai.core.world_model import World
from forge_ai.prompt.prompt_builder import PromptBuilder
from forge_ai.provider.provider_interface import AIProvider


@dataclass(frozen=True)
class Intent:
    """Forgeパイプラインが処理可能な、目的・必要概念・必要操作・制約の集合。

    FORGE-MILESTONE-007第一段階で、M006 7章(Intent Recognition)が
    要求する追加フィールドを、既定値付きで追加した(既存の
    `Intent(goal=..., required_concepts=..., required_actions=...,
    constraints=...)`という呼び出し方は無変更で動く。IntentIR/PlanIR
    拡張時と同じ、実績のある後方互換の手法)。

    これらの新フィールドは、Legacy経路(`IntentBuilder`、既存)では
    常に既定値のままになる(Legacy Protocolは変更しないため)。
    Cognitive経路(`understanding/intent_recognizer.py`、新規)のみが
    これらを実際に埋める。
    """

    goal: str
    required_concepts: tuple[str, ...]
    required_actions: tuple[str, ...]
    constraints: tuple[str, ...]
    secondary_goals: tuple[str, ...] = ()
    actors: tuple[str, ...] = ()
    required_data: tuple[str, ...] = ()
    success_conditions: tuple[str, ...] = ()
    prohibited_behaviors: tuple[str, ...] = ()
    open_questions: tuple[str, ...] = ()
    confidence: float = 1.0
    evidence: tuple[str, ...] = ()


class IntentBuilder:
    """`AIProvider`を注入して使う。"""

    def __init__(self, provider: AIProvider, prompt_builder: PromptBuilder | None = None) -> None:
        self._provider = provider
        self._prompt_builder = prompt_builder or PromptBuilder()

    def build(self, meaning: ExtractedMeaning, world: World) -> Intent:
        """ExtractedMeaningとWorldから、Providerを通じてIntentを構築する。
        Providerが具体的な概念を返さなかった場合はWorldの既知概念へ
        安全にフォールバックする。"""
        prompt = self._prompt_builder.build_intent_prompt(
            meaning_summary={
                "mentioned_concepts": list(meaning.mentioned_concepts),
                "mentioned_actions": list(meaning.mentioned_actions),
                "keywords": list(meaning.keywords),
            },
            domain_name=world.domain.display_name,
        )
        response = self._provider.complete(prompt)
        structured = response.structured
        return Intent(
            goal=str(structured.get("goal", f"{world.domain.display_name}を管理する")),
            required_concepts=tuple(structured.get("required_concepts", ())) or _fallback_concepts(world),
            required_actions=tuple(structured.get("required_actions", ())) or ("add_item",),
            constraints=tuple(structured.get("constraints", ())),
        )


def _fallback_concepts(world: World) -> tuple[str, ...]:
    """Providerが具体的な概念を1つも返さなかった場合の安全なフォールバック。
    クラッシュさせず、Worldが持つ既知の概念から補う。"""
    if world.objects:
        return tuple(o.name for o in world.objects)
    return ("item",)
