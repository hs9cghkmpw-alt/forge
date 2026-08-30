from __future__ import annotations

import pytest

from forge_ai.core.orchestration.capability_gate import (
    CapabilityGapError,
    require_explicit_checklist,
)
from forge_ai.core.orchestration.extension_plan import ExtensionRoute
from forge_ai.core.semantics.capability_plan import CapabilityPlan, StructuralMode
from forge_ai.core.semantics.roles import extract_semantic_roles


def _plan(structure: StructuralMode, *, missing: tuple[str, ...] = ()) -> CapabilityPlan:
    return CapabilityPlan(
        roles=extract_semantic_roles(""),
        structure=structure,
        entity_name="task" if structure is StructuralMode.CHECKLIST else "",
        entity_label="やること" if structure is StructuralMode.CHECKLIST else "",
        missing=missing,
    )


def test_explicit_checklist_is_allowed() -> None:
    require_explicit_checklist(_plan(StructuralMode.CHECKLIST))


def test_unknown_structure_is_not_rewritten_as_checklist() -> None:
    with pytest.raises(CapabilityGapError) as exc_info:
        require_explicit_checklist(_plan(StructuralMode.UNKNOWN))

    error = exc_info.value
    assert error.stage == "capability_gap"
    assert "semantic_structure_unresolved" in str(error)
    assert error.extension_candidates[0].capability_id == "semantic_structure_unresolved"
    assert error.extension_candidates[0].routes == (ExtensionRoute.NEEDS_DECOMPOSITION,)


def test_known_missing_capability_becomes_structured_extension_candidate() -> None:
    with pytest.raises(CapabilityGapError) as exc_info:
        require_explicit_checklist(
            _plan(StructuralMode.RECORD_ENTITY, missing=("view.map",))
        )

    candidate = exc_info.value.extension_candidates[0]
    assert candidate.capability_id == "view.map"
    assert candidate.routes == (
        ExtensionRoute.DECLARATIVE,
        ExtensionRoute.BUILD_TIME,
    )


def test_sensitive_effect_gap_preserves_confirmation_requirement() -> None:
    with pytest.raises(CapabilityGapError) as exc_info:
        require_explicit_checklist(
            _plan(StructuralMode.RECORD_ENTITY, missing=("effect.http",))
        )

    candidate = exc_info.value.extension_candidates[0]
    assert candidate.requires_confirmation is True
    assert ExtensionRoute.SERVICE in candidate.routes
    assert ExtensionRoute.NATIVE_PRIVILEGED in candidate.routes


def test_record_entity_failure_is_not_rewritten_as_checklist() -> None:
    with pytest.raises(CapabilityGapError):
        require_explicit_checklist(_plan(StructuralMode.RECORD_ENTITY))
