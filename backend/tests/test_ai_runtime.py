"""backend/app/ai/runtime/ 全体のテスト(FORGE-MILESTONE-003 PHASE6/7/9)。

Protocol/Stubが「実装したふり」をしていないこと(必ずNotImplementedErrorに
なること)、型エイリアスが既存のfoundation/interfaces.pyの型と同一であること
(重複定義していないことの回帰テスト)、ProviderRouterの実際に動作する
ルーティングロジック、PromptPipelineのオーケストレーション(repair loop・
最大試行回数)を検証する。

実行方法:
    cd backend
    python -m unittest tests.test_ai_runtime -v
"""

from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))  # forge_ai/ はrepoルート直下

from app.ai.foundation.interfaces import CriticResult, IntentIR, LLMAdapter, PlanIR  # noqa: E402
from app.ai.runtime.context_builder import PromptContext, StubAIContextBuilder  # noqa: E402
from app.ai.runtime.critic import StubAICritic  # noqa: E402
from app.ai.runtime.planner import Intent, Plan, StubAIPlanner  # noqa: E402
from app.ai.runtime.prompt_pipeline import MAX_REPAIR_ATTEMPTS, PromptPipeline  # noqa: E402
from app.ai.runtime.provider_router import (  # noqa: E402
    AIProvider,
    ProviderNotAvailableError,
    ProviderRouter,
)
from app.ai.runtime.repair import RepairResult, StubAIRepair  # noqa: E402
from app.ai.validators.schema_validator import ValidationResult, validate_forge_document  # noqa: E402


# ---------------------------------------------------------------------------
# 型の重複定義防止(「foundation/との関係」コメントの回帰テスト)
# ---------------------------------------------------------------------------

class TestTypeReuseNotDuplication(unittest.TestCase):
    def test_intent_is_intent_ir_alias(self) -> None:
        self.assertIs(Intent, IntentIR)

    def test_plan_is_plan_ir_alias(self) -> None:
        self.assertIs(Plan, PlanIR)

    def test_ai_provider_is_llm_adapter_alias(self) -> None:
        self.assertIs(AIProvider, LLMAdapter)


# ---------------------------------------------------------------------------
# 各Stubが「実装したふり」をしないことの回帰テスト
# ---------------------------------------------------------------------------

class TestStubsNeverFakeSuccess(unittest.TestCase):
    """禁止事項「AI実装したふり」「未実装を実装済みと書く」の回帰テスト。
    全Stubが例外無く成功を返すことは絶対に無い(必ずNotImplementedError)。"""

    def test_stub_planner_interpret_raises(self) -> None:
        with self.assertRaises(NotImplementedError):
            StubAIPlanner().interpret("x", ())

    def test_stub_planner_plan_raises(self) -> None:
        with self.assertRaises(NotImplementedError):
            StubAIPlanner().plan(IntentIR(purpose="x"), available_templates=())

    def test_stub_critic_raises(self) -> None:
        with self.assertRaises(NotImplementedError):
            StubAICritic().evaluate({}, IntentIR(purpose="x"))

    def test_stub_repair_raises(self) -> None:
        result = validate_forge_document({"version": "9.9"})
        with self.assertRaises(NotImplementedError):
            StubAIRepair().repair({}, result, attempt=1)

    def test_stub_context_builder_raises(self) -> None:
        with self.assertRaises(NotImplementedError):
            StubAIContextBuilder().build_context("s1", "p1", "u1")

    def test_all_foundation_provider_stubs_raise(self) -> None:
        """ProviderRouterが解決する8つの名前のうち、`mock`を除く7つ
        (5 Provider + 'native'/'local'の2エイリアス)で、実際に呼ぶと
        NotImplementedErrorになることを確認する(ルーティング自体は動くが、
        推論は`mock`以外一切動かない)。FORGE-MILESTONE-005 Task7で
        `mock`のみ実装したため、`mock`はこのテストの対象から除外する
        (`test_mock_provider_actually_works`で別途検証)。"""
        router = ProviderRouter()
        for name in router.available_providers():
            if name == "mock":
                continue
            with self.subTest(provider=name):
                provider = router.resolve(name)
                with self.assertRaises(NotImplementedError):
                    provider.complete_structured("prompt", {"type": "object"})

    def test_mock_provider_actually_works(self) -> None:
        """FORGE-MILESTONE-005 Task7新規。`mock`は例外を投げず、
        schemaに沿ったdictを実際に返すことを確認する。"""
        router = ProviderRouter()
        provider = router.resolve("mock")
        result = provider.complete_structured(
            "test prompt", {"type": "object", "properties": {"goal": {"type": "string"}}}
        )
        self.assertIn("goal", result)
        self.assertIsInstance(result["goal"], str)


# ---------------------------------------------------------------------------
# ProviderRouter(実際に動作するルーティングロジック)
# ---------------------------------------------------------------------------

class TestProviderRouter(unittest.TestCase):
    def setUp(self) -> None:
        self.router = ProviderRouter()

    def test_all_eight_provider_names_registered(self) -> None:
        """FORGE-MILESTONE-005 Task8で'mock'を追加したことに合わせて
        更新(7件→8件)。"""
        expected = {"openai", "claude", "gemini", "oss", "forge_ai", "native", "local", "mock"}
        self.assertEqual(set(self.router.available_providers()), expected)

    def test_native_alias_resolves_to_same_instance_as_forge_ai(self) -> None:
        """FORGE-MILESTONE-004 PHASE8新規。'native'は新しいProvider実装では
        なく、既存の'forge_ai'と同じインスタンスへのエイリアスであることを
        確認する。"""
        self.assertIs(self.router.resolve("native"), self.router.resolve("forge_ai"))

    def test_local_alias_resolves_to_same_instance_as_oss(self) -> None:
        """FORGE-MILESTONE-004 PHASE8新規。'local'は既存の'oss'と同じ
        インスタンスへのエイリアスであることを確認する。"""
        self.assertIs(self.router.resolve("local"), self.router.resolve("oss"))

    def test_default_provider_is_mock(self) -> None:
        """FORGE-MILESTONE-005で`forge_ai`から`mock`へ変更(ADAPTER_CONTRACT_V1.md
        4.0節、Engine/Provider分離のCEOレビュー対応)。`forge_ai`は
        Cognitive Engine名であり、Provider既定名として使うべきではなかった。"""
        self.assertEqual(self.router.default_provider_name(), "mock")

    def test_resolve_known_provider_succeeds(self) -> None:
        provider = self.router.resolve("claude")
        self.assertIsNotNone(provider)

    def test_resolve_unknown_provider_raises_typed_error_not_crash(self) -> None:
        with self.assertRaises(ProviderNotAvailableError):
            self.router.resolve("does_not_exist")

    def test_no_provider_specific_sdk_imported(self) -> None:
        """禁止事項「OpenAI SDK依存」等の回帰テスト。provider_router.pyのソースに
        実SDK importが無いことを静的に確認する。"""
        import inspect

        import app.ai.runtime.provider_router as module

        source = inspect.getsource(module)
        forbidden = ["import openai", "import anthropic", "import google.generativeai", "requests.post"]
        for term in forbidden:
            self.assertNotIn(term, source)


# ---------------------------------------------------------------------------
# ContextBuilder
# ---------------------------------------------------------------------------

class TestContextBuilder(unittest.TestCase):
    def test_prompt_context_user_preferences_defaults_to_none(self) -> None:
        """opt-inしていないユーザーの場合、user_preferencesはNoneであるべき
        (方針10章のプライバシー原則)。"""
        context = PromptContext()
        self.assertIsNone(context.user_preferences)

    def test_stub_accepts_injected_memory_and_conversation(self) -> None:
        builder = StubAIContextBuilder(memory=None, conversation=None)
        self.assertIsNotNone(builder)



# ---------------------------------------------------------------------------
# PromptPipeline(オーケストレーション、FORGE-MILESTONE-005でFacade方式へ
# 全面書き換え。ADAPTER_CONTRACT_V1.md 1.2節・7.2節参照)
# ---------------------------------------------------------------------------

from unittest.mock import MagicMock, patch  # noqa: E402

from forge_ai.core.compiler import ForgeIRDocument, ForgeIRScreen, ForgeIRWidget  # noqa: E402
from forge_ai.core.domain_model import Domain, DomainCategory  # noqa: E402
from forge_ai.core.intent_model import Intent as ForgeAIIntent  # noqa: E402
from forge_ai.core.orchestration.cognitive_context import CognitiveContext  # noqa: E402
from forge_ai.core.orchestration.cognitive_types import (  # noqa: E402
    AmbiguityReport,
    ConfirmationRequest,
    CriticReport,
    DecisionTrace,
    DomainClassification,
    ExtractedMeaning,
    RequirementSet,
    TemplateSelection,
)
from forge_ai.core.orchestration.errors import PlanningError as ForgeAICognitivePlanningError  # noqa: E402
from forge_ai.core.orchestration.outcomes import (  # noqa: E402
    CognitivePipelineFailed,
    CognitivePipelineNeedsConfirmation,
    CognitivePipelineSuccess,
)
from forge_ai.core.planner import ApplicationPlan  # noqa: E402
from forge_ai.quality.quality_engine import QualityScore  # noqa: E402
from forge_ai.repair.repair_engine import RepairResult as ForgeAIRepairResult  # noqa: E402

from app.ai.runtime.pipeline_errors import (  # noqa: E402
    ForgeValidationError,
    PlanningError,
    ProviderError,
    UnsupportedEngineError,
)
from app.ai.runtime.prompt_pipeline import PipelineNeedsConfirmationResult  # noqa: E402
from app.ai.validators.schema_validator import ValidationResult as RealValidationResult  # noqa: E402


def _make_cognitive_context(valid_screen_id: str = "s1") -> CognitiveContext:
    """`CognitiveContext`(Cognitive Pipelineの成功時Context)と同じ形の、
    テスト用の軽量な充足済みインスタンスを作る。`assert_context_ready_for_success`
    が要求する9フィールドを全て埋める。"""
    domain = Domain(category=DomainCategory.GENERIC, display_name="Generic", typical_concepts=(), typical_actions=())
    intent = ForgeAIIntent(goal="test goal", required_concepts=("item",), required_actions=("add_item",), constraints=())
    plan = ApplicationPlan(title="Test App", screens=(), data_entities=("item",), primary_flow=())
    return CognitiveContext(
        raw_input="test input",
        started_at="2026-07-17T00:00:00",
        normalized_input=MagicMock(),
        ambiguity_report=AmbiguityReport(issues=(), overall_severity="low", detection_status="ok"),
        intent=intent,
        domain_classification=DomainClassification(
            primary_domain=domain, candidates=(), confidence=1.0, score_margin=1.0, rationale="test",
        ),
        world=MagicMock(),
        meaning=ExtractedMeaning(summary="test summary"),
        requirements=RequirementSet(),
        preliminary_candidates=("checklist",),
        plan=plan,
        template_selection=TemplateSelection(
            template="checklist", score_by_template=(("checklist", 1.0),),
            differs_from_preliminary=False, rationale="test",
        ),
        critic_report=CriticReport(release_ready=True, score=1.0, coverage_ratio=1.0),
        decision_trace=(
            DecisionTrace(stage="domain_classification", decision="generic", reason="test"),
        ),
        revision_attempt=0,
    )


def _make_pipeline_result(valid_screen_id: str = "s1") -> CognitivePipelineSuccess:
    """`CognitivePipelineOutcome`の成功ケース(`CognitivePipelineSuccess`)を、
    `run_cognitive_pipeline()`の戻り値として使えるテスト用インスタンスとして
    作る(旧・Legacy `run_pipeline()`用の`PipelineResult`相当品を、
    Cognitive Pipeline接続後の形へ置き換えたもの)。"""
    screen = ForgeIRScreen(
        id=valid_screen_id, title="T", state={},
        body=ForgeIRWidget(type="text", id="t1", properties={"value": "hi"}),
    )
    ir = ForgeIRDocument(version="1.0", initial_screen_id=valid_screen_id, screens=(screen,), app_title="Test")
    quality = QualityScore(
        correctness=1.0, completeness=1.0, simplicity=1.0,
        runtime_safety=1.0, explainability=1.0, maintainability=1.0,
    )
    return CognitivePipelineSuccess(context=_make_cognitive_context(valid_screen_id), ir=ir, initial_quality=quality)


def _make_needs_confirmation() -> CognitivePipelineNeedsConfirmation:
    return CognitivePipelineNeedsConfirmation(
        confirmation_request=ConfirmationRequest(
            reason="priority1_privacy_safety_permission",
            message="対象者の情報範囲を確認させてください。",
            open_questions=("誰の情報を記録しますか？",),
        ),
        reached_stage="ambiguity_detection",
        partial_context=CognitiveContext(raw_input="test input", started_at="2026-07-17T00:00:00"),
        decision_trace=(DecisionTrace(stage="ambiguity_detection", decision="escalate", reason="privacy"),),
    )


def _make_cognitive_failed() -> CognitivePipelineFailed:
    return CognitivePipelineFailed(
        error=ForgeAICognitivePlanningError("計画を構築できませんでした。", stage="application_planning"),
        reached_stage="application_planning",
        decision_trace=(),
    )


def _valid_result() -> RealValidationResult:
    return RealValidationResult(valid=True, errors=[], warnings=[])


def _invalid_result() -> RealValidationResult:
    from app.ai.validators.schema_validator import Category, Severity, ValidationIssue

    issue = ValidationIssue(path="$/app", category=Category.SCHEMA, severity=Severity.BLOCKING,
                             rule="missing_app_title", message="app.titleがありません。")
    return RealValidationResult(valid=False, errors=[issue], warnings=[])


class TestPromptPipelineFacade(unittest.TestCase):
    """ADAPTER_CONTRACT_V1.md 1.2節・7.2節(Facade方式)の回帰テスト。"""

    def test_prompt_pipeline_module_does_not_import_individual_m004_components(self) -> None:
        """ADR 1.2節・7.3節の回帰テスト: MeaningExtractor/IntentBuilder/
        Planner/Compilerをprompt_pipeline.pyから直接importしていないことを、
        実際のソースを検査して確認する。"""
        import inspect

        import app.ai.runtime.prompt_pipeline as module

        source = inspect.getsource(module)
        forbidden = [
            "from forge_ai.core.meaning_model import",
            "from forge_ai.core.intent_model import",
            "from forge_ai.core.planner import",
            "from forge_ai.core.compiler import",
        ]
        for term in forbidden:
            self.assertNotIn(term, source, f"prompt_pipeline.pyが個別コンポーネントをimportしています: {term}")

    def test_prompt_pipeline_does_not_use_legacy_run_pipeline(self) -> None:
        """FORGE v0.2 PART A 4章の回帰テスト: 本番経路がLegacy
        `run_pipeline()`ではなく`run_cognitive_pipeline()`を使うこと。"""
        import inspect

        import app.ai.runtime.prompt_pipeline as module

        source = inspect.getsource(module)
        self.assertIn("run_cognitive_pipeline", source)
        self.assertNotIn("from forge_ai.core.pipeline import run_pipeline", source)

    @patch("app.ai.runtime.prompt_pipeline.run_cognitive_pipeline")
    def test_run_cognitive_pipeline_called_exactly_once(self, mock_run_cognitive_pipeline: MagicMock) -> None:
        mock_run_cognitive_pipeline.return_value = _make_pipeline_result()
        pipeline = PromptPipeline()
        pipeline.run("test input")
        self.assertEqual(mock_run_cognitive_pipeline.call_count, 1)

    @patch("app.ai.runtime.prompt_pipeline.validate_forge_document")
    @patch("app.ai.runtime.prompt_pipeline.run_cognitive_pipeline")
    def test_valid_document_skips_repair(self, mock_run_cognitive_pipeline: MagicMock, mock_validate: MagicMock) -> None:
        mock_run_cognitive_pipeline.return_value = _make_pipeline_result()
        mock_validate.return_value = _valid_result()
        with patch("app.ai.runtime.prompt_pipeline.RepairEngine") as mock_repair_cls:
            pipeline = PromptPipeline()
            result = pipeline.run("test input")
            mock_repair_cls.assert_not_called()
        self.assertEqual(result.diagnostics.repair_attempts, 0)
        self.assertIsNotNone(result.quality)

    @patch("app.ai.runtime.prompt_pipeline.validate_forge_document")
    @patch("app.ai.runtime.prompt_pipeline.run_cognitive_pipeline")
    def test_invalid_then_repaired_then_valid(self, mock_run_cognitive_pipeline: MagicMock, mock_validate: MagicMock) -> None:
        outcome = _make_pipeline_result()
        mock_run_cognitive_pipeline.return_value = outcome
        # 1回目: 不合格、Repair後の再検証: 合格。
        mock_validate.side_effect = [_invalid_result(), _valid_result()]
        repaired_result = ForgeAIRepairResult(ir=outcome.ir, fixed_issues=(), remaining_issues=(), iterations=1)
        with patch("app.ai.runtime.prompt_pipeline.RepairEngine") as mock_repair_cls:
            mock_repair_cls.return_value.repair.return_value = repaired_result
            pipeline = PromptPipeline()
            result = pipeline.run("test input")
            # ADR 2.4節「二重ループ問題」への対応: max_iterations=1で構築されること。
            mock_repair_cls.assert_called_once()
            _, kwargs = mock_repair_cls.call_args
            self.assertEqual(kwargs.get("max_iterations"), 1)
        self.assertEqual(result.diagnostics.repair_attempts, 1)
        self.assertEqual(mock_validate.call_count, 2)

    @patch("app.ai.runtime.prompt_pipeline.validate_forge_document")
    @patch("app.ai.runtime.prompt_pipeline.run_cognitive_pipeline")
    def test_repair_exhausted_still_invalid_raises_forge_validation_error(
        self, mock_run_cognitive_pipeline: MagicMock, mock_validate: MagicMock
    ) -> None:
        """指示書10章「Repair回数」の回帰テスト。max_repair_attempts=2の場合、
        Validatorは最大3回(初回+Repair後2回)呼ばれる。"""
        outcome = _make_pipeline_result()
        mock_run_cognitive_pipeline.return_value = outcome
        mock_validate.return_value = _invalid_result()  # 常に不合格
        repaired_result = ForgeAIRepairResult(ir=outcome.ir, fixed_issues=(), remaining_issues=(outcome.ir,), iterations=1)
        with patch("app.ai.runtime.prompt_pipeline.RepairEngine") as mock_repair_cls:
            mock_repair_cls.return_value.repair.return_value = repaired_result
            pipeline = PromptPipeline(max_repair_attempts=2)
            with self.assertRaises(ForgeValidationError):
                pipeline.run("test input")
            self.assertEqual(mock_repair_cls.return_value.repair.call_count, 2)
        self.assertEqual(mock_validate.call_count, 3)

    @patch("app.ai.runtime.prompt_pipeline.QualityEngine")
    @patch("app.ai.runtime.prompt_pipeline.validate_forge_document")
    @patch("app.ai.runtime.prompt_pipeline.run_cognitive_pipeline")
    def test_quality_reevaluated_after_repair(
        self, mock_run_cognitive_pipeline: MagicMock, mock_validate: MagicMock, mock_quality_cls: MagicMock
    ) -> None:
        """ADR 2.5節の回帰テスト: Repairが発生した場合、outcome.initial_quality
        (修正前の評価)をそのまま使わず、QualityEngineで再評価する。"""
        outcome = _make_pipeline_result()
        mock_run_cognitive_pipeline.return_value = outcome
        mock_validate.side_effect = [_invalid_result(), _valid_result()]
        repaired_result = ForgeAIRepairResult(ir=outcome.ir, fixed_issues=(), remaining_issues=(), iterations=1)
        reevaluated_quality = QualityScore(
            correctness=0.5, completeness=0.5, simplicity=0.5,
            runtime_safety=0.5, explainability=0.5, maintainability=0.5,
        )
        mock_quality_cls.return_value.evaluate.return_value = reevaluated_quality
        with patch("app.ai.runtime.prompt_pipeline.RepairEngine") as mock_repair_cls:
            mock_repair_cls.return_value.repair.return_value = repaired_result
            pipeline = PromptPipeline()
            result = pipeline.run("test input")
        mock_quality_cls.return_value.evaluate.assert_called_once()
        self.assertEqual(result.quality.score, 50)  # 0.5 * 100、outcome.initial_quality(全て1.0)ではない

    @patch("app.ai.runtime.prompt_pipeline.run_cognitive_pipeline")
    def test_quality_score_reflects_critic_coverage_ratio_not_always_100(
        self, mock_run_cognitive_pipeline: MagicMock
    ) -> None:
        """FORGE_v0.2_修正指示.md P1 6章の回帰テスト(「100点乱発は禁止」)。

        `context.critic_report.coverage_ratio`が1.0未満(=M006 14軸のうち
        実際に評価できたのは一部だけ)の場合、最終scoreが100にならない
        ことを確認する。以前は`to_critic_result()`側にcoverage_ratioを
        使うロジックが実装されていたにもかかわらず、呼び出し箇所
        (`prompt_pipeline.py`)が`critic_report`引数を渡していなかった
        ため、実際には一度も機能していなかった(このセッションで実際に
        `PromptPipeline().run()`を実行し、修正前はscore=100が返り続ける
        ことを確認した上で修正した)。
        """
        import dataclasses

        from forge_ai.core.orchestration.cognitive_types import CriticReport

        outcome = _make_pipeline_result()
        # coverage_ratio=0.5(M006 14軸中7軸相当)、implemented_checks側は
        # 満点(1.0)というシナリオ: IR自体は構造的に完璧でも、Design
        # Criticの評価範囲が限定的であれば、scoreは100にならないはず。
        low_coverage_critic_report = dataclasses.replace(
            outcome.context.critic_report,
            score=1.0,
            coverage_ratio=0.5,
        )
        outcome = dataclasses.replace(
            outcome, context=dataclasses.replace(outcome.context, critic_report=low_coverage_critic_report)
        )
        mock_run_cognitive_pipeline.return_value = outcome
        pipeline = PromptPipeline()
        result = pipeline.run("test input")
        self.assertIsNotNone(result.quality)
        self.assertLess(result.quality.score, 100)

    @patch("app.ai.runtime.prompt_pipeline.run_cognitive_pipeline")
    def test_quality_score_is_100_when_coverage_is_complete(self, mock_run_cognitive_pipeline: MagicMock) -> None:
        """上記の対照実験: coverage_ratio=1.0(全軸評価済み)かつIRが
        構造的に完璧な場合は、100点も正当な結果でありうることを確認する
        (「100点を一律禁止する」のではなく、「実際の評価範囲を反映しない
        まま100点になっていた」ことが問題だったことの裏付け)。"""
        import dataclasses

        outcome = _make_pipeline_result()
        full_coverage_critic_report = dataclasses.replace(
            outcome.context.critic_report, score=1.0, coverage_ratio=1.0
        )
        outcome = dataclasses.replace(
            outcome, context=dataclasses.replace(outcome.context, critic_report=full_coverage_critic_report)
        )
        mock_run_cognitive_pipeline.return_value = outcome
        pipeline = PromptPipeline()
        result = pipeline.run("test input")
        self.assertEqual(result.quality.score, 100)

    @patch("app.ai.runtime.prompt_pipeline.run_cognitive_pipeline")
    def test_diagnostics_carries_cognitive_pipeline_fields(self, mock_run_cognitive_pipeline: MagicMock) -> None:
        """FORGE v0.2 PART A 4.2節の回帰テスト: Diagnosticsが
        cognitive_revision_attempts・ambiguity_report・domain_classification・
        decision_traceを実際に伝播すること(Schema RepairとCognitive
        Revisionのカウンタが独立していることも合わせて確認する)。"""
        outcome = _make_pipeline_result()
        # revision_attempt(Cognitive Revision Loop側)を2として、Schema Repair
        # とは独立したカウンタであることが分かるようにする。
        import dataclasses

        outcome = dataclasses.replace(outcome, context=dataclasses.replace(outcome.context, revision_attempt=2))
        mock_run_cognitive_pipeline.return_value = outcome
        pipeline = PromptPipeline()
        result = pipeline.run("test input")
        self.assertEqual(result.diagnostics.cognitive_revision_attempts, 2)
        self.assertEqual(result.diagnostics.repair_attempts, 0)  # Schema Repairは別カウンタ、今回は未発生
        self.assertIsNotNone(result.diagnostics.ambiguity_report)
        self.assertIsNotNone(result.diagnostics.domain_classification)
        self.assertGreaterEqual(len(result.diagnostics.decision_trace), 1)

    @patch("app.ai.runtime.prompt_pipeline.run_cognitive_pipeline")
    def test_needs_confirmation_outcome_is_returned_not_raised(self, mock_run_cognitive_pipeline: MagicMock) -> None:
        """FORGE v0.2 PART A 4.1節の回帰テスト: `CognitivePipelineNeedsConfirmation`
        は例外として潰さず、`PipelineNeedsConfirmationResult`という正式な
        戻り値として返す。"""
        mock_run_cognitive_pipeline.return_value = _make_needs_confirmation()
        pipeline = PromptPipeline()
        result = pipeline.run("test input")
        self.assertIsInstance(result, PipelineNeedsConfirmationResult)
        self.assertEqual(result.reason, "priority1_privacy_safety_permission")
        self.assertEqual(result.reached_stage, "ambiguity_detection")
        self.assertEqual(result.open_questions, ("誰の情報を記録しますか？",))
        self.assertEqual(result.engine_used, "forge_ai")
        self.assertEqual(result.provider_used, "mock")

    @patch("app.ai.runtime.prompt_pipeline.run_cognitive_pipeline")
    def test_cognitive_pipeline_failed_raises_planning_error(self, mock_run_cognitive_pipeline: MagicMock) -> None:
        """FORGE v0.2 PART A 4.1節の回帰テスト: `CognitivePipelineFailed`は
        既存Error Envelope体系(`PlanningError`、category="planning_error")
        へ変換される。"""
        mock_run_cognitive_pipeline.return_value = _make_cognitive_failed()
        pipeline = PromptPipeline()
        with self.assertRaises(PlanningError) as ctx:
            pipeline.run("test input")
        self.assertEqual(ctx.exception.category, "planning_error")
        self.assertIn("application_planning", str(ctx.exception))

    def test_error_stage_is_structured_not_only_in_message(self) -> None:
        """FORGE v0.2 P1 5章の回帰テスト: `reached_stage`はメッセージ
        文字列への埋め込みだけでなく、例外の`stage`属性として構造化
        されている(Frontendが文字列パースに頼らず読める)。"""
        pipeline = PromptPipeline()
        with self.assertRaises(UnsupportedEngineError) as ctx:
            pipeline.run("test", engine="bogus")
        self.assertEqual(ctx.exception.stage, "engine_validation")

        pipeline = PromptPipeline()
        with self.assertRaises(ProviderError) as ctx2:
            pipeline.run("test", provider="does_not_exist")
        self.assertEqual(ctx2.exception.stage, "provider_resolution")

    @patch("app.ai.runtime.prompt_pipeline.run_cognitive_pipeline")
    def test_cognitive_pipeline_failed_carries_stage_from_outcome(self, mock_run_cognitive_pipeline: MagicMock) -> None:
        mock_run_cognitive_pipeline.return_value = _make_cognitive_failed()
        pipeline = PromptPipeline()
        with self.assertRaises(PlanningError) as ctx:
            pipeline.run("test input")
        self.assertEqual(ctx.exception.stage, "application_planning")

    @patch("app.ai.runtime.prompt_pipeline.run_cognitive_pipeline")
    def test_needs_confirmation_carries_partial_ambiguity_and_domain_diagnostics(
        self, mock_run_cognitive_pipeline: MagicMock
    ) -> None:
        """FORGE v0.2 P1 4章の回帰テスト: `partial_context`に既に埋まって
        いるambiguity_report・domain_classificationは、needs_confirmation
        レスポンスでも失われない。"""
        domain = Domain(category=DomainCategory.SHOPPING, display_name="Shopping", typical_concepts=(), typical_actions=())
        rich_context = CognitiveContext(
            raw_input="test input",
            started_at="2026-07-17T00:00:00",
            ambiguity_report=AmbiguityReport(issues=(), overall_severity="low", detection_status="ok"),
            domain_classification=DomainClassification(
                primary_domain=domain, candidates=(), confidence=0.9, score_margin=0.5, rationale="test",
            ),
        )
        outcome = CognitivePipelineNeedsConfirmation(
            confirmation_request=ConfirmationRequest(reason="priority2_low_domain_confidence", message="確認してください"),
            reached_stage="domain_classification",
            partial_context=rich_context,
            decision_trace=(),
        )
        mock_run_cognitive_pipeline.return_value = outcome
        pipeline = PromptPipeline()
        result = pipeline.run("test input")
        self.assertIsInstance(result, PipelineNeedsConfirmationResult)
        self.assertIsNotNone(result.ambiguity_report)
        self.assertIsNotNone(result.domain_classification)
        self.assertEqual(result.domain_classification["primary_domain"], "shopping")

    @patch("app.ai.runtime.prompt_pipeline.run_cognitive_pipeline")
    def test_needs_confirmation_diagnostics_are_none_when_not_yet_computed(
        self, mock_run_cognitive_pipeline: MagicMock
    ) -> None:
        """未到達の段階の情報は`None`のままにする(存在しない情報を
        捏造しない、共通指示書の原則)。"""
        mock_run_cognitive_pipeline.return_value = _make_needs_confirmation()
        pipeline = PromptPipeline()
        result = pipeline.run("test input")
        self.assertIsNone(result.domain_classification)

    @patch("app.ai.runtime.prompt_pipeline.run_cognitive_pipeline")
    def test_unsupported_engine_raises_before_calling_run_cognitive_pipeline(
        self, mock_run_cognitive_pipeline: MagicMock
    ) -> None:
        pipeline = PromptPipeline()
        with self.assertRaises(UnsupportedEngineError):
            pipeline.run("test", engine="not_forge_ai")
        mock_run_cognitive_pipeline.assert_not_called()

    def test_unregistered_provider_raises_provider_error_503(self) -> None:
        pipeline = PromptPipeline()
        with self.assertRaises(ProviderError) as ctx:
            pipeline.run("test", provider="does_not_exist")
        self.assertEqual(ctx.exception.http_status, 503)
        self.assertEqual(ctx.exception.sub_reason, "unavailable")

    def test_unimplemented_provider_raises_provider_error(self) -> None:
        pipeline = PromptPipeline()
        with self.assertRaises(ProviderError):
            pipeline.run("test", provider="openai")

    def test_very_short_input_escalates_before_provider_is_invoked(self) -> None:
        """回帰テスト(CEO実物監査、pytest実行で発見): 1文字の入力は
        Ambiguity Detection(missing_goal、HIGH severity)で
        `needs_confirmation`となり、Providerが実際に呼ばれる前に
        Pipelineが終了する。`provider="openai"`(未実装)を指定していても
        `ProviderError`は送出されない(Providerへ到達しないため)。
        `backend/tests/test_http_api.py`の
        `test_error_envelope_format_is_consistent_across_error_types`が
        以前この挙動と衝突して失敗していた原因の根本を、実行可能な形で
        固定する。"""
        pipeline = PromptPipeline()
        result = pipeline.run("x", provider="openai")
        self.assertIsInstance(result, PipelineNeedsConfirmationResult)
        self.assertEqual(result.reason, "ambiguity_high_severity")
        self.assertEqual(result.reached_stage, "ambiguity_detection")

    def test_default_provider_is_mock_end_to_end(self) -> None:
        """Mockを実際に使ったEnd-to-Endの成功ケース(モックしない、実行確認)。"""
        pipeline = PromptPipeline()
        result = pipeline.run("add item track shopping price")
        self.assertTrue(result.validation.valid)
        self.assertEqual(result.diagnostics.provider_used, "mock")
        self.assertEqual(result.diagnostics.engine_used, "forge_ai")


if __name__ == "__main__":
    unittest.main()
