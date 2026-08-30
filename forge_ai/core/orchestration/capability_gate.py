"""Fail-closed gate between capability planning and legacy document compilation.

Whole Scan 2026-08-30 found that the cognitive pipeline could reach the legacy
Checklist compiler whenever entity construction/synthesis returned no IR.  That
made an *unresolved structure* look like a valid checklist merely because the
checklist compiler was available.

Forge's product rule is stricter: existing capabilities may be composed, but a
missing/unresolved capability must stay explicit until it is generated or the
request fails truthfully.  A legacy compiler may therefore be used only when
the semantic CapabilityPlan itself explicitly asks for CHECKLIST.

A truthful failure is not the end state.  Known missing capability IDs are also
translated into structured ExtensionCandidates so the next self-extension loop
can choose a managed implementation route without re-parsing an error string.
"""

from __future__ import annotations

from forge_ai.core.orchestration.errors import PlanningError
from forge_ai.core.orchestration.extension_plan import (
    ExtensionCandidate,
    ExtensionRoute,
    plan_extension_candidates,
)
from forge_ai.core.semantics.capability_plan import CapabilityPlan, StructuralMode


class CapabilityGapError(PlanningError):
    """The requested structure cannot be represented by current capabilities."""

    def __init__(
        self,
        message: str,
        *,
        stage: str,
        extension_candidates: tuple[ExtensionCandidate, ...] = (),
    ) -> None:
        super().__init__(message, stage=stage)
        self.extension_candidates = extension_candidates


def require_explicit_checklist(plan: CapabilityPlan) -> None:
    """Allow the legacy checklist compiler only for an explicit checklist plan.

    This intentionally does *not* reinterpret UNKNOWN or RECORD_ENTITY as a
    checklist.  The caller may attempt synthesis/extension first; if it still
    arrives here without an IR, the unresolved semantic requirement is a
    capability gap, not a template-selection opportunity.
    """
    if plan.structure is StructuralMode.CHECKLIST:
        return

    if plan.missing:
        candidates = plan_extension_candidates(plan.missing)
        missing = ", ".join(plan.missing)
    else:
        # UNKNOWN structure means semantic decomposition itself is incomplete;
        # do not fabricate a capability ID.  Keep that fact structured too.
        candidates = (
            ExtensionCandidate(
                capability_id="semantic_structure_unresolved",
                label_ja="要求構造の分解が未完了",
                support=None,
                safety=None,
                routes=(ExtensionRoute.NEEDS_DECOMPOSITION,),
                reason="No exact missing capability ID is known yet; decompose the user need before implementation.",
                requires_confirmation=False,
            ),
        )
        missing = "semantic_structure_unresolved"

    raise CapabilityGapError(
        "Capability Plan could not produce the requested structure; refusing "
        f"legacy checklist substitution ({missing}).",
        stage="capability_gap",
        extension_candidates=candidates,
    )
