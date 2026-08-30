from __future__ import annotations

import pytest

from forge_ai.core.orchestration.capability_gate import (
    CapabilityGapError,
    require_explicit_checklist,
)
from forge_ai.core.semantics.capability_plan import CapabilityPlan, StructuralMode
from forge_ai.core.semantics.roles import extract_semantic_roles


def _plan(structure: StructuralMode) -> CapabilityPlan:
    return CapabilityPlan(
        roles=extract_semantic_roles(""),
        structure=structure,
        entity_name="task" if structure is StructuralMode.CHECKLIST else "",
        entity_label="やること" if structure is StructuralMode.CHECKLIST else "",
    )


def test_explicit_checklist_is_allowed() -> None:
    require_explicit_checklist(_plan(StructuralMode.CHECKLIST))


def test_unknown_structure_is_not_rewritten_as_checklist() -> None:
    with pytest.raises(CapabilityGapError) as exc_info:
        require_explicit_checklist(_plan(StructuralMode.UNKNOWN))

    assert exc_info.value.stage == "capability_gap"
    assert "semantic_structure_unresolved" in str(exc_info.value)


def test_record_entity_failure_is_not_rewritten_as_checklist() -> None:
    with pytest.raises(CapabilityGapError):
        require_explicit_checklist(_plan(StructuralMode.RECORD_ENTITY))
