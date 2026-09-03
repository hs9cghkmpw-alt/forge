from __future__ import annotations

from dataclasses import replace

import pytest

from forge_ai.core.orchestration.extension_manifest import (
    ExtensionEvidence,
    ExtensionStatus,
    create_extension_manifest,
)
from forge_ai.core.orchestration.extension_plan import (
    ExtensionRoute,
    plan_extension_candidate,
)


def _complete_evidence(
    *,
    safety_review: bool = False,
    sandbox_preflight: bool = False,
) -> ExtensionEvidence:
    return ExtensionEvidence(
        semantic_decomposition=True,
        reusable_primitive=True,
        language_binding=True,
        validator_binding=True,
        runtime_binding=True,
        compiler_binding=True,
        tests_pass=True,
        build_pass=True,
        runtime_evidence=True,
        sandbox_preflight=sandbox_preflight,
        safety_review=safety_review,
    )


def test_missing_view_cannot_be_promoted_from_generated_manifest_alone() -> None:
    candidate = plan_extension_candidate("view.map")
    manifest = create_extension_manifest(candidate, ExtensionRoute.BUILD_TIME)

    assert manifest.status is ExtensionStatus.DRAFT
    assert not manifest.can_promote
    assert "runtime_binding" in manifest.promotion_blockers()
    assert "runtime_evidence" in manifest.promotion_blockers()
    assert "sandbox_preflight" in manifest.promotion_blockers()

    with pytest.raises(ValueError, match="complete evidence"):
        manifest.verified()


def test_build_time_capability_needs_sandbox_even_if_all_old_gates_are_green() -> None:
    candidate = plan_extension_candidate("view.map")
    manifest = create_extension_manifest(candidate, ExtensionRoute.BUILD_TIME)
    manifest = replace(manifest, evidence=_complete_evidence(sandbox_preflight=False))

    assert manifest.promotion_blockers() == ("sandbox_preflight",)
    with pytest.raises(ValueError, match="sandbox_preflight"):
        manifest.verified()


def test_safe_capability_can_promote_only_after_full_reusable_evidence() -> None:
    candidate = plan_extension_candidate("view.map")
    manifest = create_extension_manifest(candidate, ExtensionRoute.BUILD_TIME)
    manifest = replace(
        manifest,
        evidence=_complete_evidence(sandbox_preflight=True),
    )

    verified = manifest.verified()
    promoted = verified.promoted()

    assert verified.status is ExtensionStatus.VERIFIED
    assert promoted.status is ExtensionStatus.PROMOTED


def test_sensitive_effect_requires_safety_review_in_addition_to_runtime_proof() -> None:
    candidate = plan_extension_candidate("effect.http")
    manifest = create_extension_manifest(candidate, ExtensionRoute.SERVICE)
    manifest = replace(manifest, evidence=_complete_evidence(safety_review=False))

    assert manifest.promotion_blockers() == ("safety_review",)
    with pytest.raises(ValueError, match="safety_review"):
        manifest.verified()

    manifest = replace(manifest, evidence=_complete_evidence(safety_review=True))
    assert manifest.verified().promoted().status is ExtensionStatus.PROMOTED


def test_unresolved_semantic_gap_cannot_skip_decomposition() -> None:
    candidate = plan_extension_candidate("semantic_structure_unresolved")
    assert candidate.routes == (ExtensionRoute.NEEDS_DECOMPOSITION,)

    with pytest.raises(ValueError, match="decomposed"):
        create_extension_manifest(candidate, ExtensionRoute.NEEDS_DECOMPOSITION)


def test_route_must_be_allowed_by_candidate() -> None:
    candidate = plan_extension_candidate("view.map")
    with pytest.raises(ValueError, match="not permitted"):
        create_extension_manifest(candidate, ExtensionRoute.SERVICE)