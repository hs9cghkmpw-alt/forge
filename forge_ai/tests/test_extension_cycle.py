from __future__ import annotations

from forge_ai.tests.promotion_helpers import allowed_decision


def _gate_promote(manifest):
    """本物の Gate を通して PROMOTED にする。"""
    return manifest.promoted(allowed_decision(manifest.capability_id))

from dataclasses import dataclass, replace
from types import SimpleNamespace

import pytest

from forge_ai.core.orchestration.build_time_extension import LoadedBuildActivation
from forge_ai.core.orchestration.extension_activation import ExtensionImplementation
from forge_ai.core.orchestration.extension_cycle import ExtensionCycleError, run_extension_cycle
from forge_ai.core.orchestration.extension_manifest import ExtensionEvidence
from forge_ai.core.orchestration.extension_registry import PROMOTED_CAPABILITIES
from forge_ai.core.orchestration.extension_plan import (
    ExtensionCandidate,
    ExtensionRoute,
)
from forge_ai.core.orchestration.outcomes import CognitivePipelineNeedsExtension
from forge_ai.core.semantics.capabilities import SafetyClass, SupportLevel


@dataclass(frozen=True)
class _Activation:
    capability_id: str


def _candidate(capability_id: str = "view.map") -> ExtensionCandidate:
    return ExtensionCandidate(
        capability_id=capability_id,
        label_ja="地図で見る",
        support=SupportLevel.MISSING,
        safety=SafetyClass.SAFE,
        routes=(ExtensionRoute.DECLARATIVE, ExtensionRoute.BUILD_TIME),
        reason="missing",
        requires_confirmation=False,
    )


def _outcome(candidate: ExtensionCandidate) -> CognitivePipelineNeedsExtension:
    return CognitivePipelineNeedsExtension(
        error=Exception("gap"),
        reached_stage="capability_gap",
        partial_context=SimpleNamespace(raw_input="釣果を地図で見たい"),
        extension_candidates=(candidate,),
        decision_trace=(),
    )


def _promoted_manifest(manifest):
    evidence = ExtensionEvidence(
        semantic_decomposition=True,
        reusable_primitive=True,
        language_binding=True,
        validator_binding=True,
        runtime_binding=True,
        compiler_binding=True,
        tests_pass=True,
        build_pass=True,
        runtime_evidence=True,
        # This helper intentionally synthesizes an already-evidenced manifest.
        # BUILD_TIME now requires sandbox evidence as a lifecycle invariant; the
        # DECLARATIVE route does not claim generated host-code execution.
        sandbox_preflight=manifest.route is ExtensionRoute.BUILD_TIME,
    )
    return _gate_promote(replace(manifest, evidence=evidence).verified())


def _promote_with_activation(manifest):
    promoted = _promoted_manifest(manifest)
    return ExtensionImplementation(promoted, _Activation(promoted.capability_id))


def test_promoted_declarative_extension_is_installed_then_retries_original_request() -> None:
    PROMOTED_CAPABILITIES.clear()
    retried: list[str] = []

    result = run_extension_cycle(
        _outcome(_candidate()),
        decompose=lambda c: c,
        select_route=lambda c: ExtensionRoute.DECLARATIVE,
        implement=_promote_with_activation,
        retry=lambda raw: retried.append(raw) or "RETRIED",  # type: ignore[arg-type,return-value]
    )

    assert result.manifest.status.value == "promoted"
    assert PROMOTED_CAPABILITIES.is_promoted("view.map")
    assert retried == ["釣果を地図で見たい"]
    assert result.retry_outcome == "RETRIED"


def test_metadata_only_promotion_cannot_trigger_retry() -> None:
    PROMOTED_CAPABILITIES.clear()
    retried: list[str] = []

    with pytest.raises(ExtensionCycleError, match="no executable activation"):
        run_extension_cycle(
            _outcome(_candidate()),
            decompose=lambda c: c,
            select_route=lambda c: ExtensionRoute.DECLARATIVE,
            implement=lambda manifest: ExtensionImplementation(_promoted_manifest(manifest), None),
            retry=lambda raw: retried.append(raw) or "RETRIED",  # type: ignore[arg-type,return-value]
        )
    assert retried == []


def test_unverified_extension_cannot_trigger_retry() -> None:
    retried: list[str] = []
    with pytest.raises(ExtensionCycleError, match="not evidence-gated PROMOTED"):
        run_extension_cycle(
            _outcome(_candidate()),
            decompose=lambda c: c,
            select_route=lambda c: ExtensionRoute.DECLARATIVE,
            implement=lambda manifest: ExtensionImplementation(manifest, _Activation(manifest.capability_id)),
            retry=lambda raw: retried.append(raw) or "RETRIED",  # type: ignore[arg-type,return-value]
        )
    assert retried == []


def test_unresolved_semantics_cannot_enter_implementation() -> None:
    unresolved = ExtensionCandidate(
        capability_id="semantic_structure_unresolved",
        label_ja="要求構造の分解が未完了",
        support=None,
        safety=None,
        routes=(ExtensionRoute.NEEDS_DECOMPOSITION,),
        reason="unresolved",
        requires_confirmation=False,
    )
    with pytest.raises(ExtensionCycleError, match="did not resolve"):
        run_extension_cycle(
            _outcome(unresolved),
            decompose=lambda c: c,
            select_route=lambda c: ExtensionRoute.NEEDS_DECOMPOSITION,
            implement=lambda manifest: ExtensionImplementation(manifest, None),
            retry=lambda raw: "RETRIED",  # type: ignore[return-value]
        )


def test_implementer_cannot_swap_capability_identity() -> None:
    with pytest.raises(ExtensionCycleError, match="changed capability identity"):
        run_extension_cycle(
            _outcome(_candidate("view.map")),
            decompose=lambda c: c,
            select_route=lambda c: ExtensionRoute.DECLARATIVE,
            implement=lambda manifest: ExtensionImplementation(
                replace(_promoted_manifest(manifest), capability_id="view.calendar"),
                _Activation("view.calendar"),
            ),
            retry=lambda raw: "RETRIED",  # type: ignore[return-value]
        )


def test_activation_cannot_swap_capability_identity() -> None:
    PROMOTED_CAPABILITIES.clear()
    with pytest.raises(ExtensionCycleError, match="Activation changed capability identity"):
        run_extension_cycle(
            _outcome(_candidate("view.map")),
            decompose=lambda c: c,
            select_route=lambda c: ExtensionRoute.DECLARATIVE,
            implement=lambda manifest: ExtensionImplementation(
                _promoted_manifest(manifest), _Activation("view.calendar")
            ),
            retry=lambda raw: "RETRIED",  # type: ignore[return-value]
        )


def test_build_time_retry_requires_loaded_verified_runtime() -> None:
    PROMOTED_CAPABILITIES.clear()
    retried: list[str] = []

    def implement(manifest):
        promoted = _promoted_manifest(manifest)
        activation = LoadedBuildActivation(
            capability_id=promoted.capability_id,
            build_id="build-1",
            runtime_fingerprint="runtime-1",
            source_digest="digest-1",
        )
        return ExtensionImplementation(promoted, activation)

    result = run_extension_cycle(
        _outcome(_candidate()),
        decompose=lambda c: c,
        select_route=lambda c: ExtensionRoute.BUILD_TIME,
        implement=implement,
        retry=lambda raw: retried.append(raw) or "RETRIED",  # type: ignore[arg-type,return-value]
    )

    assert PROMOTED_CAPABILITIES.is_promoted("view.map")
    assert retried == ["釣果を地図で見たい"]
    assert result.retry_outcome == "RETRIED"


def test_build_time_fake_runtime_activation_cannot_trigger_retry() -> None:
    PROMOTED_CAPABILITIES.clear()
    retried: list[str] = []
    with pytest.raises(ExtensionCycleError, match="loaded build activation"):
        run_extension_cycle(
            _outcome(_candidate()),
            decompose=lambda c: c,
            select_route=lambda c: ExtensionRoute.BUILD_TIME,
            implement=lambda manifest: ExtensionImplementation(
                _promoted_manifest(manifest), _Activation(manifest.capability_id)
            ),
            retry=lambda raw: retried.append(raw) or "RETRIED",  # type: ignore[arg-type,return-value]
        )
    assert retried == []
