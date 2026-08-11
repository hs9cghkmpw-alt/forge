"""forge_ai_adapter.py のテスト(FORGE-MILESTONE-005 Task13、Adapter系)。

`docs/spec/ADAPTER_CONTRACT_V1.md` 2章の各Adapter関数を検証する。
"""

from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))  # forge_ai/ はrepoルート直下

from forge_ai.core.compiler import ForgeIRDocument, ForgeIRScreen, ForgeIRStateValue, ForgeIRWidget  # noqa: E402
from forge_ai.core.intent_model import Intent as ForgeAIIntent  # noqa: E402
from forge_ai.core.planner import ApplicationPlan, ScreenPlan as ForgeAIScreenPlan  # noqa: E402
from forge_ai.repair.repair_engine import RepairIssue as ForgeAIRepairIssue  # noqa: E402
from forge_ai.repair.repair_engine import RepairResult as ForgeAIRepairResult  # noqa: E402
from forge_ai.quality.quality_engine import QualityScore  # noqa: E402

from app.ai.foundation.interfaces import Platform  # noqa: E402
from app.ai.runtime.forge_ai_adapter import (  # noqa: E402
    intent_ir_from_forge_ai_intent,
    plan_ir_from_application_plan,
    to_backend_repair_result,
    to_critic_result,
    to_repair_issues,
)
from app.ai.validators.schema_validator import validate_forge_document  # noqa: E402


class TestIntentAdapter(unittest.TestCase):
    def test_goal_maps_to_purpose(self) -> None:
        intent = ForgeAIIntent(goal="買い物を管理する", required_concepts=(), required_actions=(), constraints=())
        result = intent_ir_from_forge_ai_intent(intent)
        self.assertEqual(result.purpose, "買い物を管理する")

    def test_required_concepts_maps_to_entities(self) -> None:
        intent = ForgeAIIntent(goal="x", required_concepts=("item", "price"), required_actions=(), constraints=())
        result = intent_ir_from_forge_ai_intent(intent)
        self.assertEqual(result.entities, ("item", "price"))

    def test_required_actions_maps_to_required_features(self) -> None:
        """CEO指摘4の回帰テスト: required_actionsが失われずrequired_featuresへ伝わる。"""
        intent = ForgeAIIntent(goal="x", required_concepts=(), required_actions=("add_item", "delete_item"), constraints=())
        result = intent_ir_from_forge_ai_intent(intent)
        self.assertEqual(result.required_features, ("add_item", "delete_item"))

    def test_platform_override_is_respected(self) -> None:
        intent = ForgeAIIntent(goal="x", required_concepts=(), required_actions=(), constraints=())
        result = intent_ir_from_forge_ai_intent(intent, platform=Platform.WEB)
        self.assertEqual(result.platform, Platform.WEB)


class TestPlanAdapter(unittest.TestCase):
    def test_unassigned_actions_preserves_intent_required_actions(self) -> None:
        """CEO指摘4の回帰テスト: actions_needed=()固定で情報を捨てず、
        Plan全体のunassigned_actionsとして保持する。"""
        intent = ForgeAIIntent(goal="x", required_concepts=(), required_actions=("add_item", "submit_form"), constraints=())
        plan = ApplicationPlan(
            title="Test", screens=(ForgeAIScreenPlan(name="main", purpose="p", key_elements=("item",)),),
            data_entities=("item",), primary_flow=(),
        )
        result = plan_ir_from_application_plan(plan, intent)
        self.assertEqual(result.plan_ir.unassigned_actions, ("add_item", "submit_form"))

    def test_presentation_concept_excluded_from_data_needed(self) -> None:
        """CEO指摘5の回帰テスト: '検索欄'のような画面表現概念はdata_neededへ入らない。"""
        intent = ForgeAIIntent(goal="x", required_concepts=(), required_actions=(), constraints=())
        plan = ApplicationPlan(
            title="Test",
            screens=(ForgeAIScreenPlan(name="main", purpose="p", key_elements=("item", "検索欄")),),
            data_entities=("item",), primary_flow=(),
        )
        result = plan_ir_from_application_plan(plan, intent)
        self.assertEqual(result.plan_ir.screens[0].data_needed, ("item",))
        self.assertNotIn("検索欄", result.plan_ir.screens[0].data_needed)

    def test_presentation_concept_exclusion_is_reported_as_warning(self) -> None:
        """CEO実物監査 Fix 2の回帰テスト: 以前は`unclassified_diagnostics`が
        どこにも返されず、presentation conceptの除外が静かに消えていた。
        `PlanConversionResult.warnings`で確認できることを検証する。"""
        intent = ForgeAIIntent(goal="x", required_concepts=(), required_actions=(), constraints=())
        plan = ApplicationPlan(
            title="Test",
            screens=(ForgeAIScreenPlan(name="main", purpose="p", key_elements=("item", "検索欄")),),
            data_entities=("item",), primary_flow=(),
        )
        result = plan_ir_from_application_plan(plan, intent)
        self.assertEqual(len(result.warnings), 1)
        self.assertIn("検索欄", result.warnings[0])
        self.assertIn("main", result.warnings[0])

    def test_no_presentation_concepts_means_no_warnings(self) -> None:
        intent = ForgeAIIntent(goal="x", required_concepts=(), required_actions=(), constraints=())
        plan = ApplicationPlan(
            title="Test", screens=(ForgeAIScreenPlan(name="main", purpose="p", key_elements=("item",)),),
            data_entities=("item",), primary_flow=(),
        )
        result = plan_ir_from_application_plan(plan, intent)
        self.assertEqual(result.warnings, ())

    def test_data_entity_included_in_data_needed(self) -> None:
        intent = ForgeAIIntent(goal="x", required_concepts=(), required_actions=(), constraints=())
        plan = ApplicationPlan(
            title="Test", screens=(ForgeAIScreenPlan(name="main", purpose="p", key_elements=("price", "quantity")),),
            data_entities=(), primary_flow=(),
        )
        result = plan_ir_from_application_plan(plan, intent)
        self.assertEqual(set(result.plan_ir.screens[0].data_needed), {"price", "quantity"})

    def test_empty_and_error_state_needed_default_true(self) -> None:
        intent = ForgeAIIntent(goal="x", required_concepts=(), required_actions=(), constraints=())
        plan = ApplicationPlan(
            title="Test", screens=(ForgeAIScreenPlan(name="main", purpose="p", key_elements=()),),
            data_entities=(), primary_flow=(),
        )
        result = plan_ir_from_application_plan(plan, intent)
        self.assertTrue(result.plan_ir.screens[0].empty_state_needed)
        self.assertTrue(result.plan_ir.screens[0].error_state_needed)

    def test_multiple_screens_each_get_a_screen_id(self) -> None:
        intent = ForgeAIIntent(goal="x", required_concepts=(), required_actions=(), constraints=())
        plan = ApplicationPlan(
            title="Test",
            screens=(
                ForgeAIScreenPlan(name="Main Screen", purpose="p1", key_elements=()),
                ForgeAIScreenPlan(name="Detail Screen", purpose="p2", key_elements=()),
            ),
            data_entities=(), primary_flow=(),
        )
        result = plan_ir_from_application_plan(plan, intent)
        self.assertEqual(len(result.plan_ir.screens), 2)
        self.assertTrue(all(s.screen_id for s in result.plan_ir.screens))


class TestRepairIssueAdapter(unittest.TestCase):
    def test_converts_validator_errors_to_forge_ai_repair_issues(self) -> None:
        invalid_doc = {"version": "9.9", "initial_screen_id": "x", "screens": []}
        validation = validate_forge_document(invalid_doc)
        self.assertFalse(validation.valid)
        issues = to_repair_issues(validation)
        self.assertGreater(len(issues), 0)
        self.assertTrue(all(isinstance(i, ForgeAIRepairIssue) for i in issues))

    def test_valid_document_produces_no_issues(self) -> None:
        valid_doc = {
            "version": "1.0", "initial_screen_id": "s1",
            "screens": [{"id": "s1", "title": "T", "body": {"type": "text", "id": "t1", "value": "hi"}}],
        }
        validation = validate_forge_document(valid_doc)
        self.assertTrue(validation.valid)
        issues = to_repair_issues(validation)
        self.assertEqual(issues, ())

    def test_repair_issue_category_carries_the_real_validator_rule_name(self) -> None:
        """FORGE-AI-QUALITY-001(2026-08-11)回帰テスト: 実バグ修正の確認。
        以前は`category`へ`ValidationIssue.category`(Category enum、
        `"schema"`等4値のみ)を渡していたため、`RepairEngine`が判定に
        使う具体的なルール名(`"string_length"`等)と一度も一致せず、
        Repair Loopが実質的な無効化状態になっていた(TD31参照)。
        `category`に実際のrule名がそのまま入ることを確認する。"""
        invalid_doc = {
            "version": "1.0", "initial_screen_id": "s1",
            "app": {"title": ""},
            "screens": [{"id": "s1", "title": "T", "body": {"type": "text", "id": "t1", "value": "hi"}}],
        }
        validation = validate_forge_document(invalid_doc)
        self.assertFalse(validation.valid)
        issues = to_repair_issues(validation)
        title_issues = [i for i in issues if i.path.endswith("/app/title")]
        self.assertEqual(len(title_issues), 1)
        self.assertEqual(title_issues[0].category, "string_length")
        # 修正前の実装ではここが"schema"になっており、RepairEngineの
        # どの既知パターンとも一致しなかった。
        self.assertNotIn(title_issues[0].category, {"syntax", "schema", "semantic", "runtime_safety"})


class TestRepairResultAdapter(unittest.TestCase):
    def test_converts_forge_ai_repair_result_to_backend_shape(self) -> None:
        screen = ForgeIRScreen(
            id="s1", title="T", state={},
            body=ForgeIRWidget(type="text", id="t1", properties={"value": "hi"}),
        )
        ir = ForgeIRDocument(version="1.0", initial_screen_id="s1", screens=(screen,))
        forge_ai_result = ForgeAIRepairResult(
            ir=ir,
            fixed_issues=(ForgeAIRepairIssue(path="$/x", category="c", message="m"),),
            remaining_issues=(),
            iterations=1,
        )
        result = to_backend_repair_result(forge_ai_result, attempt=1)
        self.assertEqual(result.fixed_issue_count, 1)
        self.assertEqual(result.remaining_issue_count, 0)
        self.assertTrue(result.success)
        self.assertEqual(result.document["version"], "1.0")

    def test_remaining_issues_means_not_success(self) -> None:
        screen = ForgeIRScreen(id="s1", title="T", state={}, body=ForgeIRWidget(type="text", id="t1", properties={"value": "hi"}))
        ir = ForgeIRDocument(version="1.0", initial_screen_id="s1", screens=(screen,))
        forge_ai_result = ForgeAIRepairResult(
            ir=ir, fixed_issues=(), remaining_issues=(ForgeAIRepairIssue(path="$/y", category="c", message="m"),), iterations=1,
        )
        result = to_backend_repair_result(forge_ai_result, attempt=2)
        self.assertFalse(result.success)
        self.assertEqual(result.remaining_issue_count, 1)


class TestQualityAdapter(unittest.TestCase):
    def test_overall_scaled_to_0_100(self) -> None:
        quality = QualityScore(
            correctness=1.0, completeness=1.0, simplicity=1.0,
            runtime_safety=1.0, explainability=1.0, maintainability=1.0,
        )
        result = to_critic_result(quality)
        self.assertEqual(result.score, 100)

    def test_release_ready_true_above_threshold(self) -> None:
        quality = QualityScore(
            correctness=0.9, completeness=0.9, simplicity=0.9,
            runtime_safety=0.9, explainability=0.9, maintainability=0.9,
        )
        result = to_critic_result(quality, threshold=0.8)
        self.assertTrue(result.release_ready)

    def test_release_ready_false_below_threshold(self) -> None:
        quality = QualityScore(
            correctness=0.5, completeness=0.5, simplicity=0.5,
            runtime_safety=0.5, explainability=0.5, maintainability=0.5,
        )
        result = to_critic_result(quality, threshold=0.8)
        self.assertFalse(result.release_ready)


if __name__ == "__main__":
    unittest.main()
