from __future__ import annotations

from forge_ai.core.orchestration.extension_plan import (
    ExtensionRoute,
    plan_extension_candidate,
    plan_extension_candidates,
)


def test_implemented_capability_routes_to_composition() -> None:
    candidate = plan_extension_candidate("data.number")
    assert candidate.routes == (ExtensionRoute.COMPOSITION,)
    assert candidate.requires_confirmation is False


def test_missing_safe_view_keeps_declarative_and_build_time_open() -> None:
    candidate = plan_extension_candidate("view.map")
    assert candidate.routes == (
        ExtensionRoute.DECLARATIVE,
        ExtensionRoute.BUILD_TIME,
    )
    assert candidate.requires_confirmation is False


def test_sensitive_effect_requires_confirmation_and_managed_routes() -> None:
    candidate = plan_extension_candidate("effect.http")
    assert candidate.routes == (
        ExtensionRoute.SERVICE,
        ExtensionRoute.NATIVE_PRIVILEGED,
        ExtensionRoute.BUILD_TIME,
    )
    assert candidate.requires_confirmation is True


def test_unknown_internal_id_is_not_relabelled_as_product_missing() -> None:
    candidate = plan_extension_candidate("view.typo_does_not_exist")
    assert candidate.routes == (ExtensionRoute.NEEDS_DECOMPOSITION,)
    assert candidate.support is None


def test_candidates_are_deduplicated_without_reordering() -> None:
    candidates = plan_extension_candidates(("view.map", "effect.http", "view.map"))
    assert [candidate.capability_id for candidate in candidates] == ["view.map", "effect.http"]
