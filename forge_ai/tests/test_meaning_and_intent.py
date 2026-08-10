"""meaning_model.py と intent_model.py のテスト。"""

from __future__ import annotations

import unittest

from forge_ai.core.domain_model import DomainCategory, DomainRegistry
from forge_ai.core.intent_model import IntentBuilder
from forge_ai.core.meaning_model import MeaningExtractor
from forge_ai.core.world_model import World, WorldModelBuilder
from forge_ai.provider.mock_provider import MockProvider


class TestMeaningExtractor(unittest.TestCase):
    def setUp(self) -> None:
        self.provider = MockProvider()
        self.extractor = MeaningExtractor(self.provider)
        registry = DomainRegistry()
        self.world = WorldModelBuilder().build(registry.get(DomainCategory.SHOPPING))

    def test_extract_returns_raw_text_unchanged(self) -> None:
        meaning = self.extractor.extract("add item track price", self.world)
        self.assertEqual(meaning.raw_text, "add item track price")

    def test_extract_does_not_mutate_world(self) -> None:
        """Worldはfrozen dataclassのため変更不能だが、それでも同一性(id)が
        保たれる(新しいWorldを作って差し替えたりしていない)ことを確認する。"""
        world_id_before = id(self.world)
        self.extractor.extract("add item", self.world)
        self.assertEqual(id(self.world), world_id_before)

    def test_extract_populates_keywords(self) -> None:
        meaning = self.extractor.extract("add item track price", self.world)
        self.assertGreater(len(meaning.keywords), 0)

    def test_extract_handles_empty_input_without_crashing(self) -> None:
        meaning = self.extractor.extract("", self.world)
        self.assertEqual(meaning.mentioned_concepts, ())


class TestIntentBuilder(unittest.TestCase):
    def setUp(self) -> None:
        self.provider = MockProvider()
        self.extractor = MeaningExtractor(self.provider)
        self.intent_builder = IntentBuilder(self.provider)
        registry = DomainRegistry()
        self.world = WorldModelBuilder().build(registry.get(DomainCategory.SHOPPING))

    def test_build_produces_nonempty_goal(self) -> None:
        meaning = self.extractor.extract("add item track price", self.world)
        intent = self.intent_builder.build(meaning, self.world)
        self.assertTrue(intent.goal.strip())

    def test_build_falls_back_to_world_concepts_when_meaning_is_empty(self) -> None:
        """MeaningがconceptsをMockProviderから1つも得られなかった場合でも、
        Worldの既知概念にフォールバックし、空のIntentにならないことを確認する。"""
        meaning = self.extractor.extract("", self.world)
        intent = self.intent_builder.build(meaning, self.world)
        self.assertGreater(len(intent.required_concepts), 0)

    def test_build_never_crashes_across_all_domains(self) -> None:
        registry = DomainRegistry()
        for category in DomainCategory:
            with self.subTest(category=category):
                world = WorldModelBuilder().build(registry.get(category))
                meaning = self.extractor.extract(f"manage {category.value}", world)
                intent = self.intent_builder.build(meaning, world)
                self.assertIsNotNone(intent)


if __name__ == "__main__":
    unittest.main()
