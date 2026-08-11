"""repair_engine.py のテスト。"""

from __future__ import annotations

import unittest

from forge_ai.core.compiler import ForgeIRDocument, ForgeIRScreen, ForgeIRStateValue, ForgeIRWidget
from forge_ai.provider.mock_provider import MockProvider
from forge_ai.repair.repair_engine import RepairEngine, RepairIssue


def _make_ir(app_title: str | None = None, checklist_value: list | None = None) -> ForgeIRDocument:
    screen = ForgeIRScreen(
        id="s1",
        title="Test",
        state={"items": ForgeIRStateValue(type="checklist", value=checklist_value or [])},
        body=ForgeIRWidget(type="checklist", id="cl1", properties={"state_ref": "items"}),
    )
    return ForgeIRDocument(version="1.0", initial_screen_id="s1", screens=(screen,), app_title=app_title)


class TestRepairEngine(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = RepairEngine(MockProvider())

    def test_repair_fixes_missing_app_title(self) -> None:
        """forge_ai自身が直接`RepairIssue`を構築する場合(Adapterを経由
        しない呼び出し)の後方互換を確認する。"""
        ir = _make_ir(app_title=None)
        issues = (RepairIssue(path="$/app", category="missing_app_title", message="タイトルがありません"),)
        result = self.engine.repair(ir, issues)
        self.assertIsNotNone(result.ir.app_title)
        self.assertIn("missing_app_title", [i.category for i in result.fixed_issues])
        self.assertEqual(result.remaining_issues, ())

    def test_repair_fixes_invalid_app_title_length_from_real_validator_rule_name(self) -> None:
        """FORGE-AI-QUALITY-001(2026-08-11)回帰テスト: 実際の
        `backend/app/ai/validators/schema_validator.py`が生成する
        rule名(`"string_length"`)+path(`.../app/title`)で、正しく
        タイトルを修正できることを確認する(以前は`category`に
        Category enum値(`"schema"`等)が渡っていたため、この現実の
        パターンを一度も修正できていなかった、TD31参照)。"""
        ir = _make_ir(app_title="")
        issues = (RepairIssue(path="$/app/title", category="string_length", message="1〜80文字である必要があります"),)
        result = self.engine.repair(ir, issues)
        self.assertIsNotNone(result.ir.app_title)
        self.assertEqual(result.remaining_issues, ())

    def test_repair_does_not_fix_string_length_issues_on_unrelated_paths(self) -> None:
        """`string_length`はchecklist項目のtext等、app.title以外にも
        使われうるrule名のため、pathで正しく絞り込めていることを確認する
        (誤ってtitle以外を「タイトル修正」ロジックで扱わないこと)。"""
        ir = _make_ir(app_title="Already Set")
        issues = (
            RepairIssue(path="$/screens/0/state/items/value/0/text", category="string_length", message="不正な長さ"),
        )
        result = self.engine.repair(ir, issues)
        self.assertEqual(result.ir.app_title, "Already Set")
        self.assertEqual(len(result.remaining_issues), 1)

    def test_repair_leaves_unknown_category_unresolved_without_crashing(self) -> None:
        ir = _make_ir()
        issues = (RepairIssue(path="$/x", category="some_unknown_category", message="不明"),)
        result = self.engine.repair(ir, issues)
        self.assertEqual(len(result.remaining_issues), 1)
        self.assertEqual(result.remaining_issues[0].category, "some_unknown_category")

    def test_repair_with_no_issues_is_a_no_op(self) -> None:
        ir = _make_ir(app_title="Already Set")
        result = self.engine.repair(ir, ())
        self.assertEqual(result.ir.app_title, "Already Set")
        self.assertEqual(result.iterations, 0)

    def test_repair_does_not_loop_forever_on_unfixable_issues(self) -> None:
        """指示書「複数回実行可能」だが無限リトライは禁止(禁止事項11章)。
        1回も直せない問題に対して、max_iterationsを超えて回り続けないことを
        確認する。"""
        ir = _make_ir()
        issues = tuple(
            RepairIssue(path=f"$/x{i}", category="unfixable", message="直せません") for i in range(5)
        )
        engine = RepairEngine(MockProvider(), max_iterations=2)
        result = engine.repair(ir, issues)
        self.assertLessEqual(result.iterations, 2)
        self.assertEqual(len(result.remaining_issues), 5)

    def test_repair_respects_max_iterations_parameter(self) -> None:
        engine = RepairEngine(MockProvider(), max_iterations=1)
        ir = _make_ir(app_title=None)
        issues = (
            RepairIssue(path="$/app", category="missing_app_title", message="x"),
            RepairIssue(path="$/x", category="unfixable", message="y"),
        )
        result = engine.repair(ir, issues)
        self.assertLessEqual(result.iterations, 1)

    def test_repair_mixed_known_and_unknown_issues(self) -> None:
        ir = _make_ir(app_title=None)
        issues = (
            RepairIssue(path="$/app", category="missing_app_title", message="x"),
            RepairIssue(path="$/y", category="unknown_thing", message="y"),
        )
        result = self.engine.repair(ir, issues)
        fixed_categories = {i.category for i in result.fixed_issues}
        remaining_categories = {i.category for i in result.remaining_issues}
        self.assertIn("missing_app_title", fixed_categories)
        self.assertIn("unknown_thing", remaining_categories)


if __name__ == "__main__":
    unittest.main()
