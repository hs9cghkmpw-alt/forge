"""Template Selector・Application Planner・Design Critic・Revision Engine・
Escalation Handler のテスト(FORGE-MILESTONE-007第一段階)。"""

from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from forge_ai.core.confirmation.escalation_handler import EscalationHandler  # noqa: E402
from forge_ai.core.critic.design_critic import DesignCritic  # noqa: E402
from forge_ai.core.critic.revision_engine import RevisionEngine  # noqa: E402
from forge_ai.core.domain_model import DomainCategory, DomainRegistry  # noqa: E402
from forge_ai.core.intent_model import Intent  # noqa: E402
from forge_ai.core.orchestration.cognitive_context import CognitiveContext  # noqa: E402
from forge_ai.core.orchestration.cognitive_types import (  # noqa: E402
    CriticIssue,
    CriticReport,
    DomainCandidate,
    DomainClassification,
    RequirementSet,
)
from forge_ai.core.planner import ApplicationPlan, ScreenPlan  # noqa: E402
from forge_ai.core.planning.application_planner import CognitiveApplicationPlanner  # noqa: E402
from forge_ai.core.planning.template_selector import TemplateSelector  # noqa: E402
from forge_ai.core.understanding.domain_classifier import CognitiveDomainClassifier  # noqa: E402
from forge_ai.core.understanding.requirement_extractor import RequirementExtractor  # noqa: E402
from forge_ai.core.understanding.world_builder import CognitiveWorldBuilder  # noqa: E402


class TestTemplateSelector(unittest.TestCase):
    def setUp(self) -> None:
        self.selector = TemplateSelector()
        self.registry = DomainRegistry()

    def test_preliminary_shopping_includes_checklist(self) -> None:
        domain = self.registry.get(__import__(
            "forge_ai.core.domain_model", fromlist=["DomainCategory"]
        ).DomainCategory.SHOPPING)
        intent = Intent(goal="x", required_concepts=("item",), required_actions=(), constraints=())
        candidates = self.selector.select_preliminary(domain, intent, RequirementSet())
        self.assertIn("checklist", candidates)

    def test_final_selection_for_calendar_like_actions(self) -> None:
        plan = ApplicationPlan(
            title="x", screens=(ScreenPlan(name="main", purpose="x", key_elements=("event",)),),
            data_entities=("event", "time"), primary_flow=("add_event", "set_reminder"),
        )
        result = self.selector.select_final(plan)
        self.assertEqual(result.template, "calendar")

    def test_final_selection_for_checklist_like_actions(self) -> None:
        plan = ApplicationPlan(
            title="x", screens=(ScreenPlan(name="main", purpose="x", key_elements=("item",)),),
            data_entities=("item",), primary_flow=("add_item", "remove_item"),
        )
        result = self.selector.select_final(plan)
        self.assertEqual(result.template, "checklist")

    def test_final_selection_always_returns_a_valid_template(self) -> None:
        """何もヒットしない場合でもcrashせず、必ず何らかのTemplateを返す。"""
        plan = ApplicationPlan(title="x", screens=(), data_entities=(), primary_flow=())
        result = self.selector.select_final(plan)
        self.assertIsInstance(result.template, str)
        self.assertTrue(result.template)

    def test_shopping_tie_is_resolved_by_preliminary_candidates_not_registration_order(self) -> None:
        """CEO実物監査(Phase 1.1)指摘3の回帰テスト:「買い物リストを
        作りたい」相当の入力(add_item/remove_item/mark_purchased/
        set_budget)は、checklistとtrackerが同点(4.0)になる。これが
        辞書登録順ではなく、Preliminary候補('checklist'が含まれる)に
        よる明示的なtie-breakでchecklistへ決まることを検証する。"""
        plan = ApplicationPlan(
            title="買い物リストを作りたい",
            screens=(ScreenPlan(name="main", purpose="x", key_elements=("item", "price", "quantity", "store")),),
            data_entities=("item", "price", "quantity", "store"),
            primary_flow=("add_item", "remove_item", "mark_purchased", "set_budget"),
        )
        # 実際に同点になることを先に確認する(前提条件チェック)。
        result_no_preliminary = self.selector.select_final(plan, preliminary_candidates=())
        scores = dict(result_no_preliminary.score_by_template)
        self.assertEqual(scores["checklist"], scores["tracker"], "この前提が崩れている場合、テストの意味が変わる")

        result = self.selector.select_final(plan, preliminary_candidates=("checklist", "form"))
        self.assertEqual(result.template, "checklist")
        self.assertIn("tie-break", result.rationale)
        self.assertIn("Preliminary候補", result.rationale)

    def test_tie_break_falls_through_to_dominant_action_when_not_in_preliminary(self) -> None:
        """Preliminary候補のいずれにも同点候補が含まれない場合、
        Dominant action一致数(tie-break 2)まで進むことを確認する。"""
        plan = ApplicationPlan(
            title="x",
            screens=(ScreenPlan(name="main", purpose="x", key_elements=("item", "price", "quantity", "store")),),
            data_entities=("item", "price", "quantity", "store"),
            primary_flow=("add_item", "remove_item", "mark_purchased", "set_budget"),
        )
        # 同点(checklist=4.0, tracker=4.0)になることを前提とする(前段のテストと同じ入力)。
        # Preliminary候補にchecklist・trackerのどちらも含めない。
        result = self.selector.select_final(plan, preliminary_candidates=("wizard",))
        self.assertIn("Dominant action", result.rationale)

    def test_backward_compatible_call_without_preliminary_candidates_still_works(self) -> None:
        """既存の呼び出し方(preliminary_candidates省略)が壊れていないことを確認する。"""
        plan = ApplicationPlan(
            title="x", screens=(ScreenPlan(name="main", purpose="x", key_elements=("item",)),),
            data_entities=("item",), primary_flow=("add_item",),
        )
        result = self.selector.select_final(plan)
        self.assertEqual(result.template, "checklist")

    def test_all_domain_category_values_are_registered_in_preliminary_table(self) -> None:
        """CEO報告(household_budget欠落によるpreliminary_final_mismatch_
        exhausted)を受けた監査の回帰テスト。`DomainCategory`が取りうる
        全ての`.value`が、`_DOMAIN_TO_PRELIMINARY`(`.get()`の
        フォールバック経由ではなく、明示的なキーとして)に登録されて
        いることを確認する。1件でも欠落があれば、そのDomainは常に
        `("generic",)`へフォールバックし、`select_final()`が別の
        Templateを選ぶたびに`differs_from_preliminary=True`が発生し
        続け、`preliminary_final_mismatch_exhausted`で確認要求に
        落ちるリスクを持つ(今回発見された実際の不具合と同種)。

        **2026-07-21追記(CEO指示「辞書の手動管理に依存しない検出の
        仕組み」対応)**: この判定ロジック自体は
        `template_selector._missing_domain_preliminary_entries()`
        (単一のSource of Truth)を呼ぶだけにし、この行のテストと
        モジュール読み込み時の自己検証(`template_selector.py`側)が
        別々に同じロジックを重複して持たないようにした。このテストは
        「テストとして明示的に落ちて分かりやすい失敗理由を示す」層、
        モジュール側の検証は「テストの実行有無に関わらず、import
        された瞬間に構造的に防ぐ」層という、2つの独立した安全網の
        役割分担になっている。"""
        from forge_ai.core.planning.template_selector import _missing_domain_preliminary_entries

        missing = _missing_domain_preliminary_entries()
        self.assertEqual(
            missing, frozenset(),
            f"_DOMAIN_TO_PRELIMINARYに未登録のDomainCategoryがあります: {sorted(missing)}",
        )

    def test_module_import_itself_fails_fast_if_a_domain_is_unregistered(self) -> None:
        """`template_selector.py`が、モジュール読み込み時点で同じ完全性
        検証を行い、欠落があれば即座に失敗する設計になっていることを
        確認する(「テストを書いたが実行し忘れる」という失敗モードを、
        import時点の構造的な保証で補完しているという設計の裏付け)。"""
        import importlib

        from forge_ai.core.planning import template_selector as selector_module

        # 現在の(欠落が無い)状態で再読み込みしても、問題なく成功すること。
        importlib.reload(selector_module)
        self.assertEqual(selector_module._missing_domain_preliminary_entries(), frozenset())

    def test_raise_if_domain_preliminary_incomplete_raises_runtime_error_with_all_missing_names(self) -> None:
        """CEO指摘の回帰テスト(2026-07-21修正): 完全性チェックの送出
        ロジック(`_raise_if_domain_preliminary_incomplete()`)を直接
        呼び、(1)`RuntimeError`(`AssertionError`ではない)が送出される
        こと、(2)不足しているDomain名が**全て**例外メッセージに含まれる
        ことを確認する。`python -O`実行下でも、`assert`文ではなく
        明示的な`raise`文であるため、この検証は無効化されない
        (`raise`文自体は最適化フラグの対象にならない。手動で
        `python -O`実行下でも同じ結果になることを別途確認済み、
        `FORGE-TEMPLATE-SELECTOR-CI-HARDENING-PATCH1-report.md`参照)。
        """
        from forge_ai.core.planning.template_selector import _raise_if_domain_preliminary_incomplete

        with self.assertRaises(RuntimeError) as ctx:
            _raise_if_domain_preliminary_incomplete(frozenset({"domain_z", "domain_a", "domain_m"}))
        message = str(ctx.exception)
        self.assertIn("domain_a", message)
        self.assertIn("domain_m", message)
        self.assertIn("domain_z", message)

    def test_raise_if_domain_preliminary_incomplete_does_nothing_when_empty(self) -> None:
        """空集合(欠落なし)を渡した場合は何も送出しない(正常系)。"""
        from forge_ai.core.planning.template_selector import _raise_if_domain_preliminary_incomplete

        try:
            _raise_if_domain_preliminary_incomplete(frozenset())
        except Exception as exc:  # noqa: BLE001 — 「何も起きないこと」自体を確認するテストのため
            self.fail(f"欠落が無い場合は何も送出しないはずだが、{type(exc).__name__}が発生した: {exc}")

    def test_current_domain_preliminary_table_has_no_extra_unknown_keys(self) -> None:
        """CEO指摘2.への回答: 余分な未知キー(`DomainCategory`のどの
        `.value`にも一致しないキー)が現状無いことを確認する。この
        チェックはimport時のfail-fastには含めない(タイポ発見用の
        hygieneチェックとして、テストでのみ検査する設計、
        `_extra_domain_preliminary_entries()`のdocstring参照)。"""
        from forge_ai.core.planning.template_selector import _extra_domain_preliminary_entries

        self.assertEqual(_extra_domain_preliminary_entries(), frozenset())

    def test_extra_domain_preliminary_entries_detects_a_simulated_typo(self) -> None:
        """`_extra_domain_preliminary_entries()`が、実際に存在しない
        キー(タイポを模したもの)を正しく検出することを確認する。"""
        from forge_ai.core.planning import template_selector as selector_module

        original = dict(selector_module._DOMAIN_TO_PRELIMINARY)
        try:
            selector_module._DOMAIN_TO_PRELIMINARY["houshold_budget_typo"] = ("form",)
            extra = selector_module._extra_domain_preliminary_entries()
            self.assertIn("houshold_budget_typo", extra)
        finally:
            selector_module._DOMAIN_TO_PRELIMINARY.clear()
            selector_module._DOMAIN_TO_PRELIMINARY.update(original)

    def test_household_budget_preliminary_includes_form(self) -> None:
        """指示書の明示的な検証項目1: select_preliminary()がformを含む。"""
        registry = DomainRegistry()
        domain = registry.get(DomainCategory.HOUSEHOLD_BUDGET)
        intent = Intent(goal="家計簿をつけたい", required_concepts=("transaction",), required_actions=(), constraints=())
        candidates = self.selector.select_preliminary(domain, intent, RequirementSet())
        self.assertIn("form", candidates)

    def test_household_budget_final_selection_does_not_differ_from_preliminary(self) -> None:
        """指示書の明示的な検証項目2: select_final()の結果が、
        household_budgetのpreliminary候補に含まれること
        (differs_from_preliminary=False)。実際にForge AIが
        household_budget向けに生成する典型的なApplicationPlanの形
        (transaction/category/amount/budget_limitエンティティ、
        add_transaction等のaction)を使う。"""
        registry = DomainRegistry()
        domain = registry.get(DomainCategory.HOUSEHOLD_BUDGET)
        intent = Intent(goal="x", required_concepts=("transaction",), required_actions=(), constraints=())
        preliminary = self.selector.select_preliminary(domain, intent, RequirementSet())

        plan = ApplicationPlan(
            title="家計簿",
            screens=(ScreenPlan(name="main", purpose="x", key_elements=("transaction", "amount", "category")),),
            data_entities=("transaction", "category", "amount", "budget_limit"),
            primary_flow=("add_transaction", "set_budget_limit", "view_summary"),
        )
        result = self.selector.select_final(plan, preliminary_candidates=preliminary)
        self.assertIn(result.template, preliminary)
        self.assertFalse(result.differs_from_preliminary)

    def test_household_budget_prompt_reaches_success_not_confirmation(self) -> None:
        """指示書の明示的な検証項目3・4: 「家計簿アプリを作りたい」＋
        詳細説明の入力で、`preliminary_final_mismatch_exhausted`に
        ならず、`CognitivePipelineNeedsConfirmation`ではなく
        `CognitivePipelineSuccess`として正常完了することを、Template
        Selector単体ではなく実際のPipeline全体を通して確認する
        (`test_v03_domain_inference_golden.py`が3件の短いhousehold_
        budgetプロンプトを既にカバーしているが、今回CEOが実際に
        再現した「詳細説明付きの長いプロンプト」に相当するケースを
        追加する)。"""
        from forge_ai.core.orchestration.outcomes import CognitivePipelineNeedsConfirmation, CognitivePipelineSuccess
        from forge_ai.core.pipeline import run_cognitive_pipeline
        from forge_ai.provider.mock_provider import MockProvider

        text = "家計簿アプリを作りたい。毎月の支出をカテゴリ別に記録して、収入と支出を管理したい。"
        outcome = run_cognitive_pipeline(text, provider=MockProvider())

        if isinstance(outcome, CognitivePipelineNeedsConfirmation):
            self.fail(
                f"確認要求になった(reason={outcome.confirmation_request.reason})。"
                "household_budgetがpreliminary_final_mismatch_exhaustedへ落ちる"
                "リグレッションが再発している可能性があります。"
            )
        self.assertIsInstance(outcome, CognitivePipelineSuccess)
        self.assertFalse(outcome.context.template_selection.differs_from_preliminary)


class TestCognitiveApplicationPlanner(unittest.TestCase):
    def setUp(self) -> None:
        self.planner = CognitiveApplicationPlanner()
        self.classifier = CognitiveDomainClassifier()
        self.world_builder = CognitiveWorldBuilder()
        self.req_extractor = RequirementExtractor()
        self.registry = DomainRegistry()

    def _plan_for(self, concepts):
        from forge_ai.core.orchestration.cognitive_types import ExtractedMeaning

        intent = Intent(goal="test goal", required_concepts=concepts, required_actions=(), constraints=())
        classification = self.classifier.classify(intent, self.registry)
        world = self.world_builder.build(classification, intent)
        meaning = ExtractedMeaning(summary=intent.goal)
        requirements = self.req_extractor.extract(meaning, world, intent)
        return self.planner.plan(intent, world, requirements, ("checklist",))

    def test_plan_has_at_least_one_screen(self) -> None:
        plan = self._plan_for(("item",))
        self.assertGreaterEqual(len(plan.screens), 1)

    def test_screen_has_empty_state_message(self) -> None:
        plan = self._plan_for(("item",))
        self.assertTrue(plan.screens[0].empty_state_message)

    def test_screen_has_validation_rules(self) -> None:
        plan = self._plan_for(("item",))
        self.assertGreater(len(plan.screens[0].validation_rules), 0)

    def test_title_reflects_intent_goal(self) -> None:
        plan = self._plan_for(("item",))
        self.assertEqual(plan.title, "test goal")

    def test_functional_requirement_with_missing_action_is_unassigned_and_blocks_critic(self) -> None:
        """CEO実物監査(Phase 1.1、2回目)指摘3の回帰テスト: 必須の
        delete_item(operation_ref)がPlanのrequired_actionsに実在しない
        場合、unassigned_requirementsへ入り、Criticがrelease_readyを
        Falseにする。"""
        from forge_ai.core.orchestration.cognitive_types import CriticReport, Requirement, RequirementSet, TemplateSelection

        intent = Intent(goal="x", required_concepts=("item",), required_actions=(), constraints=())
        classification = self.classifier.classify(intent, self.registry)
        world = self.world_builder.build(classification, intent)
        requirements = RequirementSet(requirements=(
            Requirement(requirement_id="REQ-001", category="functional",
                        description="利用者が'delete_item'(対象: item)を実行できること。",
                        mandatory=True, operation_ref="delete_item"),
        ))
        plan = self.planner.plan(intent, world, requirements, ("checklist",))
        self.assertIn("利用者が'delete_item'(対象: item)を実行できること。", plan.unassigned_requirements)

        from forge_ai.core.critic.design_critic import DesignCritic

        selection = TemplateSelection(template="checklist", score_by_template=(), differs_from_preliminary=False, rationale="x")
        report = DesignCritic().evaluate(plan, selection, requirements)
        self.assertFalse(report.release_ready)

    def test_functional_requirement_with_present_action_is_assigned(self) -> None:
        """operation_refが実際にrequired_actionsに存在する場合は
        割当済みになる。"""
        from forge_ai.core.orchestration.cognitive_types import Requirement, RequirementSet

        intent = Intent(goal="x", required_concepts=("item",), required_actions=("add_item",), constraints=())
        classification = self.classifier.classify(intent, self.registry)
        world = self.world_builder.build(classification, intent)
        requirements = RequirementSet(requirements=(
            Requirement(requirement_id="REQ-001", category="functional",
                        description="利用者が'add_item'(対象: item)を実行できること。",
                        mandatory=True, operation_ref="add_item"),
        ))
        plan = self.planner.plan(intent, world, requirements, ("checklist",))
        self.assertNotIn("利用者が'add_item'(対象: item)を実行できること。", plan.unassigned_requirements)

    def test_data_requirement_with_missing_entity_is_unassigned(self) -> None:
        """CEO実物監査(Phase 1.1、2回目)指摘3の回帰テスト: target_refが
        実際のdata_entitiesに存在しないData要件は未割当のままになる。"""
        from forge_ai.core.orchestration.cognitive_types import Requirement, RequirementSet

        intent = Intent(goal="x", required_concepts=("item",), required_actions=(), constraints=())
        classification = self.classifier.classify(intent, self.registry)
        world = self.world_builder.build(classification, intent)
        requirements = RequirementSet(requirements=(
            Requirement(requirement_id="REQ-001", category="data",
                        description="'nonexistent_entity' のデータを保持できること。",
                        mandatory=True, target_ref="nonexistent_entity"),
        ))
        plan = self.planner.plan(intent, world, requirements, ("checklist",))
        self.assertIn("'nonexistent_entity' のデータを保持できること。", plan.unassigned_requirements)

    def test_description_string_coincidence_alone_does_not_cause_false_assignment(self) -> None:
        """CEO実物監査(Phase 1.1、2回目)指摘3の核心: descriptionの文字列が
        たまたまvalidation_rules等と一致していても、target_ref/
        operation_refが実際に対応していなければ割当済みにしない
        (機械的な参照整合性のみで判定し、文字列の偶然一致で判定しない)。
        """
        from forge_ai.core.orchestration.cognitive_types import Requirement, RequirementSet

        intent = Intent(goal="x", required_concepts=("item",), required_actions=(), constraints=())
        classification = self.classifier.classify(intent, self.registry)
        world = self.world_builder.build(classification, intent)
        # category="data"だがtarget_refを設定しない(=参照を持たない、
        # 判定不能な要件)。descriptionの文字列がitem(実在するentity名)を
        # 含んでいても、target_refが無ければ機械的には判定できないため
        # 未割当のままとする。
        requirements = RequirementSet(requirements=(
            Requirement(requirement_id="REQ-001", category="data",
                        description="'item' に関連する何らかの要件(target_ref未設定)。",
                        mandatory=True, target_ref=None),
        ))
        plan = self.planner.plan(intent, world, requirements, ("checklist",))
        self.assertIn("'item' に関連する何らかの要件(target_ref未設定)。", plan.unassigned_requirements)


class TestDesignCritic(unittest.TestCase):
    def setUp(self) -> None:
        self.critic = DesignCritic()

    def test_complete_plan_is_release_ready(self) -> None:
        plan = ApplicationPlan(
            title="x",
            screens=(ScreenPlan(
                name="main", purpose="x", key_elements=("item",), required_actions=("add_item",),
                empty_state_message="empty", validation_rules=("rule",),
            ),),
            data_entities=("item",), primary_flow=("add_item",),
        )
        from forge_ai.core.orchestration.cognitive_types import TemplateSelection

        selection = TemplateSelection(template="checklist", score_by_template=(), differs_from_preliminary=False, rationale="x")
        report = self.critic.evaluate(plan, selection, RequirementSet())
        self.assertTrue(report.release_ready)

    def test_missing_empty_state_lowers_score_and_reports_issue(self) -> None:
        plan = ApplicationPlan(
            title="x",
            screens=(ScreenPlan(name="main", purpose="x", key_elements=("item",), validation_rules=("rule",)),),
            data_entities=("item",), primary_flow=(),
        )
        from forge_ai.core.orchestration.cognitive_types import TemplateSelection

        selection = TemplateSelection(template="checklist", score_by_template=(), differs_from_preliminary=False, rationale="x")
        report = self.critic.evaluate(plan, selection, RequirementSet())
        self.assertTrue(any(i.category == "empty_state" for i in report.issues))

    def test_unassigned_mandatory_requirement_blocks_release_ready(self) -> None:
        """CEO実物監査(Phase 1.1)指摘5の回帰テスト: 4(現7)評価軸が
        全て満点でも、未割当の必須要件が残っていればrelease_readyに
        しない。"""
        from forge_ai.core.orchestration.cognitive_types import Requirement, TemplateSelection

        plan = ApplicationPlan(
            title="x",
            screens=(ScreenPlan(
                name="main", purpose="x", key_elements=("item",), required_actions=("add_item",),
                empty_state_message="empty", validation_rules=("rule",),
            ),),
            data_entities=("item",), primary_flow=("add_item",),
            unassigned_requirements=("未割当の重要な要件",),
        )
        requirements = RequirementSet(requirements=(
            Requirement(requirement_id="REQ-001", category="functional", description="未割当の重要な要件", mandatory=True),
        ))
        selection = TemplateSelection(template="checklist", score_by_template=(), differs_from_preliminary=False, rationale="x")
        report = self.critic.evaluate(plan, selection, requirements)
        self.assertFalse(report.release_ready)
        self.assertTrue(any(i.category == "unassigned_mandatory_requirement" for i in report.issues))

    def test_unassigned_non_mandatory_requirement_does_not_block_release_ready(self) -> None:
        """mandatory=Falseの要件(例: Accessibility)が未割当でも、
        それだけではrelease_readyをFalseにしない(他の全評価軸が
        満点の場合)。CEO実物監査(Phase 1.1、2回目)指摘4: これは
        Accessibilityがmandatory=Falseの場合の既定挙動である。"""
        from forge_ai.core.orchestration.cognitive_types import Requirement, TemplateSelection

        plan = ApplicationPlan(
            title="x",
            screens=(ScreenPlan(
                name="main", purpose="x", key_elements=("item",), required_actions=("add_item",),
                empty_state_message="empty", validation_rules=("rule",),
            ),),
            data_entities=("item",), primary_flow=("add_item",),
            unassigned_requirements=("キーボード操作の要件",),
        )
        requirements = RequirementSet(requirements=(
            Requirement(requirement_id="REQ-001", category="accessibility", description="キーボード操作の要件", mandatory=False),
        ))
        selection = TemplateSelection(template="checklist", score_by_template=(), differs_from_preliminary=False, rationale="x")
        report = self.critic.evaluate(plan, selection, requirements)
        self.assertTrue(report.release_ready)
        self.assertTrue(any(i.category == "accessibility" and i.severity == "medium" for i in report.issues))

    def test_mandatory_accessibility_unassigned_is_high_and_blocking(self) -> None:
        """CEO実物監査(Phase 1.1、2回目)指摘4への対応: Accessibility要件が
        mandatory=Trueの場合は、Privacyと同様にhigh/blockingとして扱う
        (第一段階の既定実装では発生しないが、将来Accessibility要件が
        mandatory=Trueで生成される場合に備えた回帰テスト)。"""
        from forge_ai.core.orchestration.cognitive_types import Requirement, TemplateSelection

        plan = ApplicationPlan(
            title="x",
            screens=(ScreenPlan(
                name="main", purpose="x", key_elements=("item",), required_actions=("add_item",),
                empty_state_message="empty", validation_rules=("rule",),
            ),),
            data_entities=("item",), primary_flow=("add_item",),
            unassigned_requirements=("必須のキーボード操作要件",),
        )
        requirements = RequirementSet(requirements=(
            Requirement(requirement_id="REQ-001", category="accessibility", description="必須のキーボード操作要件", mandatory=True),
        ))
        selection = TemplateSelection(template="checklist", score_by_template=(), differs_from_preliminary=False, rationale="x")
        report = self.critic.evaluate(plan, selection, requirements)
        self.assertFalse(report.release_ready)
        self.assertTrue(any(i.category == "accessibility" and i.severity == "high" for i in report.issues))

    def test_unassigned_privacy_requirement_is_blocking(self) -> None:
        """CEO実物監査(Phase 1.1)指摘5: Privacy要件が未割当の場合、
        blocking issueとして扱いrelease_readyにしない。"""
        from forge_ai.core.orchestration.cognitive_types import Requirement, TemplateSelection

        plan = ApplicationPlan(
            title="x",
            screens=(ScreenPlan(
                name="main", purpose="x", key_elements=("item",), required_actions=("add_item",),
                empty_state_message="empty", validation_rules=("rule",),
            ),),
            data_entities=("item",), primary_flow=("add_item",),
            unassigned_requirements=("記録範囲の確認",),
        )
        requirements = RequirementSet(requirements=(
            Requirement(requirement_id="REQ-001", category="privacy", description="記録範囲の確認", mandatory=True),
        ))
        selection = TemplateSelection(template="checklist", score_by_template=(), differs_from_preliminary=False, rationale="x")
        report = self.critic.evaluate(plan, selection, requirements)
        self.assertFalse(report.release_ready)
        self.assertTrue(any(i.category == "privacy" and i.severity == "high" for i in report.issues))

    def test_single_screen_does_not_need_navigation(self) -> None:
        """画面が1つだけの場合、navigation_edgesが空でもnavigation_coherence
        は満点(遷移が不要なだけであり、設計欠落ではない)。"""
        from forge_ai.core.orchestration.cognitive_types import TemplateSelection

        plan = ApplicationPlan(
            title="x",
            screens=(ScreenPlan(
                name="main", purpose="x", key_elements=("item",), required_actions=("add_item",),
                empty_state_message="empty", validation_rules=("rule",),
            ),),
            data_entities=("item",), primary_flow=("add_item",), navigation_edges=(),
        )
        selection = TemplateSelection(template="checklist", score_by_template=(), differs_from_preliminary=False, rationale="x")
        report = self.critic.evaluate(plan, selection, RequirementSet())
        self.assertFalse(any(i.category == "navigation_coherence" for i in report.issues))

    def test_multiple_screens_without_navigation_edges_is_flagged(self) -> None:
        """複数画面なのにnavigation_edgesが空の場合、遷移設計の欠落として
        指摘される(単一画面で不要な場合と区別する)。"""
        from forge_ai.core.orchestration.cognitive_types import TemplateSelection

        plan = ApplicationPlan(
            title="x",
            screens=(
                ScreenPlan(name="list", purpose="x", key_elements=("item",), empty_state_message="e", validation_rules=("r",)),
                ScreenPlan(name="detail", purpose="y", key_elements=("item",), empty_state_message="e", validation_rules=("r",)),
            ),
            data_entities=("item",), primary_flow=("add_item",), navigation_edges=(),
        )
        selection = TemplateSelection(template="detail_list", score_by_template=(), differs_from_preliminary=False, rationale="x")
        report = self.critic.evaluate(plan, selection, RequirementSet())
        self.assertTrue(any(i.category == "navigation_coherence" for i in report.issues))
        self.assertFalse(report.release_ready)

    def test_report_tracks_evaluated_and_unevaluated_axes(self) -> None:
        """CEO実物監査(Phase 1.1)指摘5: 「評価済み軸」「未評価軸」を
        CriticReportが保持する。"""
        plan = ApplicationPlan(
            title="x",
            screens=(ScreenPlan(
                name="main", purpose="x", key_elements=("item",), required_actions=("add_item",),
                empty_state_message="empty", validation_rules=("rule",),
            ),),
            data_entities=("item",), primary_flow=("add_item",),
        )
        from forge_ai.core.orchestration.cognitive_types import TemplateSelection

        selection = TemplateSelection(template="checklist", score_by_template=(), differs_from_preliminary=False, rationale="x")
        report = self.critic.evaluate(plan, selection, RequirementSet())
        self.assertGreater(len(report.evaluated_axes), 0)
        self.assertGreater(len(report.unevaluated_axes), 0)
        self.assertAlmostEqual(
            report.coverage_ratio,
            len(report.evaluated_axes) / (len(report.evaluated_axes) + len(report.unevaluated_axes)),
        )
        # score(後方互換)とimplemented_checks_scoreが同じ値であること。
        self.assertEqual(report.score, report.implemented_checks_score)


class TestRevisionEngine(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = RevisionEngine()

    def test_fixes_missing_empty_state(self) -> None:
        plan = ApplicationPlan(
            title="x", screens=(ScreenPlan(name="main", purpose="x", key_elements=("item",)),),
            data_entities=("item",), primary_flow=(),
        )
        report = CriticReport(release_ready=False, score=0.4, issues=(
            CriticIssue(category="empty_state", severity="medium", evidence="x", recommended_fix="x",
                        affected_component="application_plan", auto_fixable=True),
        ))
        revised = self.engine.revise(plan, report, attempt=0)
        self.assertTrue(revised.screens[0].empty_state_message)

    def test_non_auto_fixable_issue_leaves_plan_unchanged(self) -> None:
        """直せると偽らない: auto_fixable=Falseの指摘は、Planを変更しない。"""
        plan = ApplicationPlan(
            title="x", screens=(ScreenPlan(name="main", purpose="x", key_elements=()),),
            data_entities=(), primary_flow=(),
        )
        report = CriticReport(release_ready=False, score=0.3, issues=(
            CriticIssue(category="completeness", severity="high", evidence="x", recommended_fix="x",
                        affected_component="application_plan", auto_fixable=False),
        ))
        revised = self.engine.revise(plan, report, attempt=0)
        self.assertEqual(revised, plan)


class TestEscalationHandler(unittest.TestCase):
    def setUp(self) -> None:
        self.handler = EscalationHandler()

    def test_known_reason_produces_specific_message(self) -> None:
        context = CognitiveContext(raw_input="x", started_at="2026-01-01T00:00:00")
        request = self.handler.build_confirmation_request(context, reason="priority1_privacy_safety_permission")
        self.assertIn("プライバシー", request.message)

    def test_unknown_reason_produces_default_message(self) -> None:
        context = CognitiveContext(raw_input="x", started_at="2026-01-01T00:00:00")
        request = self.handler.build_confirmation_request(context, reason="some_future_reason")
        self.assertTrue(request.message)

    # --- FORGE_v0.2_最終調整 P2: revision_exhausted質問品質の回帰テスト ---

    def test_revision_exhausted_does_not_expose_internal_jargon(self) -> None:
        """「品質基準を満たせませんでした」のような内部事情を見せない
        ことを確認する(旧文言の完全な削除)。"""
        critic_report = CriticReport(
            release_ready=False, score=0.5,
            issues=(
                CriticIssue(
                    category="unassigned_mandatory_requirement", severity="high",
                    evidence="未割当の必須要件が1件残っています: ['共有・複数利用者(家族)に対するアクセス権限を管理できること']",
                    recommended_fix="必須要件を画面へ割り当てる", affected_component="application_plan",
                ),
            ),
        )
        context = CognitiveContext(
            raw_input="x", started_at="2026-01-01T00:00:00", critic_report=critic_report,
        )
        request = self.handler.build_confirmation_request(context, reason="revision_exhausted")
        self.assertNotIn("品質基準", request.message)
        self.assertNotIn("revision", request.message.lower())
        self.assertNotIn("critic", request.message.lower())

    def test_revision_exhausted_quotes_the_actual_missing_requirement(self) -> None:
        """`unassigned_mandatory_requirement`のevidenceから、実際の
        要件説明文を抽出して質問へ含めることを確認する(架空の質問を
        作らず、実際に検出された内容に基づく)。"""
        critic_report = CriticReport(
            release_ready=False, score=0.5,
            issues=(
                CriticIssue(
                    category="unassigned_mandatory_requirement", severity="high",
                    evidence="未割当の必須要件が1件残っています: ['共有・複数利用者(家族)に対するアクセス権限を管理できること']",
                    recommended_fix="必須要件を画面へ割り当てる", affected_component="application_plan",
                ),
            ),
        )
        context = CognitiveContext(
            raw_input="x", started_at="2026-01-01T00:00:00", critic_report=critic_report,
        )
        request = self.handler.build_confirmation_request(context, reason="revision_exhausted")
        self.assertIn("共有・複数利用者(家族)に対するアクセス権限を管理できること", request.message)

    def test_revision_exhausted_falls_back_when_no_critic_report(self) -> None:
        """critic_reportが無い場合、目的・対象・管理内容を尋ねる既定文言
        (指示書の例に沿う)へ安全にフォールバックする。"""
        context = CognitiveContext(raw_input="x", started_at="2026-01-01T00:00:00", critic_report=None)
        request = self.handler.build_confirmation_request(context, reason="revision_exhausted")
        self.assertIn("目的", request.message)

    def test_revision_exhausted_falls_back_when_no_issues(self) -> None:
        context = CognitiveContext(
            raw_input="x", started_at="2026-01-01T00:00:00",
            critic_report=CriticReport(release_ready=False, score=0.5, issues=()),
        )
        request = self.handler.build_confirmation_request(context, reason="revision_exhausted")
        self.assertIn("目的", request.message)

    def test_revision_exhausted_prioritizes_mandatory_requirement_over_accessibility(self) -> None:
        """複数カテゴリのissueが同時にある場合、より具体的で優先度の
        高いもの(unassigned_mandatory_requirement)を先に質問する。"""
        critic_report = CriticReport(
            release_ready=False, score=0.5,
            issues=(
                CriticIssue(
                    category="accessibility", severity="medium",
                    evidence="未割当のAccessibility要件が1件残っています(mandatory=False)。",
                    recommended_fix="...", affected_component="application_plan",
                ),
                CriticIssue(
                    category="unassigned_mandatory_requirement", severity="high",
                    evidence="未割当の必須要件が1件残っています: ['在庫の閾値を管理できること']",
                    recommended_fix="...", affected_component="application_plan",
                ),
            ),
        )
        context = CognitiveContext(
            raw_input="x", started_at="2026-01-01T00:00:00", critic_report=critic_report,
        )
        request = self.handler.build_confirmation_request(context, reason="revision_exhausted")
        self.assertIn("在庫の閾値を管理できること", request.message)

    def test_extract_requirement_descriptions_handles_malformed_evidence_safely(self) -> None:
        """既知の形式に一致しないevidence文字列でもクラッシュせず、
        空タプルへ安全にフォールバックする。"""
        from forge_ai.core.confirmation.escalation_handler import _extract_requirement_descriptions

        self.assertEqual(_extract_requirement_descriptions("形式に一致しない文字列"), ())
        self.assertEqual(_extract_requirement_descriptions(""), ())

    # --- FORGE v0.3 Task4: Domain固有のsub-type質問の回帰テスト ---

    def _domain_classification_for(self, category: DomainCategory, *, confidence: float = 0.6):
        registry = DomainRegistry()
        domain = registry.get(category)
        return DomainClassification(
            primary_domain=domain,
            candidates=(
                DomainCandidate(
                    domain=domain, raw_score=2.0, normalized_score=confidence,
                    matched_concepts=("x",), matched_actions=(),
                ),
            ),
            confidence=confidence,
            score_margin=0.15,
            rationale="test",
        )

    def test_household_budget_gets_personal_vs_family_question(self) -> None:
        context = CognitiveContext(
            raw_input="家計簿をつけたい", started_at="2026-01-01T00:00:00",
            domain_classification=self._domain_classification_for(DomainCategory.HOUSEHOLD_BUDGET),
        )
        request = self.handler.build_confirmation_request(context, reason="priority2_low_domain_confidence")
        self.assertIn("個人用", request.message)
        self.assertIn("家族", request.message)

    def test_fishing_log_gets_saltwater_vs_freshwater_question(self) -> None:
        context = CognitiveContext(
            raw_input="釣果を記録したい", started_at="2026-01-01T00:00:00",
            domain_classification=self._domain_classification_for(DomainCategory.FISHING_LOG),
        )
        request = self.handler.build_confirmation_request(context, reason="priority2_low_domain_confidence")
        self.assertIn("海釣り", request.message)
        self.assertIn("淡水", request.message)

    def test_domain_without_subtype_question_falls_back_to_candidate_listing(self) -> None:
        """sub-type質問を持たないDomain(例: Shopping)では、既存の
        「候補を列挙する」動作(回帰)を維持する。"""
        registry = DomainRegistry()
        shopping = registry.get(DomainCategory.SHOPPING)
        task_mgmt = registry.get(DomainCategory.TASK_MANAGEMENT)
        dc = DomainClassification(
            primary_domain=shopping,
            candidates=(
                DomainCandidate(domain=shopping, raw_score=1.0, normalized_score=0.5,
                                 matched_concepts=("item",), matched_actions=()),
                DomainCandidate(domain=task_mgmt, raw_score=1.0, normalized_score=0.5,
                                 matched_concepts=("task",), matched_actions=()),
            ),
            confidence=0.5, score_margin=0.0, rationale="test",
        )
        context = CognitiveContext(
            raw_input="x", started_at="2026-01-01T00:00:00", domain_classification=dc,
        )
        request = self.handler.build_confirmation_request(context, reason="priority2_low_domain_confidence")
        self.assertIn("Shopping", request.message)
        self.assertIn("Task Management", request.message)
        # sub-type質問固有の文言(例: household_budget用)が紛れ込んでいないこと。
        self.assertNotIn("個人用", request.message)


if __name__ == "__main__":
    unittest.main()
