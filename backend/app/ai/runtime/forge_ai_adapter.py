"""M004(forge_ai/)↔M005(backend/app/ai/runtime/)Adapter。

`docs/spec/ADAPTER_CONTRACT_V1.md`(v1.1、CEO実コード監査済み)の
2章(Shared Types)を実装したもの。ここで定義する関数は、いずれも
**forge_ai.core.pipeline.run_pipeline()が返す`PipelineResult`を
「事後的に」診断・ログ用途へ変換するためのものであり、M004内部の
処理(Meaning→Intent→Plan→Compile)を駆動するためのものではない**
(ADR 1.1節「粗粒度Facade」の原則)。

このファイルは、Intent/Plan/RepairIssue/RepairResult/Quality という
forge_ai/の型を直接importする(型変換が責務のため)。ADR 1.2節
「M004呼び出し規則」により、`prompt_pipeline.py`も`run_pipeline`・
`RepairEngine`・`QualityEngine`の3つに限り直接importが許可されている
(このファイルだけがforge_aiをimportするわけではない。CEO実物監査により
訂正)。禁止されているのはMeaningExtractor/IntentBuilder/Planner/
Compilerの個別呼び出しであり、この2ファイルからもimportしていない。
"""

from __future__ import annotations

from dataclasses import dataclass

from forge_ai.core.compiler import ForgeIRDocument
from forge_ai.core.intent_model import Intent as ForgeAIIntent
from forge_ai.core.orchestration.cognitive_types import CriticReport
from forge_ai.core.planner import ApplicationPlan
from forge_ai.quality.quality_engine import QualityScore
from forge_ai.repair.repair_engine import RepairIssue as ForgeAIRepairIssue
from forge_ai.repair.repair_engine import RepairResult as ForgeAIRepairResult

from app.ai.foundation.interfaces import Complexity, CriticResult, IntentIR, Platform, PlanIR
from app.ai.foundation.interfaces import ScreenPlan as BackendScreenPlan
from app.ai.runtime.repair import RepairResult as BackendRepairResult
from app.ai.validators.schema_validator import ValidationResult


# ADAPTER_CONTRACT_V1.md 2.2節(CEO指摘5)への対応: 画面表現概念(UIの部品を
# 指す語)らしいキーワードの簡易リスト。ここに一致した`key_element`は
# データ実体として扱わない(`data_needed`に入れない)。
#
# 既知の制限: 単純な部分一致による簡易ヒューリスティックであり、完全ではない
# (ADAPTER_CONTRACT_V1.md 2.2節が要求する「3分類」の最初の実装)。
_PRESENTATION_KEYWORDS: tuple[str, ...] = (
    "検索", "search", "フィルタ", "filter", "ボタン", "button",
    "画面", "screen", "タブ", "tab", "メニュー", "menu",
    "確認", "確認画面", "ダイアログ", "dialog",
)


def _looks_like_presentation_concept(key_element: str) -> bool:
    lowered = key_element.lower()
    return any(keyword in lowered for keyword in _PRESENTATION_KEYWORDS)


def intent_ir_from_forge_ai_intent(
    intent: ForgeAIIntent,
    *,
    platform: Platform = Platform.CROSS_PLATFORM,
    target_users: tuple[str, ...] = (),
    open_questions: tuple[str, ...] = (),
    privacy_notes: tuple[str, ...] = (),
    accessibility_notes: tuple[str, ...] = (),
    complexity: Complexity = Complexity.SIMPLE,
    category: str | None = None,
    output_type: str | None = None,
) -> IntentIR:
    """`ADAPTER_CONTRACT_V1.md` 2.1節。診断・ログ用途のみ(M004内部の
    処理は駆動しない、ADR 1.1節参照)。

    `target_users`・`open_questions`・`privacy_notes`・
    `accessibility_notes`・`platform`・`complexity`・`category`・
    `output_type`はforge_ai.Intentには情報が無いため、呼び出し側
    (HTTPリクエストのgeneration_options等)から明示的に渡す
    (ADR 6.1節PROVISIONAL、実装時点でも「どこから補うか」の自動化は
    まだ行わない)。
    """
    return IntentIR(
        purpose=intent.goal,
        target_users=target_users,
        required_features=intent.required_actions,
        constraints=intent.constraints,
        open_questions=open_questions,
        privacy_notes=privacy_notes,
        accessibility_notes=accessibility_notes,
        entities=intent.required_concepts,
        platform=platform,
        complexity=complexity,
        category=category,
        output_type=output_type,
    )


@dataclass(frozen=True)
class PlanConversionResult:
    """`plan_ir_from_application_plan()`の戻り値(CEO実物監査対応)。

    以前は`unclassified_diagnostics`(presentation conceptと判定されて
    `data_needed`から除外された要素の記録)を変数として作るだけで、
    どこにも返さず・使わずに捨てていた。この結果型で、変換後の`PlanIR`と
    変換時に生じた警告を一緒に返す(HTTPレスポンスの`diagnostics.
    conversion_warnings`まで到達させる、`prompt_pipeline.py`参照)。
    """

    plan_ir: PlanIR
    warnings: tuple[str, ...]


def plan_ir_from_application_plan(plan: ApplicationPlan, intent: ForgeAIIntent) -> PlanConversionResult:
    """`ADAPTER_CONTRACT_V1.md` 2.2節。診断・ログ用途のみ。

    CEO指摘4(actions_needed=()固定でIntent.required_actionsを失う)・
    指摘5(key_elementsを無条件でdata_neededへ写す)への対応を含む。
    戻り値は`PlanConversionResult`(CEO実物監査対応。以前は`PlanIR`を
    直接返し、分類時の警告を捨てていた)。

    `intent`を明示的に受け取るのは、`ApplicationPlan`自体には
    (現状のforge_ai.Planner実装では)`required_actions`に相当する
    情報が伝播していないため。これはforge_ai.Plannerの既知の制限であり、
    今回のTaskでforge_ai/側を変更することはしない(Adapter側で
    Intentから直接補う)。
    """
    backend_screens: list[BackendScreenPlan] = []
    warnings: list[str] = []

    for screen in plan.screens:
        data_needed: list[str] = []
        for element in screen.key_elements:
            if _looks_like_presentation_concept(element):
                # データ実体として扱わない。今回は`presentation_hints`
                # フィールドを追加しない(指示書「presentation_hintsは
                # 今回追加しない」)ため、変換警告として返す
                # (CEO実物監査対応。以前はここで記録するだけで、
                # 呼び出し元へ一切返していなかった)。
                warnings.append(
                    f"screen={screen.name!r}: '{element}' はpresentation conceptと判定され、data_neededから除外されました。"
                )
            else:
                data_needed.append(element)

        backend_screens.append(
            BackendScreenPlan(
                screen_id=_slugify(screen.name),
                purpose=screen.purpose,
                data_needed=tuple(data_needed),
                actions_needed=(),  # 個別画面への割当はforge_ai.Planner側で未対応(既知のギャップ)
                empty_state_needed=True,
                error_state_needed=True,
            )
        )

    plan_ir = PlanIR(
        screens=tuple(backend_screens),
        navigation_edges=(),  # forge_ai.Plannerは画面間遷移を明示的に計算しない(既知のギャップ)
        template_hint=None,
        unassigned_actions=intent.required_actions,  # 指摘4: 捨てずにPlan全体で保持する
    )
    return PlanConversionResult(plan_ir=plan_ir, warnings=tuple(warnings))




def _slugify(name: str) -> str:
    """screen名から、Forge Languageのidentifier規則
    (^[a-z][a-z0-9_]*$)に近い形のscreen_idを作る簡易実装。
    厳密なidentifier検証はBackend Validator側の責務であり、ここでは
    診断用途として使える程度の変換に留める。"""
    slug = name.strip().lower().replace(" ", "_").replace("-", "_")
    return slug or "screen"


def to_repair_issues(validation_result: ValidationResult) -> tuple[ForgeAIRepairIssue, ...]:
    """`ADAPTER_CONTRACT_V1.md` 2.4節。`ValidationResult.errors`
    (blockingなもの)だけをforge_ai.RepairIssueへ変換する。
    warningsは修正対象にしない(Validatorのblocking/warning区分をそのまま尊重する)。
    """
    return tuple(
        ForgeAIRepairIssue(path=e.path, category=e.category.value, message=e.message)
        for e in validation_result.errors
    )


def to_backend_repair_result(result: ForgeAIRepairResult, attempt: int) -> BackendRepairResult:
    """`ADAPTER_CONTRACT_V1.md` 2.4節。"""
    return BackendRepairResult(
        document=result.ir.to_json_dict(),
        attempt=attempt,
        fixed_issue_count=len(result.fixed_issues),
        remaining_issue_count=len(result.remaining_issues),
        success=len(result.remaining_issues) == 0,
    )


def to_critic_result(
    quality: QualityScore, *, threshold: float = 0.8, critic_report: "CriticReport | None" = None
) -> CriticResult:
    """`ADAPTER_CONTRACT_V1.md` 2.5節。`threshold`(既定0.8)は暫定値であり、
    実際のCritic運用データが無い現時点では根拠のない数値であることを
    明記する(ADR 2.5節と同じ注記)。

    **FORGE_v0.2_修正指示.md P1 6章対応(「100点乱発は禁止」)**:
    以前は`quality`(forge_ai.QualityEngineの6軸、Forge IRの構造的品質
    のみを見る)だけからscoreを算出しており、単純な単一画面アプリでは
    構造的には常に満点に近くなるため、実際には`context.critic_report`
    (Design Critic、14軸中8軸を評価、`coverage_ratio`で「実際に評価
    できた割合」を正直に持つ)が把握している「未評価の観点がある」
    「必須要件が未割当」等の事実が、外部向けscoreへ一切反映されて
    いなかった(実際に実行して確認した: 単純な入力でscore=100・
    release_ready=Trueが常に返ることを確認済み)。

    `critic_report`を渡した場合、`quality.overall`(IR構造品質)と
    `critic_report.coverage_ratio`(Design Criticが実際に評価できた
    観点の割合)を掛け合わせて最終scoreとする。これにより、IR自体は
    構造的に正しくても、Design Criticの評価範囲(8/14軸)が限定的で
    あることが、外部向けscoreにも正直に反映される。`critic_report`が
    `release_ready=False`(mandatory要件未割当等のblocking issueが
    残っている)場合、`quality.overall`が高くても`release_ready`は
    Falseのままにする。`critic_report.issues`もそのまま
    `CriticResult.issues`へ変換する(以前は空のままだった既知のギャップを
    ここで一部解消する)。

    `critic_report`を渡さない場合(後方互換)は、以前と同じ、
    `quality.overall`のみに基づく算出のままとする。
    """
    if critic_report is None:
        return CriticResult(
            score=round(quality.overall * 100),
            release_ready=quality.overall >= threshold,
            issues=(),
            required_fixes=(),
        )

    combined_overall = quality.overall * critic_report.coverage_ratio
    has_blocking_issue = any(issue.severity == "high" for issue in critic_report.issues)
    release_ready = (
        combined_overall >= threshold
        and critic_report.release_ready
        and not has_blocking_issue
    )
    issues = tuple(
        {"severity": issue.severity, "category": issue.category, "description": issue.evidence}
        for issue in critic_report.issues
    )
    required_fixes = tuple(
        issue.recommended_fix for issue in critic_report.issues if issue.recommended_fix
    )
    return CriticResult(
        score=round(combined_overall * 100),
        release_ready=release_ready,
        issues=issues,
        required_fixes=required_fixes,
    )


__all__ = [
    "intent_ir_from_forge_ai_intent",
    "plan_ir_from_application_plan",
    "PlanConversionResult",
    "to_repair_issues",
    "to_backend_repair_result",
    "to_critic_result",
    "ForgeIRDocument",
]
