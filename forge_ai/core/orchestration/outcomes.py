"""CognitivePipelineOutcome(FORGE-MILESTONE-007第一段階)。

`docs/spec/FORGE_M007_IMPLEMENTATION_BLUEPRINT.md` v1.3 Task3.5に対応。

**重要**: `CognitivePipelineOutcome`はUnion型エイリアスであり、クラスでは
ない。`CognitivePipelineOutcome.success(...)`のような呼び出しは型として
成立しない(Union型エイリアスはメソッドを持たない)。対応する具体的な
dataclassを直接構築すること。
"""

from __future__ import annotations

from dataclasses import dataclass

from forge_ai.core.compiler import ForgeIRDocument
from forge_ai.core.orchestration.cognitive_context import CognitiveContext
from forge_ai.core.orchestration.cognitive_types import ConfirmationRequest, DecisionTrace
from forge_ai.core.orchestration.errors import CognitiveError, PlanningError
from forge_ai.quality.quality_engine import QualityScore


@dataclass(frozen=True)
class CognitivePipelineSuccess:
    """Forge IR Compilation・Initial Quality Evaluationまで完了した場合。

    `context`が既に保持している情報(intent・domain_classification・
    world・requirements・plan・template_selection・critic_report等)を
    個別フィールドとして重複保持しない(Contextとの不一致を防ぐため、
    Blueprint 3.5節)。`ir`・`initial_quality`はContextに含めていない
    情報なので、ここでのみ保持する。
    """

    context: CognitiveContext
    ir: ForgeIRDocument
    initial_quality: QualityScore


@dataclass(frozen=True)
class CognitivePipelineNeedsConfirmation:
    """いずれかの段階でHuman Confirmation/Escalationが必要と判断された場合。
    domain/world/plan等の一部または全部が存在しない可能性があるため、
    これらをOptionalにする、あるいはダミー値で埋めることはしない。"""

    confirmation_request: ConfirmationRequest
    reached_stage: str
    partial_context: CognitiveContext
    decision_trace: tuple[DecisionTrace, ...]


@dataclass(frozen=True)
class CognitivePipelineFailed:
    """回復不能な失敗。"""

    error: CognitiveError
    reached_stage: str
    decision_trace: tuple[DecisionTrace, ...]


CognitivePipelineOutcome = (
    CognitivePipelineSuccess | CognitivePipelineNeedsConfirmation | CognitivePipelineFailed
)


_REQUIRED_FIELDS_FOR_SUCCESS = (
    "intent",
    "domain_classification",
    "world",
    "meaning",
    "requirements",
    "preliminary_candidates",
    "plan",
    "template_selection",
    "critic_report",
)
# FORGE-MILESTONE-007 Phase 1.2でMeaning Modelを正式接続したため、
# Blueprint v1.3 Task3.5本来の9項目(meaningを含む)へ復元した
# (Phase 1ではMeaning Model未実装のため8項目だった)。


def assert_context_ready_for_success(context: CognitiveContext) -> None:
    """`CognitivePipelineSuccess`を構築する前提条件を検証する
    (Blueprint 3.5節)。満たされていない場合は`PlanningError`を送出する
    (プログラミングエラーの早期検出。通常の実行パスでは到達しないはず)。
    """
    missing = [f for f in _REQUIRED_FIELDS_FOR_SUCCESS if getattr(context, f) is None]
    if missing:
        raise PlanningError(
            f"CognitivePipelineSuccess構築の前提条件を満たしていません。未設定: {missing}",
            stage="internal_consistency_check",
        )
