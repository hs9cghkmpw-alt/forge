"""AI Runtime — Prompt Pipeline(FORGE v0.2 PART A — Cognitive Pipeline本番接続)。

**変更点(FORGE_v0.2_COMPLETE_IMPLEMENTATION_DIRECTIVE.md PART A 4章)**:
本番生成経路は、Legacyの`forge_ai.core.pipeline.run_pipeline()`ではなく
`forge_ai.core.pipeline.run_cognitive_pipeline()`を1回だけ呼ぶ(粗粒度
Facade)。これによりAmbiguity Detection・Domain Classification・Meaning
Model・Requirement Extraction・Template Selection・Design Critic・
Cognitive Revisionを含む、M006 Cognitive Architectureの全段階が本番経路へ
接続される(旧`run_pipeline()`はこれらを一切実行しない、より単純な後方
互換経路であり、新しい本番経路からは呼ばない。ただし後方互換のため
`forge_ai/`側の関数自体は削除しない)。

**責務(`docs/spec/ADAPTER_CONTRACT_V1.md` 1.2節を、Cognitive Pipeline用に
更新)**:
1. Engine/Provider検証
2. Provider解決(`ProviderRouter`)
3. M004 `run_cognitive_pipeline()`を1回だけ呼ぶ(個別コンポーネントは呼ばない)
4. `CognitivePipelineOutcome`(Success / NeedsConfirmation / Failed)を分岐処理
5. Success: IRをdict化 → Validator → 不合格時Repair → 再Validation →
   Repair後Quality再評価 → CriticResult変換
6. NeedsConfirmation: 例外にせず、`PipelineNeedsConfirmationResult`という
   正式な戻り値として返す(ディレクティブPART A 4.1節「例外として潰さず、
   公開APIの正式な結果型として返す」)
7. Failed: 既存Error Envelope体系(`PlanningError`)へ変換
8. Diagnostics作成(Decision Trace・Ambiguity・Domain Classification等を含む)
9. 結果返却

このファイルは`forge_ai.core.pipeline.run_cognitive_pipeline`・
`forge_ai.repair.repair_engine.RepairEngine`・
`forge_ai.quality.quality_engine.QualityEngine`の3つに限り、forge_ai/を
直接importしてよい。禁止されているのは`MeaningExtractor`/
`IntentBuilder`/`Planner`/`Compiler`という個別コンポーネントの直接呼び出し
であり、この3つ以外はこのファイルからimportしない(回帰テストで検査)。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from forge_ai.core.orchestration.outcomes import (
    CognitivePipelineFailed,
    CognitivePipelineNeedsConfirmation,
    CognitivePipelineSuccess,
)
from forge_ai.core.orchestration.cognitive_types import DecisionTrace
from forge_ai.core.pipeline import run_cognitive_pipeline
from forge_ai.quality.quality_engine import QualityEngine
from forge_ai.repair.repair_engine import RepairEngine

from app.ai.foundation.interfaces import CriticResult
from app.ai.gateway.ai_router import AIRouter, NoProviderAvailableError, default_router
from app.ai.gateway.tasks import ForgeTask
from app.ai.runtime.forge_ai_adapter import (
    intent_ir_from_forge_ai_intent,
    plan_ir_from_application_plan,
    to_backend_repair_result,
    to_critic_result,
    to_repair_issues,
)
from app.ai.runtime.forge_ai_provider_bridge import ForgeAIProviderBridge
from app.ai.runtime.output_safety import OutputSafetyChecker
from app.ai.runtime.pipeline_errors import (
    ForgeValidationError,
    PlanningError,
    ProviderError,
    UnsupportedEngineError,
)
from app.ai.runtime.provider_router import ProviderRouter
from app.ai.validators.schema_validator import ValidationResult, validate_forge_document

# 共通指示書6.5節「修正回数には上限を設ける。推奨は最大2回。無限修正
# ループは禁止」。ADR 2.4節の二重ループ問題を踏まえ、このMAX_REPAIR_ATTEMPTS
# だけがリトライ回数を制御する(forge_ai.RepairEngineはmax_iterations=1で
# 構築し、内側の独自ループを無効化する)。
MAX_REPAIR_ATTEMPTS = 2

# 現時点でサポートするEngineは"forge_ai"のみ(ADR 4.0節)。
SUPPORTED_ENGINES = ("forge_ai",)


@dataclass(frozen=True)
class Diagnostics:
    """HTTPレスポンスの`diagnostics`フィールドに対応する(ADAPTER_CONTRACT_V1.md
    5.3節を、Cognitive Pipeline接続に合わせて拡張)。

    `conversion_warnings`はCEO実物監査対応(Fix 2): `plan_ir_from_
    application_plan()`がpresentation conceptと判定してdata_neededから
    除外した要素の警告を、以前はどこにも返さず捨てていた。ここへ含めて
    HTTPレスポンス経由で確認できるようにする。

    `repair_attempts`は既存フィールド名を維持する(Schema Repair、
    `forge_ai.repair.repair_engine.RepairEngine`の試行回数)。
    `cognitive_revision_attempts`はこれとは独立したカウンタであり、
    Cognitive Revision Loop(Design Criticの指摘に基づくApplicationPlanの
    修正)の試行回数を表す(2つのループのカウンタは完全に独立、共通指示書
    6.5節・M005 D59の教訓)。
    """

    engine_used: str
    provider_used: str
    repair_attempts: int
    intent_ir: dict[str, Any] | None = None
    plan_ir: dict[str, Any] | None = None
    conversion_warnings: tuple[str, ...] = ()
    cognitive_revision_attempts: int = 0
    ambiguity_report: dict[str, Any] | None = None
    domain_classification: dict[str, Any] | None = None
    decision_trace: tuple[dict[str, Any], ...] = ()

    injection_report: dict[str, Any] | None = None
    """FORGE-AI-CONNECT-001 TD21対応(2026-08-11)。呼び出し側
    (`routers/ai.py`)が`app.ai.runtime.injection_scan.scan_for_injection()`
    で事前に計算した結果をそのまま受け取り、診断として記録するだけ
    (`PromptPipeline`自体はforge_ai/のInjection Guardを直接呼ばない、
    既存の「このファイルはforge_ai/を3つに限り直接importしてよい」という
    制約を守るため)。検出のみで、ブロックはしない。"""

    safety_report: dict[str, Any] | None = None
    """FORGE-AI-CONNECT-001 TD20対応(2026-08-11)。最終Forge Documentに
    対する`OutputSafetyChecker`(`app/ai/runtime/output_safety.py`、
    backend内で完結しforge_ai/には依存しない)の検査結果。検出のみで、
    生成そのものはブロックしない(TD21と同じ設計方針)。"""


@dataclass(frozen=True)
class PipelineRunResult:
    """`PromptPipeline.run()`の戻り値(成功時)。HTTP層がこれをそのまま
    Responseへ整形できる形にしている。"""

    forge_document: dict[str, Any]
    validation: ValidationResult
    quality: CriticResult | None
    diagnostics: Diagnostics


@dataclass(frozen=True)
class PipelineNeedsConfirmationResult:
    """`PromptPipeline.run()`の戻り値(確認要求時)。

    ディレクティブPART A 4.1節: `CognitivePipelineNeedsConfirmation`は
    例外として潰さず、公開APIの正式な結果型として返す。HTTP層はこれを
    `status = "needs_confirmation"`のレスポンスへ変換する(5.2節)。

    `ambiguity_report`・`domain_classification`はFORGE v0.2 P1 4章
    「Diagnosticsを失わない」対応で追加した(既定値`None`)。到達した
    段階までに実際に計算済みの情報のみを保持し、未到達の段階は`None`の
    ままにする(存在しない情報を捏造しない)。
    """

    reason: str
    message: str
    open_questions: tuple[str, ...]
    reached_stage: str
    engine_used: str
    provider_used: str
    decision_trace: tuple[dict[str, Any], ...] = ()
    ambiguity_report: dict[str, Any] | None = None
    domain_classification: dict[str, Any] | None = None
    injection_report: dict[str, Any] | None = None
    """FORGE-AI-CONNECT-001 TD21対応(2026-08-11)。`Diagnostics.
    injection_report`と同じ(呼び出し側が事前計算した結果をそのまま
    保持するだけ)。"""

    requested_provider: str | None = None
    """利用者が**明示的に要求した**Provider名(通常は`None`)。

    FORGE-AI-FOUNDATION-010 Phase Bで追加。`provider_used`とは意味が
    違う——`provider_used`は「実際に応答を返したのは誰か」という観測
    結果であり、確認往復の再開時に**そのまま指定し直してよい値では
    ない**(そもそも何も呼ばれていなければ`"none"`になる)。

    `/generate/confirm`はこの値を`ConfirmationStore`へ保存して再開時に
    渡す。再現すべきなのは「利用者の指定」であって「たまたま選ばれた
    Provider」ではない。`None`のまま保存すれば、再開時も同じように
    Routingが働く。"""


PromptPipelineOutcome = PipelineRunResult | PipelineNeedsConfirmationResult


def _decision_trace_to_dicts(decision_trace: tuple[DecisionTrace, ...]) -> tuple[dict[str, Any], ...]:
    """`DecisionTrace`(forge_ai/、frozen dataclass)をJSON化しやすいdictへ
    変換する(診断表示用の簡易シリアライズ)。"""

    return tuple(
        {
            "stage": entry.stage,
            "decision": entry.decision,
            "reason": entry.reason,
            "confidence": entry.confidence,
            "alternatives": list(entry.alternatives),
        }
        for entry in decision_trace
    )


def _ambiguity_report_to_dict(ambiguity_report: Any) -> dict[str, Any] | None:
    if ambiguity_report is None:
        return None
    return {
        "detection_status": ambiguity_report.detection_status,
        "overall_severity": ambiguity_report.overall_severity,
        "issues": [
            {"category": i.category, "severity": i.severity, "description": i.description}
            for i in ambiguity_report.issues
        ],
    }


def _domain_classification_to_dict(classification: Any) -> dict[str, Any] | None:
    if classification is None:
        return None
    primary = classification.primary_domain
    return {
        "primary_domain": primary.category.value,
        "display_name": primary.display_name,
        "confidence": classification.confidence,
        "score_margin": classification.score_margin,
        "rationale": classification.rationale,
        "candidates": [
            {"domain": c.domain.category.value, "raw_score": c.raw_score, "normalized_score": c.normalized_score}
            for c in classification.candidates
        ],
    }


class PromptPipeline:
    """ADR 1.2節のフローを、Facade方式で実行する。

    Widget/画面固有の知識を持たない(Runtime非依存)。判断ロジックは
    「Validator結果に基づく分岐」「Repairループの回数制御」に限定し、
    認知処理そのもの(Meaning/Intent/Planner/Compile)はforge_ai/
    (`run_pipeline()`)へ完全に委譲する(「巨大Manager」にしないための
    設計方針)。
    """

    def __init__(
        self,
        *,
        provider_router: ProviderRouter | None = None,
        ai_router: AIRouter | None = None,
        max_repair_attempts: int = MAX_REPAIR_ATTEMPTS,
    ) -> None:
        self._provider_router = provider_router or ProviderRouter()
        self._ai_router = ai_router
        self._max_repair_attempts = max_repair_attempts

    @property
    def ai_router(self) -> AIRouter:
        """AI呼び出しの唯一の出口(FORGE-AI-FOUNDATION-010 Phase B)。

        遅延解決にしているのは、`default_router()`のCatalogが環境変数を
        読むためである。import時に固定すると、テストが環境を差し替えても
        古いCatalogを見続ける。
        """
        return self._ai_router or default_router()

    def run(
        self,
        natural_language: str,
        *,
        engine: str = "forge_ai",
        provider: str | None = None,
        clarification_answers: tuple[str, ...] = (),
        injection_report: dict[str, Any] | None = None,
        title_seed: str | None = None,
    ) -> PromptPipelineOutcome:
        """フロー全体を1回実行する。

        `injection_report`(FORGE-AI-CONNECT-001 TD21対応、2026-08-11):
        呼び出し側が`app.ai.runtime.injection_scan.scan_for_injection()`で
        事前に計算した結果。このメソッド自身は計算せず、そのまま
        Diagnostics/PipelineNeedsConfirmationResultへ記録するだけ
        (このファイルがforge_ai/を直接importしてよい3つに限る制約を
        守るため)。

        `clarification_answers`(FORGE v0.2 Final Gate P0.1で新設、
        最終調整で複数累積対応へ変更): `needs_confirmation`への回答が
        ある場合に渡す。**複数回の確認往復があった場合、全ての回答を
        タプルで渡すこと**(1回目の回答を失わないため)。呼び出し側は
        あらかじめ`natural_language`へ結合済みの文字列を作ってはならない
        (以前の`confirmation_store.py`のバグ、6.3節参照)。この関数が
        `run_cognitive_pipeline()`へ両方を別引数として渡し、内部で
        ラベル無しの結合を1箇所(`forge_ai.core.pipeline._combine_
        with_answers()`)だけで行う。

        `title_seed`(FORGE-HANDOFF-LOCAL-AI-UX-004、2026-08-13):
        生成されるアプリのタイトルを導出する元にする短いテキスト。
        `/converse`経由の場合、`natural_language`は会話全体を要約した
        `build_brief`(説明文)であり、そこからタイトルを作ると
        「〜を記録・管理するための道具」という説明文がそのまま
        アプリ名になる(実機で確認)。ユーザー自身の短い言葉を
        ここへ渡す。Domain判定等は引き続き`natural_language`全体を使う。

        戻り値は`PipelineRunResult`(成功)または
        `PipelineNeedsConfirmationResult`(確認要求、正式な結果型として
        返す。例外にしない)のいずれか。

        送出しうる例外(いずれも`pipeline_errors.py`で定義、HTTP層が
        Error Envelopeへ変換する):
        - `UnsupportedEngineError`: `engine`が未知の値。
        - `ProviderError`(sub_reason="unavailable"): Provider名が
          未登録、またはMock以外の未実装Providerを実際に呼んだ場合。
        - `ForgeValidationError`: Repair試行後もValidator不合格。
        - `PlanningError`: `run_cognitive_pipeline()`が回復不能な失敗
          (`CognitivePipelineFailed`)を返した場合、または予期しない
          例外を送出した場合。
        """
        # 1. Engine検証
        if engine not in SUPPORTED_ENGINES:
            raise UnsupportedEngineError(
                f"engine '{engine}' はサポートされていません。利用可能: {SUPPORTED_ENGINES}",
                stage="engine_validation",
            )

        # 2. Provider解決 — **AIRouter経由**
        # (FORGE-AI-FOUNDATION-010 Phase B、2026-08-13)。
        #
        # 以前はここで`ProviderRouter.resolve()`を直接呼んでおり、
        # `/generate`・`/generate/confirm`・`/converse`のBUILD経路は
        # **Routerを一度も通っていなかった**。Quota切れのfallbackも
        # Circuit Breakerも、製品の主要生成経路には効いていなかった
        # ——「基盤はあるのに製品では使っていない」の3例目である。
        #
        # `provider`が明示されている場合だけ、その名前が実在するかを
        # 先に検証する(既存契約: 未登録名は`ProviderError`)。
        #
        # **`resolve()`ではなく`is_registered()`を使う**。名前の確認に
        # Adapterを取り出す必要は無く、取り出してしまうと「確認しただけ」
        # と「Routerを迂回してAIを呼んだ」がコード上区別できなくなる
        # (Anti-Bypass Regressionが誤検知する。実際に誤検知させて
        # 気付いた)。
        if provider is not None and not self._provider_router.is_registered(provider):
            raise ProviderError(
                f"Provider '{provider}' is not registered. "
                f"Available: {', '.join(self._provider_router.available_providers())}",
                sub_reason="unavailable",
                stage="provider_resolution",
            )

        bound = self.ai_router.bind(ForgeTask.COGNITIVE_STAGE, provider=provider)
        bridge = ForgeAIProviderBridge(bound)

        # 実際に応答を返したProvider名は**実行後**にしか分からない。
        # 明示指定が無い場合、ここで名前を確定させない
        # (`_provider_used()`が実行後の事実を読む)。
        def _provider_used() -> str:
            """実際に応答を返したProvider名。

            `"none"`は「**まだ一度もAIを呼んでいない**」という事実である
            (Ambiguity Detectionのような決定的な段階だけで確認要求へ
            抜けた場合に起きる)。以前ここは「既定として選ばれるはずの
            名前」を返しており、AIを呼んでいなくても`"mock"`と報告して
            いた。呼んでいないなら、呼んでいないと言う。
            """
            return bound.last_provider_used or provider or "none"

        # 3. M004 run_cognitive_pipeline()を1回だけ呼ぶ(個別コンポーネントは
        # 呼ばない、Blueprint v1.3 Task1.2)。`CognitiveOrchestrator`は
        # `NotImplementedError`を意図的に捕捉せず伝播させるため
        # (Blueprint 6.2節)、ここでの捕捉は既存の挙動と同じ。
        try:
            outcome = run_cognitive_pipeline(
                natural_language,
                bridge,
                clarification_answers=clarification_answers,
                # FORGE-HANDOFF-LOCAL-AI-UX-004(2026-08-13): `/converse`が
                # ユーザー自身の短い言葉を渡す。アプリのタイトルを
                # `build_brief`(説明文)ではなくユーザーの言葉から導出する
                # ため(`forge_ai.core.pipeline.run_cognitive_pipeline()`の
                # docstring参照)。`None`の場合は従来どおりの挙動。
                title_seed=title_seed,
            )
        except NoProviderAvailableError as exc:
            # Routerが候補を使い切った(枠切れ・Circuit Breaker・鍵なし・
            # 未実装スタブ等)。**理由込みで**伝える(§33)。ここでMockへ
            # 倒して偽のToolを作らない。
            #
            # `stage`を2つに分けているのは、**起きたことが違う**ため:
            #
            # * `provider`明示あり → その1つを呼んで失敗した。以前
            #   (Router導入前)は`NotImplementedError`として
            #   `forge_ir_compilation`を返していた経路であり、
            #   同じ意味の失敗なのでstageも保つ(既存契約)。
            # * `provider`指定なし → 候補を選ぶ段階で全滅した。
            #   IRの生成には一度も到達していない。
            stage = "forge_ir_compilation" if provider is not None else "provider_resolution"
            raise ProviderError(str(exc), sub_reason="unavailable", stage=stage) from exc
        except NotImplementedError as exc:
            # Mock以外の未実装Providerを実際に呼んだ場合、ここでNotImplementedErrorが
            # 発生する(foundation/providers.pyの_UnimplementedProvider)。
            raise ProviderError(str(exc), sub_reason="unavailable", stage="forge_ir_compilation") from exc
        except Exception as exc:  # noqa: BLE001 — 意図的な、分類のための最終防波堤
            raise PlanningError(
                f"run_cognitive_pipeline()が失敗しました: {exc}", stage="cognitive_pipeline_execution"
            ) from exc

        # 4. Outcome分岐
        if isinstance(outcome, CognitivePipelineNeedsConfirmation):
            request = outcome.confirmation_request
            partial = outcome.partial_context
            # FORGE v0.2 P1 4章「Diagnosticsを失わない」対応: ambiguity_report・
            # domain_classificationは、到達した段階までに実際に埋まっている
            # ものだけをそのまま返す(未到達の段階はNoneのまま、捏造しない)。
            return PipelineNeedsConfirmationResult(
                reason=request.reason,
                message=request.message,
                open_questions=request.open_questions,
                reached_stage=outcome.reached_stage,
                engine_used=engine,
                provider_used=_provider_used(),
                requested_provider=provider,
                decision_trace=_decision_trace_to_dicts(outcome.decision_trace),
                ambiguity_report=_ambiguity_report_to_dict(partial.ambiguity_report) if partial is not None else None,
                domain_classification=(
                    _domain_classification_to_dict(partial.domain_classification) if partial is not None else None
                ),
                injection_report=injection_report,
            )

        if isinstance(outcome, CognitivePipelineFailed):
            raise PlanningError(
                f"Cognitive Pipelineが段階'{outcome.reached_stage}'で失敗しました: {outcome.error.message}",
                stage=outcome.reached_stage,
            )

        assert isinstance(outcome, CognitivePipelineSuccess)  # noqa: S101 — 3型Unionの網羅性を明示

        # 5. IRをdict化
        current_ir = outcome.ir
        forge_document = current_ir.to_json_dict()
        context = outcome.context

        # 6. Validator(1回目)
        validation = validate_forge_document(forge_document)

        # 7/8. 不合格時Repair、再Validation(最大 self._max_repair_attempts 回)
        # Schema Repair Loopは、Cognitive Revision Loop(context.revision_attempt、
        # Design Criticの指摘に基づくApplicationPlanの修正)とは完全に独立した
        # カウンタである(共通指示書6.5節・M005 D59「二重ループ問題」の教訓)。
        repair_attempts = 0
        while not validation.valid and repair_attempts < self._max_repair_attempts:
            issues = to_repair_issues(validation)
            if not issues:
                # blockingなエラーが無い(warningのみ)場合、Repairしても
                # 直せるものが無い。無限に回さず打ち切る。
                break
            repair_attempts += 1
            # ADR 2.4節「二重ループ問題」への対応: max_iterations=1で構築し、
            # このwhileループだけがリトライ回数を制御する。
            repair_engine = RepairEngine(bridge, max_iterations=1)
            forge_ai_repair_result = repair_engine.repair(current_ir, issues)
            to_backend_repair_result(forge_ai_repair_result, repair_attempts)  # 診断用途
            current_ir = forge_ai_repair_result.ir
            forge_document = current_ir.to_json_dict()
            validation = validate_forge_document(forge_document)

        # 9. Repair後Quality再評価 / CriticResult変換
        critic_result: CriticResult | None = None
        if validation.valid:
            if repair_attempts > 0:
                # Repairが発生した場合、outcome.initial_qualityは修正前のIRに
                # 対する評価のままなので古い(ADR 2.5節)。再評価する。
                quality_score = QualityEngine().evaluate(current_ir, context.plan)
            else:
                quality_score = outcome.initial_quality
            # FORGE_v0.2_修正指示.md P1 6章対応(「100点乱発は禁止」):
            # `context.critic_report`(Design Critic、coverage_ratioを持つ)を
            # 実際に渡す。以前は`to_critic_result()`側に対応するロジックが
            # 実装されていたにもかかわらず、この呼び出し箇所が引数を渡して
            # いなかったため、実際には一度も機能していなかった
            # (実行して確認: 引数無しの場合、単純な入力でscore=100が
            # 返り続けることを確認した上で、この行を修正した)。
            critic_result = to_critic_result(quality_score, critic_report=context.critic_report)
        else:
            raise ForgeValidationError(
                f"Repair({repair_attempts}回)後もValidatorに合格しませんでした。",
                validation_errors=tuple(e.to_dict() for e in validation.errors),
                stage="validation",
            )

        # 10. Diagnostics作成(2.1・2.2節の変換は診断・ログ用途のみ、M004内部は駆動しない)
        intent_ir = intent_ir_from_forge_ai_intent(context.intent)
        plan_conversion = plan_ir_from_application_plan(context.plan, context.intent)
        # FORGE-AI-CONNECT-001 TD20対応(2026-08-11): 最終Forge Document
        # (Repair後の確定版)に対して実行する。検出のみ、ブロックはしない。
        safety_result = OutputSafetyChecker().check(forge_document)
        safety_report = {
            "safe": safety_result.safe,
            "issues": [
                {
                    "path": i.path,
                    "category": i.category,
                    "severity": i.severity,
                    "matched_phrase": i.matched_phrase,
                    "message": i.message,
                }
                for i in safety_result.issues
            ],
        }
        diagnostics = Diagnostics(
            engine_used=engine,
            provider_used=_provider_used(),
            repair_attempts=repair_attempts,
            intent_ir=_intent_ir_to_dict(intent_ir),
            plan_ir=_plan_ir_to_dict(plan_conversion.plan_ir),
            conversion_warnings=plan_conversion.warnings,
            cognitive_revision_attempts=context.revision_attempt,
            ambiguity_report=_ambiguity_report_to_dict(context.ambiguity_report),
            domain_classification=_domain_classification_to_dict(context.domain_classification),
            decision_trace=_decision_trace_to_dicts(context.decision_trace),
            injection_report=injection_report,
            safety_report=safety_report,
        )

        # 11. 結果返却
        return PipelineRunResult(
            forge_document=forge_document,
            validation=validation,
            quality=critic_result,
            diagnostics=diagnostics,
        )


def _intent_ir_to_dict(intent_ir: Any) -> dict[str, Any]:
    """診断表示用の簡易シリアライズ(dataclassのフィールドをそのままdict化)。
    Enumはvalueへ変換する。"""
    result = {}
    for key, value in vars(intent_ir).items():
        result[key] = value.value if hasattr(value, "value") else value
    return result


def _plan_ir_to_dict(plan_ir: Any) -> dict[str, Any]:
    """診断表示用の簡易シリアライズ。"""
    return {
        "screens": [vars(s) for s in plan_ir.screens],
        "navigation_edges": list(plan_ir.navigation_edges),
        "template_hint": plan_ir.template_hint,
        "unassigned_actions": list(plan_ir.unassigned_actions),
        # FORGE-AI-CONNECT-001 TD22対応(2026-08-11)。
        "schema_version": plan_ir.schema_version,
    }
