from __future__ import annotations

from dataclasses import dataclass, replace

import pytest

from forge_ai.core.orchestration.extension_manifest import ExtensionEvidence, create_extension_manifest
from forge_ai.core.orchestration.extension_plan import ExtensionCandidate, ExtensionRoute
from forge_ai.core.orchestration.extension_registry import PROMOTED_CAPABILITIES
from forge_ai.core.semantics.capabilities import SafetyClass, SupportLevel
from forge_ai.core.semantics.capability_plan import _classify


@dataclass(frozen=True)
class _Activation:
    capability_id: str


def _promoted_manifest(route: ExtensionRoute = ExtensionRoute.DECLARATIVE):
    candidate = ExtensionCandidate(
        capability_id="interact.filter", label_ja="絞り込む",
        support=SupportLevel.MISSING, safety=SafetyClass.SAFE,
        routes=(ExtensionRoute.DECLARATIVE, ExtensionRoute.BUILD_TIME),
        reason="test", requires_confirmation=False,
    )
    manifest = create_extension_manifest(candidate, route)
    evidence = ExtensionEvidence(
        semantic_decomposition=True, reusable_primitive=True, language_binding=True,
        validator_binding=True, runtime_binding=True, compiler_binding=True,
        tests_pass=True, build_pass=True, runtime_evidence=True,
    )
    return replace(manifest, evidence=evidence).verified().promoted()


def test_promoted_declarative_capability_changes_effective_support_for_retry() -> None:
    PROMOTED_CAPABILITIES.clear()
    before_ok, _, before_missing = _classify({"interact.filter"})
    assert before_ok == ()
    assert before_missing == ("interact.filter",)

    PROMOTED_CAPABILITIES.install(_promoted_manifest(), _Activation("interact.filter"))
    after_ok, after_partial, after_missing = _classify({"interact.filter"})
    assert after_ok == ("interact.filter",)
    assert after_partial == ()
    assert after_missing == ()


def test_metadata_only_promoted_manifest_cannot_change_effective_support() -> None:
    PROMOTED_CAPABILITIES.clear()
    with pytest.raises(ValueError, match="no executable activation"):
        PROMOTED_CAPABILITIES.install(_promoted_manifest(), None)
    ok, _, missing = _classify({"interact.filter"})
    assert ok == ()
    assert missing == ("interact.filter",)


def test_unverified_manifest_cannot_enter_promoted_registry() -> None:
    PROMOTED_CAPABILITIES.clear()
    candidate = ExtensionCandidate(
        capability_id="interact.filter", label_ja="絞り込む",
        support=SupportLevel.MISSING, safety=SafetyClass.SAFE,
        routes=(ExtensionRoute.DECLARATIVE,), reason="test", requires_confirmation=False,
    )
    with pytest.raises(ValueError, match="Only PROMOTED"):
        PROMOTED_CAPABILITIES.install(
            create_extension_manifest(candidate, ExtensionRoute.DECLARATIVE),
            _Activation("interact.filter"),
        )


def test_activation_identity_must_match_manifest() -> None:
    PROMOTED_CAPABILITIES.clear()
    with pytest.raises(ValueError, match="Activation changed capability identity"):
        PROMOTED_CAPABILITIES.install(_promoted_manifest(), _Activation("view.map"))


def test_build_time_manifest_cannot_claim_in_process_activation() -> None:
    PROMOTED_CAPABILITIES.clear()
    with pytest.raises(ValueError, match="cannot be activated in-process"):
        PROMOTED_CAPABILITIES.install(
            _promoted_manifest(ExtensionRoute.BUILD_TIME),
            _Activation("interact.filter"),
        )
