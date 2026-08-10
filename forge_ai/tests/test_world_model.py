"""world_model.py のテスト。"""

from __future__ import annotations

import unittest

from forge_ai.core.domain_model import DomainCategory, DomainRegistry
from forge_ai.core.world_model import WorldModelBuilder


class TestWorldModelBuilder(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = DomainRegistry()
        self.builder = WorldModelBuilder()

    def test_build_produces_at_least_one_actor(self) -> None:
        world = self.builder.build(self.registry.get(DomainCategory.SHOPPING))
        self.assertGreaterEqual(len(world.actors), 1)

    def test_build_objects_match_domain_concepts(self) -> None:
        domain = self.registry.get(DomainCategory.SHOPPING)
        world = self.builder.build(domain)
        object_names = {o.name for o in world.objects}
        concept_names = {c.name for c in domain.typical_concepts}
        self.assertEqual(object_names, concept_names)

    def test_build_creates_relationships_for_each_action(self) -> None:
        domain = self.registry.get(DomainCategory.HOSPITAL)
        world = self.builder.build(domain)
        self.assertEqual(len(world.relationships), len(domain.typical_actions))

    def test_build_creates_a_rule_per_concept(self) -> None:
        domain = self.registry.get(DomainCategory.DIARY)
        world = self.builder.build(domain)
        self.assertEqual(len(world.rules), len(domain.typical_concepts))

    def test_world_retains_reference_to_domain(self) -> None:
        domain = self.registry.get(DomainCategory.INVENTORY)
        world = self.builder.build(domain)
        self.assertEqual(world.domain, domain)

    def test_build_does_not_crash_for_generic_domain(self) -> None:
        world = self.builder.build(self.registry.get(DomainCategory.GENERIC))
        self.assertIsNotNone(world)

    def test_all_six_domains_build_without_error(self) -> None:
        for category in DomainCategory:
            with self.subTest(category=category):
                world = self.builder.build(self.registry.get(category))
                self.assertEqual(world.domain.category, category)


if __name__ == "__main__":
    unittest.main()
