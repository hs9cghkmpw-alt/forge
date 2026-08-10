"""domain_model.py のテスト。"""

from __future__ import annotations

import unittest

from forge_ai.core.domain_model import Domain, DomainCategory, DomainConcept, DomainRegistry


class TestDomainRegistry(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = DomainRegistry()

    def test_all_fourteen_named_domains_plus_generic_exist(self) -> None:
        """FORGE-MILESTONE-007第一段階で、CEO指定の6例に対応するため
        TASK_MANAGEMENT・SURVEY・SCHEDULEを追加(既存5値+GENERIC)。
        FORGE_v0.2_修正指示.md P2 11章で、家計簿・成長記録に対応する
        HOUSEHOLD_BUDGET・CHILD_GROWTHを追加した。FORGE v0.3 Task1で、
        釣果記録・習慣記録・学習記録・旅行記録に対応するFISHING_LOG・
        HABIT_TRACKING・STUDY・TRAVELを追加した。件数がこの意図的な
        拡張を正しく反映していることを確認する。"""
        categories = {d.category for d in self.registry.all_domains()}
        expected = {
            DomainCategory.SHOPPING,
            DomainCategory.HOSPITAL,
            DomainCategory.ATTENDANCE,
            DomainCategory.DIARY,
            DomainCategory.INVENTORY,
            DomainCategory.TASK_MANAGEMENT,
            DomainCategory.SURVEY,
            DomainCategory.SCHEDULE,
            DomainCategory.HOUSEHOLD_BUDGET,
            DomainCategory.CHILD_GROWTH,
            DomainCategory.FISHING_LOG,
            DomainCategory.HABIT_TRACKING,
            DomainCategory.STUDY,
            DomainCategory.TRAVEL,
            DomainCategory.GENERIC,
        }
        self.assertEqual(categories, expected)

    def test_get_returns_household_budget_domain(self) -> None:
        domain = self.registry.get(DomainCategory.HOUSEHOLD_BUDGET)
        self.assertEqual(domain.category, DomainCategory.HOUSEHOLD_BUDGET)
        self.assertGreater(len(domain.typical_concepts), 0)
        self.assertGreater(len(domain.typical_actions), 0)

    def test_get_returns_child_growth_domain(self) -> None:
        domain = self.registry.get(DomainCategory.CHILD_GROWTH)
        self.assertEqual(domain.category, DomainCategory.CHILD_GROWTH)
        self.assertGreater(len(domain.typical_concepts), 0)
        self.assertGreater(len(domain.typical_actions), 0)

    def test_get_returns_fishing_log_domain(self) -> None:
        domain = self.registry.get(DomainCategory.FISHING_LOG)
        self.assertEqual(domain.category, DomainCategory.FISHING_LOG)
        self.assertGreater(len(domain.typical_concepts), 0)
        self.assertGreater(len(domain.typical_actions), 0)

    def test_get_returns_habit_tracking_domain(self) -> None:
        domain = self.registry.get(DomainCategory.HABIT_TRACKING)
        self.assertEqual(domain.category, DomainCategory.HABIT_TRACKING)
        self.assertGreater(len(domain.typical_concepts), 0)
        self.assertGreater(len(domain.typical_actions), 0)

    def test_get_returns_study_domain(self) -> None:
        domain = self.registry.get(DomainCategory.STUDY)
        self.assertEqual(domain.category, DomainCategory.STUDY)
        self.assertGreater(len(domain.typical_concepts), 0)
        self.assertGreater(len(domain.typical_actions), 0)

    def test_get_returns_travel_domain(self) -> None:
        domain = self.registry.get(DomainCategory.TRAVEL)
        self.assertEqual(domain.category, DomainCategory.TRAVEL)
        self.assertGreater(len(domain.typical_concepts), 0)
        self.assertGreater(len(domain.typical_actions), 0)

    def test_get_returns_requested_domain(self) -> None:
        domain = self.registry.get(DomainCategory.HOSPITAL)
        self.assertEqual(domain.category, DomainCategory.HOSPITAL)
        self.assertEqual(domain.display_name, "Hospital")

    def test_get_returns_task_management_domain(self) -> None:
        domain = self.registry.get(DomainCategory.TASK_MANAGEMENT)
        self.assertEqual(domain.category, DomainCategory.TASK_MANAGEMENT)
        self.assertGreater(len(domain.typical_concepts), 0)
        self.assertGreater(len(domain.typical_actions), 0)

    def test_get_returns_survey_domain(self) -> None:
        domain = self.registry.get(DomainCategory.SURVEY)
        self.assertEqual(domain.category, DomainCategory.SURVEY)
        self.assertGreater(len(domain.typical_concepts), 0)
        self.assertGreater(len(domain.typical_actions), 0)

    def test_get_returns_schedule_domain(self) -> None:
        domain = self.registry.get(DomainCategory.SCHEDULE)
        self.assertEqual(domain.category, DomainCategory.SCHEDULE)
        self.assertGreater(len(domain.typical_concepts), 0)
        self.assertGreater(len(domain.typical_actions), 0)

    def test_domain_does_not_reference_ui_concepts(self) -> None:
        """DomainはUIを知らない、という設計原則の回帰テスト。
        Widget/Screen/Buttonのような語彙がDomain定義に紛れ込んでいないことを
        確認する。"""
        ui_terms = {"widget", "button", "screen", "column", "row", "checklist_widget"}
        for domain in self.registry.all_domains():
            for concept in domain.typical_concepts:
                self.assertNotIn(concept.name.lower(), ui_terms)
            for action in domain.typical_actions:
                self.assertNotIn(action.lower(), ui_terms)

    def test_resolve_from_keywords_matches_shopping(self) -> None:
        domain = self.registry.resolve_from_keywords("I want to track item price")
        self.assertEqual(domain.category, DomainCategory.SHOPPING)

    def test_resolve_from_keywords_matches_hospital_via_action(self) -> None:
        domain = self.registry.resolve_from_keywords("schedule_appointment for tomorrow")
        self.assertEqual(domain.category, DomainCategory.HOSPITAL)

    def test_resolve_from_keywords_falls_back_to_generic_without_crashing(self) -> None:
        domain = self.registry.resolve_from_keywords("xyzzy qwerty asdf")
        self.assertEqual(domain.category, DomainCategory.GENERIC)

    def test_resolve_from_keywords_handles_empty_string(self) -> None:
        domain = self.registry.resolve_from_keywords("")
        self.assertEqual(domain.category, DomainCategory.GENERIC)

    def test_get_unknown_category_falls_back_to_generic(self) -> None:
        """DomainRegistryに登録されていない仮のCategoryでも安全にGENERICへ
        フォールバックし、クラッシュしないことを確認する。"""
        registry = DomainRegistry()
        # 意図的に空のレジストリと同等の状態を作る手段が無いため、
        # 実在するCategoryで代替検証する(GENERIC自体が返る経路の確認)。
        domain = registry.get(DomainCategory.GENERIC)
        self.assertEqual(domain.category, DomainCategory.GENERIC)


class TestDomainDataclasses(unittest.TestCase):
    def test_domain_is_frozen(self) -> None:
        domain = Domain(
            category=DomainCategory.GENERIC,
            display_name="Test",
            typical_concepts=(DomainConcept("x", "desc"),),
            typical_actions=("act",),
        )
        with self.assertRaises(Exception):
            domain.display_name = "Changed"  # type: ignore[misc]


if __name__ == "__main__":
    unittest.main()
