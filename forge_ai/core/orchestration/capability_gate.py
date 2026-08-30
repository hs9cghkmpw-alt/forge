"""Fail-closed gate between capability planning and legacy document compilation.

Whole Scan 2026-08-30 found that the cognitive pipeline could reach the legacy
Checklist compiler whenever entity construction/synthesis returned no IR.  That
made an *unresolved structure* look like a valid checklist merely because the
checklist compiler was available.

Forge's product rule is stricter: existing capabilities may be composed, but a
missing/unresolved capability must stay explicit until it is generated or the
request fails truthfully.  A legacy compiler may therefore be used only when
the semantic CapabilityPlan itself explicitly asks for CHECKLIST.
"""

from __future__ import annotations

from forge_ai.core.orchestration.errors import PlanningError
from forge_ai.core.semantics.capability_plan import CapabilityPlan, StructuralMode


class CapabilityGapError(PlanningError):
    """The requested structure cannot be represented by current capabilities."""


def require_explicit_checklist(plan: CapabilityPlan) -> None:
    """Allow the legacy checklist compiler only for an explicit checklist plan.

    This intentionally does *not* reinterpret UNKNOWN or RECORD_ENTITY as a
    checklist.  The caller may attempt synthesis/extension first; if it still
    arrives here without an IR, the unresolved semantic requirement is a
    capability gap, not a template-selection opportunity.
    """
    if plan.structure is StructuralMode.CHECKLIST:
        return

    missing = ", ".join(plan.missing) if plan.missing else "semantic_structure_unresolved"
    raise CapabilityGapError(
        "Capability Plan could not produce the requested structure; refusing "
        f"legacy checklist substitution ({missing}).",
        stage="capability_gap",
    )
