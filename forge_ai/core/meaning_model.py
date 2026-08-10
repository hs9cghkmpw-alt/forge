"""Meaning Model。

ユーザー文章から意味を抽出する。World Modelを直接変更してはいけない
(このモジュールはWorldを読み取り専用の参照としてのみ使う)。

実際の抽出処理は`AIProvider`へ委譲する(Dependency Injection)。
テスト・開発では`MockProvider`(決定的、キーワードベース)を使う。
"""

from __future__ import annotations

from dataclasses import dataclass

from forge_ai.core.world_model import World
from forge_ai.prompt.prompt_builder import PromptBuilder
from forge_ai.provider.provider_interface import AIProvider


@dataclass(frozen=True)
class ExtractedMeaning:
    """1回のユーザー発話から抽出された意味。"""

    raw_text: str
    mentioned_concepts: tuple[str, ...]
    mentioned_actions: tuple[str, ...]
    keywords: tuple[str, ...]


class MeaningExtractor:
    """`AIProvider`を注入して使う。Providerの具体実装は知らない。"""

    def __init__(self, provider: AIProvider, prompt_builder: PromptBuilder | None = None) -> None:
        self._provider = provider
        self._prompt_builder = prompt_builder or PromptBuilder()

    def extract(self, text: str, world: World) -> ExtractedMeaning:
        """`world`は文脈として渡すのみで、このメソッド内で変更しない
        (Worldはfrozen dataclassのため、そもそも変更不能でもある)。"""
        prompt = self._prompt_builder.build_meaning_prompt(
            user_text=text, domain_name=world.domain.display_name
        )
        response = self._provider.complete(prompt)
        structured = response.structured
        return ExtractedMeaning(
            raw_text=text,
            mentioned_concepts=tuple(structured.get("mentioned_concepts", ())),
            mentioned_actions=tuple(structured.get("mentioned_actions", ())),
            keywords=tuple(structured.get("keywords", ())),
        )
