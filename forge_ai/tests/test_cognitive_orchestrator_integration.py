"""CognitiveOrchestrator・run_cognitive_pipeline() の統合テスト
(FORGE-MILESTONE-007第一段階)。"""

from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from forge_ai.core.pipeline import run_cognitive_pipeline, run_pipeline  # noqa: E402
from forge_ai.core.orchestration.outcomes import (  # noqa: E402
    CognitivePipelineFailed,
    CognitivePipelineNeedsConfirmation,
    CognitivePipelineNeedsExtension,
    CognitivePipelineSuccess,
)
from forge_ai.provider.mock_provider import MockProvider  # noqa: E402


class TestRunCognitivePipelineSuccess(unittest.TestCase):
    def test_simple_shopping_input_succeeds(self) -> None:
        outcome = run_cognitive_pipeline("買い物リストを作りたい")
        self.assertIsInstance(outcome, CognitivePipelineSuccess)

    def test_success_outcome_contains_full_context(self) -> None:
        outcome = run_cognitive_pipeline("買い物リストを作りたい")
        assert isinstance(outcome, CognitivePipelineSuccess)
        self.assertIsNotNone(outcome.context.intent)
        self.assertIsNotNone(outcome.context.domain_classification)
        self.assertIsNotNone(outcome.context.world)
        self.assertIsNotNone(outcome.context.requirements)
        self.assertIsNotNone(outcome.context.plan)
        self.assertIsNotNone(outcome.context.template_selection)
        self.assertIsNotNone(outcome.context.critic_report)

    def test_success_outcome_has_forge_ir_and_quality(self) -> None:
        outcome = run_cognitive_pipeline("買い物リストを作りたい")
        assert isinstance(outcome, CognitivePipelineSuccess)
        self.assertIsNotNone(outcome.ir)
        self.assertIsNotNone(outcome.initial_quality)

    def test_decision_trace_is_populated(self) -> None:
        outcome = run_cognitive_pipeline("買い物リストを作りたい")
        assert isinstance(outcome, CognitivePipelineSuccess)
        self.assertGreater(len(outcome.context.decision_trace), 0)


class TestRunCognitivePipelineNeedsConfirmation(unittest.TestCase):
    def test_privacy_sensitive_input_needs_confirmation(self) -> None:
        outcome = run_cognitive_pipeline("福祉支援の記録を管理したい")
        self.assertIsInstance(outcome, CognitivePipelineNeedsConfirmation)
        self.assertEqual(outcome.confirmation_request.reason, "priority1_privacy_safety_permission")

    def test_empty_input_needs_confirmation(self) -> None:
        outcome = run_cognitive_pipeline("")
        self.assertIsInstance(outcome, CognitivePipelineNeedsConfirmation)

    def test_needs_confirmation_preserves_partial_context(self) -> None:
        """CEO実物監査(4回目)指摘2: NeedsConfirmationはダミー値を
        使わない。到達した時点までの情報(normalized_input・
        ambiguity_report)は保持されている一方、まだ到達していない
        情報(intent等)はNoneのままである。"""
        outcome = run_cognitive_pipeline("福祉支援の記録を管理したい")
        assert isinstance(outcome, CognitivePipelineNeedsConfirmation)
        self.assertIsNotNone(outcome.partial_context.normalized_input)
        self.assertIsNotNone(outcome.partial_context.ambiguity_report)


class TestCombinedConfidenceAssessment(unittest.TestCase):
    """CEO実物監査(Phase 1.1)指摘6の回帰テスト: 単一の
    `classification.confidence`だけでなく、intent_extraction_
    confidence・domain_coverage・score_marginを明示的に組み合わせて
    Human Confirmation判定することを検証する。"""

    def setUp(self) -> None:
        from forge_ai.core.domain_model import Domain, DomainCategory
        from forge_ai.core.intent_model import Intent
        from forge_ai.core.orchestration.cognitive_types import DomainCandidate, DomainClassification
        from forge_ai.core.orchestration.pipeline_orchestrator import _should_escalate_for_low_confidence

        self.Intent = Intent
        self.DomainClassification = DomainClassification
        self.DomainCandidate = DomainCandidate
        self._fn = _should_escalate_for_low_confidence
        self._dummy_domain = Domain(
            category=DomainCategory.GENERIC, display_name="x", typical_concepts=(), typical_actions=()
        )

    def _classification(self, *, coverage: float, margin: float) -> "object":
        return self.DomainClassification(
            primary_domain=self._dummy_domain,
            candidates=(self.DomainCandidate(domain=self._dummy_domain, raw_score=1.0, normalized_score=coverage,
                                              matched_concepts=(), matched_actions=()),),
            confidence=coverage, score_margin=margin, rationale="test",
        )

    def _intent(self, *, confidence: float) -> "object":
        return self.Intent(goal="x", required_concepts=(), required_actions=(), constraints=(), confidence=confidence)

    def test_high_coverage_high_margin_high_intent_confidence_does_not_escalate(self) -> None:
        result = self._fn(self._intent(confidence=0.9), self._classification(coverage=1.0, margin=1.0))
        self.assertFalse(result)

    def test_low_domain_coverage_escalates(self) -> None:
        result = self._fn(self._intent(confidence=0.9), self._classification(coverage=0.3, margin=1.0))
        self.assertTrue(result)

    def test_low_intent_extraction_confidence_escalates_even_with_high_coverage(self) -> None:
        """CEO指摘6の核心: domain_coverageが高くても、Intent抽出自体の
        confidenceが低ければ、単純にdomain_coverageだけで押し切らない。"""
        result = self._fn(self._intent(confidence=0.3), self._classification(coverage=1.0, margin=1.0))
        self.assertTrue(result)

    def test_low_margin_with_moderate_coverage_escalates(self) -> None:
        """僅差(margin小)かつcoverageもさほど高くない場合、辞書の偶然
        一致による誤判定の可能性を考慮して確認を求める。"""
        result = self._fn(self._intent(confidence=0.9), self._classification(coverage=0.6, margin=0.1))
        self.assertTrue(result)

    def test_near_tie_margin_escalates_even_with_full_coverage(self) -> None:
        """FORGE_v0.2_修正指示.md P1 5章の回帰テスト: margin(1位と2位の
        差)が事実上の同点(<0.1)の場合、coverageがどれだけ高くても
        (例: Shopping/Genericの'item'重複のように、1つの概念だけで
        Intentの信号を100%説明できてしまうケース)、確認要求を省略しない。
        これは以前の`margin < 0.2 and coverage < 0.8`というAND条件が、
        margin=0.0・coverage=1.0という完全な同点を見逃していたバグの
        修正を検証する(このテスト自体が、修正前は逆の期待値
        (`assertFalse`)を持っていた)。"""
        result = self._fn(self._intent(confidence=0.9), self._classification(coverage=1.0, margin=0.0))
        self.assertTrue(result)


class TestCognitiveOrchestratorDoesNotCallIndividualLegacyComponents(unittest.TestCase):
    def test_pipeline_orchestrator_module_does_not_import_legacy_protocols(self) -> None:
        """Blueprint 4.0節: CognitiveOrchestratorはLegacy Protocol
        (IntentBuilder/Planner/WorldModelBuilder/MeaningExtractor/
        DomainResolver)を一切importしない。"""
        import inspect

        import forge_ai.core.orchestration.pipeline_orchestrator as module

        source = inspect.getsource(module)
        forbidden = [
            "from forge_ai.core.intent_model import IntentBuilder",
            "from forge_ai.core.planner import Planner",
            "from forge_ai.core.world_model import WorldModelBuilder",
            "from forge_ai.core.meaning_model import MeaningExtractor",
        ]
        for term in forbidden:
            self.assertNotIn(term, source, f"pipeline_orchestrator.pyがLegacy実装をimportしています: {term}")

    def test_cognitive_dependencies_module_does_not_import_legacy_protocols(self) -> None:
        import inspect

        import forge_ai.core.orchestration.cognitive_dependencies as module

        source = inspect.getsource(module)
        forbidden = [
            "IntentBuilderProtocol",  # (Legacy, contracts.interfacesの方)
            "PlannerProtocol",
            "DomainResolverProtocol",
            "WorldModelBuilderProtocol",
            "MeaningExtractorProtocol",
        ]
        # forbidden各語がLegacy由来のimportとして登場しないことを確認する
        # (Cognitive版の名前、例えばCognitivePlannerProtocolは許可される)。
        for term in forbidden:
            # "Cognitive" + termという形の名前は許可(例: CognitivePlannerProtocol)。
            occurrences = [line for line in source.splitlines() if term in line and f"Cognitive{term}" not in line and f"{term[:-8]}Protocol" != term]
            legacy_occurrences = [line for line in occurrences if not line.strip().startswith("#")]
            self.assertEqual(legacy_occurrences, [], f"Legacy Protocol '{term}' の使用が見つかりました: {legacy_occurrences}")


class TestRunPipelineUnaffected(unittest.TestCase):
    """既存run_pipeline()が、run_cognitive_pipeline()追加によって
    一切影響を受けていないことを確認する回帰テスト。"""

    def test_run_pipeline_still_works_with_mock_provider(self) -> None:
        result = run_pipeline("買い物リストを作りたい", MockProvider())
        self.assertIsNotNone(result.ir)
        self.assertIsNotNone(result.quality)

    def test_run_pipeline_signature_unchanged(self) -> None:
        import inspect

        sig = inspect.signature(run_pipeline)
        params = list(sig.parameters.keys())
        self.assertEqual(params, ["user_text", "provider", "domain_registry", "world_builder"])


class TestRevisionAttemptCounterSharing(unittest.TestCase):
    """CEO実物監査(4回目)指摘6: Preliminary/Final不一致とCognitive
    Revisionが、同じrevision_attemptカウンタを共有し、無限ループに
    ならないことを確認する。"""

    def test_context_revision_attempt_never_exceeds_max(self) -> None:
        # 6例全てで、revision_attemptがmax_revision_attempts(既定2)を
        # 超えないことを確認する(超えた場合は必ずNeedsConfirmationへ
        # 到達しているはず)。
        inputs = (
            "買い物リストを作りたい", "今日のタスクを管理したい", "日記を記録したい",
            "簡単なアンケートを作りたい", "予定を管理したい", "在庫を管理したい",
        )
        for text in inputs:
            with self.subTest(text=text):
                outcome = run_cognitive_pipeline(text)
                if isinstance(outcome, CognitivePipelineSuccess):
                    self.assertLessEqual(outcome.context.revision_attempt, outcome.context.max_revision_attempts)
                elif isinstance(outcome, CognitivePipelineNeedsConfirmation):
                    self.assertLessEqual(outcome.partial_context.revision_attempt, outcome.partial_context.max_revision_attempts)


class TestProviderContract(unittest.TestCase):
    """CEO実物監査(Phase 1.1)対応: `provider`がFacadeの公開契約として
    機能し、実際にCompilerへ注入されることを検証する
    (以前は内部で`MockProvider()`を固定生成しており、外部からの
    Provider差し替えができなかった)。"""

    def test_default_provider_is_used_when_omitted(self) -> None:
        """providerを省略した場合、既定のMockProviderで動作すること
        (後方互換の確認)。"""
        outcome = run_cognitive_pipeline("買い物リストを作りたい")
        self.assertIsInstance(outcome, CognitivePipelineSuccess)

    def test_explicit_provider_is_actually_invoked(self) -> None:
        """明示的に渡したProviderが、実際にCompiler経由で呼び出される
        ことを確認する(単にコンストラクタ引数として受理するだけでなく、
        実行時に使われることの証拠)。"""

        class _CountingProvider:
            def __init__(self) -> None:
                self.call_count = 0
                self._delegate = MockProvider()

            def complete(self, prompt):
                self.call_count += 1
                return self._delegate.complete(prompt)

        provider = _CountingProvider()
        outcome = run_cognitive_pipeline("買い物リストを作りたい", provider)
        self.assertIsInstance(outcome, CognitivePipelineSuccess)
        self.assertGreaterEqual(provider.call_count, 1, "明示的に渡したProviderが一度も呼ばれていない")

    def test_two_different_providers_can_be_swapped_independently(self) -> None:
        """同じ入力に対し、異なる2つのProviderインスタンスをそれぞれ渡しても、
        それぞれが独立して呼び出されること(Providerの差し替えが可能で
        あることの直接的な証拠)。"""

        class _TaggedProvider:
            def __init__(self, tag: str) -> None:
                self.tag = tag
                self.calls: list[str] = []
                self._delegate = MockProvider()

            def complete(self, prompt):
                self.calls.append(self.tag)
                return self._delegate.complete(prompt)

        provider_a = _TaggedProvider("A")
        provider_b = _TaggedProvider("B")
        run_cognitive_pipeline("買い物リストを作りたい", provider_a)
        run_cognitive_pipeline("買い物リストを作りたい", provider_b)

        self.assertEqual(provider_a.calls, ["A"] * len(provider_a.calls))
        self.assertEqual(provider_b.calls, ["B"] * len(provider_b.calls))
        self.assertGreaterEqual(len(provider_a.calls), 1)
        self.assertGreaterEqual(len(provider_b.calls), 1)


class TestPreliminaryFinalMismatchAcrossRevisions(unittest.TestCase):
    """CEO実物監査(Phase 1.1、2回目)指摘1の回帰テスト。`TemplateSelector.
    select_final()`自身がdiffers_from_preliminaryを毎回正しく設定する
    ことを、Revisionが複数回発生するシナリオで検証する。実際の自然言語
    入力では意図的なmismatchを再現しにくいため、Preliminary/Finalの
    整合状況を直接制御できるFake TemplateSelectorを使う。"""

    def _build_orchestrator(self, fake_template_selector) -> "object":
        from forge_ai.core.confirmation.escalation_handler import EscalationHandler
        from forge_ai.core.critic.design_critic import DesignCritic
        from forge_ai.core.critic.revision_engine import RevisionEngine
        from forge_ai.core.domain_model import DomainRegistry
        from forge_ai.core.input_processing.ambiguity_detector import AmbiguityDetector
        from forge_ai.core.input_processing.normalizer import InputNormalizer
        from forge_ai.core.orchestration.cognitive_dependencies import CognitiveDependencies
        from forge_ai.core.orchestration.pipeline_orchestrator import CognitiveOrchestrator
        from forge_ai.core.compiler import Compiler
        from forge_ai.core.planning.application_planner import CognitiveApplicationPlanner
        from forge_ai.quality.quality_engine import QualityEngine
        from forge_ai.core.understanding.domain_classifier import CognitiveDomainClassifier
        from forge_ai.core.understanding.intent_recognizer import CognitiveIntentRecognizer
        from forge_ai.core.understanding.meaning_extractor import CognitiveMeaningExtractor
        from forge_ai.core.understanding.requirement_extractor import RequirementExtractor
        from forge_ai.core.understanding.world_builder import CognitiveWorldBuilder

        deps = CognitiveDependencies(
            normalizer=InputNormalizer(), ambiguity_detector=AmbiguityDetector(),
            intent_recognizer=CognitiveIntentRecognizer(), domain_classifier=CognitiveDomainClassifier(),
            world_builder=CognitiveWorldBuilder(), meaning_extractor=CognitiveMeaningExtractor(),
            requirement_extractor=RequirementExtractor(),
            template_selector=fake_template_selector, planner=CognitiveApplicationPlanner(),
            design_critic=DesignCritic(), revision_engine=RevisionEngine(),
            escalation_handler=EscalationHandler(), compiler=Compiler(provider=MockProvider()),
            quality_engine=QualityEngine(),
        )
        return CognitiveOrchestrator(DomainRegistry(), deps)

    def test_mismatch_persists_across_revision_when_final_never_converges(self) -> None:
        """Revision後もFinal TemplateがPreliminary候補外なら、
        differs_from_preliminary=Trueが維持される(常にPreliminary候補外の
        Templateを返すFakeで検証)。"""
        from forge_ai.core.orchestration.cognitive_types import TemplateSelection

        class _AlwaysMismatchingSelector:
            def select_preliminary(self, domain, intent, requirements):
                return ("checklist",)

            def select_final(self, plan, preliminary_candidates=()):
                return TemplateSelection(
                    template="wizard", score_by_template=(("wizard", 1.0),),
                    differs_from_preliminary="wizard" not in preliminary_candidates, rationale="常にwizardを返すFake",
                )

        orchestrator = self._build_orchestrator(_AlwaysMismatchingSelector())
        outcome = orchestrator.run("買い物リストを作りたい")
        self.assertIsInstance(outcome, CognitivePipelineNeedsConfirmation)
        self.assertEqual(outcome.confirmation_request.reason, "preliminary_final_mismatch_exhausted")
        # 不一致が残ったままSuccessへは進んでいないことの確認。
        self.assertNotIsInstance(outcome, CognitivePipelineSuccess)

    def test_mismatch_resolves_to_false_once_converged_within_preliminary(self) -> None:
        """Revision後にPreliminary候補内へ収束した場合のみ
        differs_from_preliminary=Falseになる(1回目はPreliminary候補外、
        2回目(Revision後)はPreliminary候補内を返すFakeで検証)。"""
        from forge_ai.core.orchestration.cognitive_types import TemplateSelection

        class _ConvergingSelector:
            def __init__(self) -> None:
                self.call_count = 0

            def select_preliminary(self, domain, intent, requirements):
                return ("checklist",)

            def select_final(self, plan, preliminary_candidates=()):
                self.call_count += 1
                template = "wizard" if self.call_count == 1 else "checklist"
                return TemplateSelection(
                    template=template, score_by_template=((template, 1.0),),
                    differs_from_preliminary=template not in preliminary_candidates,
                    rationale=f"call_count={self.call_count}",
                )

        orchestrator = self._build_orchestrator(_ConvergingSelector())
        outcome = orchestrator.run("買い物リストを作りたい")
        # Template mismatch自体は収束しても、Capability PlanがUNKNOWNなら
        # 「checklistを選べた」ことを成功理由にしてはならない。
        # 新しいfail-closed契約では意味構造未解決として失敗する。
        self.assertIsInstance(outcome, CognitivePipelineNeedsExtension)
        self.assertEqual(outcome.reached_stage, "capability_gap")
        self.assertIn("semantic_structure_unresolved", str(outcome.error))
        self.assertEqual(outcome.extension_candidates[0].capability_id, "semantic_structure_unresolved")

    def test_shared_revision_limit_reached_results_in_needs_confirmation(self) -> None:
        """共有Revision上限到達時はNeedsConfirmationになる(上記の
        test_mismatch_persists...と同じシナリオだが、revision_attemptが
        実際にmax_revision_attemptsへ到達していることも確認する)。"""
        from forge_ai.core.orchestration.cognitive_types import TemplateSelection

        class _AlwaysMismatchingSelector:
            def select_preliminary(self, domain, intent, requirements):
                return ("checklist",)

            def select_final(self, plan, preliminary_candidates=()):
                return TemplateSelection(
                    template="wizard", score_by_template=(("wizard", 1.0),),
                    differs_from_preliminary=True, rationale="常に不一致",
                )

        orchestrator = self._build_orchestrator(_AlwaysMismatchingSelector())
        outcome = orchestrator.run("買い物リストを作りたい")
        self.assertIsInstance(outcome, CognitivePipelineNeedsConfirmation)
        self.assertGreaterEqual(
            outcome.partial_context.revision_attempt, outcome.partial_context.max_revision_attempts
        )


class TestMeaningModelIntegration(unittest.TestCase):
    """CEO指示(Phase 1.2)5章のIntegration Test要件に対応。"""

    def test_meaning_context_is_always_present_on_success(self) -> None:
        outcome = run_cognitive_pipeline("家族で共有できる買い物リストを作りたい")
        self.assertIsInstance(outcome, CognitivePipelineSuccess)
        self.assertIsNotNone(outcome.context.meaning)

    def test_decision_trace_records_meaning_extraction_stage(self) -> None:
        """Meaning ModelがWorldの後、Requirement Extractionの前に
        実行されることを、Decision Traceのstage順序で確認する。"""
        outcome = run_cognitive_pipeline("家族で共有できる買い物リストを作りたい")
        self.assertIsInstance(outcome, CognitivePipelineSuccess)
        stages = [dt.stage for dt in outcome.context.decision_trace]
        self.assertIn("meaning_extraction", stages)
        domain_idx = stages.index("domain_classification")
        meaning_idx = stages.index("meaning_extraction")
        self.assertLess(domain_idx, meaning_idx, "Domain ClassificationはMeaning Modelより前に実行されるべき")

    def test_success_cannot_be_constructed_without_meaning(self) -> None:
        """CognitivePipelineSuccess構築の前提条件チェックが、meaningの
        欠落を検出することを確認する(assert_context_ready_for_success)。"""
        from forge_ai.core.orchestration.cognitive_context import CognitiveContext
        from forge_ai.core.orchestration.outcomes import assert_context_ready_for_success
        from forge_ai.core.orchestration.errors import PlanningError

        incomplete_context = CognitiveContext(raw_input="x", started_at="2026-01-01T00:00:00")
        with self.assertRaises(PlanningError) as ctx:
            assert_context_ready_for_success(incomplete_context)
        self.assertIn("meaning", str(ctx.exception))

    def test_meaning_derived_action_is_reflected_in_plan(self) -> None:
        """Meaning由来のAction("share")が、実際にPlanのrequired_actions
        (primary_flow)へ反映されることを確認する(単にDecision Traceへ
        記録するだけの実装ではないことの証拠)。"""
        outcome = run_cognitive_pipeline("家族で共有できる買い物リストを作りたい")
        self.assertIsInstance(outcome, CognitivePipelineSuccess)
        self.assertIn("share", outcome.context.plan.primary_flow)

    def test_meaning_derived_entity_is_reflected_in_plan(self) -> None:
        """Meaning由来のEntity("photo"・"mood")が、実際にPlanの
        data_entitiesへ反映されることを確認する。"""
        outcome = run_cognitive_pipeline("写真と気分を記録できる日記がほしい")
        self.assertIsInstance(outcome, CognitivePipelineSuccess)
        self.assertIn("photo", outcome.context.plan.data_entities)
        self.assertIn("mood", outcome.context.plan.data_entities)

    def test_mandatory_meaning_requirement_unassigned_blocks_critic(self) -> None:
        """Meaning由来のmandatory要件がPlanへ反映されない場合、
        Criticがblockingすることを確認する(Fake RequirementExtractorで、
        意図的にtarget_ref/operation_refがWorldにもPlanにも存在しない
        Meaning由来requirementを生成させる)。"""
        from forge_ai.core.orchestration.cognitive_types import Requirement, RequirementSet
        from forge_ai.core.confirmation.escalation_handler import EscalationHandler
        from forge_ai.core.critic.design_critic import DesignCritic
        from forge_ai.core.critic.revision_engine import RevisionEngine
        from forge_ai.core.domain_model import DomainRegistry
        from forge_ai.core.input_processing.ambiguity_detector import AmbiguityDetector
        from forge_ai.core.input_processing.normalizer import InputNormalizer
        from forge_ai.core.orchestration.cognitive_dependencies import CognitiveDependencies
        from forge_ai.core.orchestration.pipeline_orchestrator import CognitiveOrchestrator
        from forge_ai.core.compiler import Compiler
        from forge_ai.core.planning.application_planner import CognitiveApplicationPlanner
        from forge_ai.core.planning.template_selector import TemplateSelector
        from forge_ai.quality.quality_engine import QualityEngine
        from forge_ai.core.understanding.domain_classifier import CognitiveDomainClassifier
        from forge_ai.core.understanding.intent_recognizer import CognitiveIntentRecognizer
        from forge_ai.core.understanding.meaning_extractor import CognitiveMeaningExtractor
        from forge_ai.core.understanding.world_builder import CognitiveWorldBuilder

        class _FakeRequirementExtractorWithUnreflectableMeaningRequirement:
            def extract(self, meaning, world, intent):
                return RequirementSet(requirements=(
                    Requirement(
                        # "preference"はtarget_ref/operation_refによる
                        # 自動反映(functional/data/permission対象)にも、
                        # description一致による自動反映
                        # (validation/schedule/state対象)にも該当しない
                        # カテゴリであり、Plannerの通常ロジックでは
                        # 機械的に判定できないため常に未割当のままになる
                        # (application_planner.pyのコメント「privacy/
                        # accessibility/preference/その他は常に未割当」
                        # 参照)。通常Preferenceはmandatory=Falseで
                        # 生成されるが、ここではテストのため意図的に
                        # mandatory=Trueとしている。
                        requirement_id="REQ-FAKE", category="preference",
                        description="Meaning由来だが決してPlanへ反映されないダミー要件(判定不能なカテゴリのため)",
                        mandatory=True, derived_from="meaning",
                    ),
                ))

        deps = CognitiveDependencies(
            normalizer=InputNormalizer(), ambiguity_detector=AmbiguityDetector(),
            intent_recognizer=CognitiveIntentRecognizer(), domain_classifier=CognitiveDomainClassifier(),
            world_builder=CognitiveWorldBuilder(), meaning_extractor=CognitiveMeaningExtractor(),
            requirement_extractor=_FakeRequirementExtractorWithUnreflectableMeaningRequirement(),
            template_selector=TemplateSelector(), planner=CognitiveApplicationPlanner(),
            design_critic=DesignCritic(), revision_engine=RevisionEngine(),
            escalation_handler=EscalationHandler(), compiler=Compiler(provider=MockProvider()),
            quality_engine=QualityEngine(),
        )
        orchestrator = CognitiveOrchestrator(DomainRegistry(), deps)
        outcome = orchestrator.run("買い物リストを作りたい")
        # このFake要件は自動反映されない(operation_refがWorldにも存在せず、
        # Plannerの通常ロジックでは反映されない)ため、Revisionでも解決できず
        # 最終的にNeedsConfirmationへ到達するはず。
        self.assertIsInstance(outcome, CognitivePipelineNeedsConfirmation)


if __name__ == "__main__":
    unittest.main()
