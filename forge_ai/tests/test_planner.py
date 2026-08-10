"""planner.py のテスト。特に「PlannerはRuntimeを知らない」という設計原則の
回帰テストを重視する。"""

from __future__ import annotations

import re
import unittest

from forge_ai.core.domain_model import DomainCategory, DomainRegistry
from forge_ai.core.intent_model import IntentBuilder
from forge_ai.core.meaning_model import MeaningExtractor
from forge_ai.core.planner import Planner
from forge_ai.core.world_model import WorldModelBuilder
from forge_ai.provider.mock_provider import MockProvider

_FORGE_WIDGET_VOCABULARY = {
    "text_field", "checkbox", "checklist", "divider", "heading", "card",
    "column", "row", "text", "button", "state_ref", "target_screen_id",
}


class TestPlanner(unittest.TestCase):
    def setUp(self) -> None:
        self.provider = MockProvider()
        self.registry = DomainRegistry()

    def _build_intent(self, text: str, category: DomainCategory):
        world = WorldModelBuilder().build(self.registry.get(category))
        meaning = MeaningExtractor(self.provider).extract(text, world)
        return IntentBuilder(self.provider).build(meaning, world)

    def test_plan_produces_at_least_one_screen(self) -> None:
        intent = self._build_intent("add item track price", DomainCategory.SHOPPING)
        plan = Planner(self.provider).plan(intent)
        self.assertGreaterEqual(len(plan.screens), 1)

    def test_plan_title_is_nonempty(self) -> None:
        intent = self._build_intent("add item", DomainCategory.SHOPPING)
        plan = Planner(self.provider).plan(intent)
        self.assertTrue(plan.title.strip())

    def test_plan_never_mentions_forge_widget_vocabulary(self) -> None:
        """PlannerはRuntimeを知らない、という設計原則の回帰テスト。
        ScreenPlan.key_elements等にForge Widget型名が紛れ込んでいないことを
        全Domainで確認する。"""
        for category in DomainCategory:
            with self.subTest(category=category):
                intent = self._build_intent(f"manage {category.value} records", category)
                plan = Planner(self.provider).plan(intent)
                plan_text = " ".join(
                    [plan.title]
                    + [s.name for s in plan.screens]
                    + [s.purpose for s in plan.screens]
                    + [e for s in plan.screens for e in s.key_elements]
                ).lower()
                for term in _FORGE_WIDGET_VOCABULARY:
                    # 単純substring一致だと、Domain名に偶然Runtime語彙を含む
                    # 部分文字列がある場合(例: "growth"は"row"を含む)に
                    # 誤検出する(FORGE v0.2 P2 11章でchild_growth Domainを
                    # 追加した際に実際に発見)。単語境界を考慮した一致へ
                    # 修正し、本来の目的(Runtime Widget語彙が"単語として"
                    # 紛れ込んでいないかの検出)を壊さずに誤検出を防ぐ。
                    self.assertIsNone(
                        re.search(rf"\b{re.escape(term)}\b", plan_text),
                        f"Planに'{term}'というRuntime語彙が単語として含まれています: {plan_text!r}",
                    )

    def test_plan_data_entities_default_to_intent_concepts(self) -> None:
        intent = self._build_intent("add item", DomainCategory.SHOPPING)
        plan = Planner(self.provider).plan(intent)
        self.assertGreater(len(plan.data_entities), 0)

    def test_plan_never_crashes_across_all_domains(self) -> None:
        for category in DomainCategory:
            with self.subTest(category=category):
                intent = self._build_intent(f"manage {category.value}", category)
                plan = Planner(self.provider).plan(intent)
                self.assertIsNotNone(plan)


if __name__ == "__main__":
    unittest.main()
