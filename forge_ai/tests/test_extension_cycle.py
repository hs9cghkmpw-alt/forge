from __future__ import annotations

from dataclasses import replace
from types import SimpleNamespace

import pytest

from forge_ai.core.orchestration.extension_cycle import ExtensionCycleError, run_extension_cycle
from forge_ai.core.orchestration.extension_manifest import ExtensionEvidence
from forge_ai.core.orchestration.extension_registry import PROMOTED_CAPABILITIES
from forge_ai.core.orchestration.extension_plan import (
    ExtensionCandidate,
    ExtensionRoute,
)
from forge_ai.core.orchestration.outcomes import CognitivePipelineNeedsExtension
from forge_ai.core.semantics.capabilities import SafetyClass, SupportLevel


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


def _promote(manifest):
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
    )
    return replace(manifest, evidence=evidence).verified().promoted()


def test_promoted_declarative_extension_is_installed_then_retries_original_request() -> None:
    PROMOTED_CAPABILITIES.clear()
    retried: list[str] = []

    result = run_extension_cycle(
        _outcome(_candidate()),
        decompose=lambda c: c,
        select_route=lambda c: ExtensionRoute.DECLARATIVE,
        implement=_promote,
        retry=lambda raw: retried.append(raw) or "RETRIED",  # type: ignore[arg-type,return-value]
    )

    assert result.manifest.status.value == "promoted"
    assert PROMOTED_CAPABILITIES.is_promoted("view.map")
    assert retried == ["釣果を地図で見たい"]
    assert result.retry_outcome == "RETRIED"


def test_unverified_extension_cannot_trigger_retry() -> None:
    retried: list[str] = []

    with pytest.raises(ExtensionCycleError, match="not evidence-gated PROMOTED"):
        run_extension_cycle(
            _outcome(_candidate()),
            decompose=lambda c: c,
            select_route=lambda c: ExtensionRoute.BUILD_TIME,
            implement=lambda manifest: manifest,
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
            implement=lambda manifest: manifest,
            retry=lambda raw: "RETRIED",  # type: ignore[return-value]
        )


def test_implementer_cannot_swap_capability_identity() -> None:
    with pytest.raises(ExtensionCycleError, match="changed capability identity"):
        run_extension_cycle(
            _outcome(_candidate("view.map")),
            decompose=lambda c: c,
            select_route=lambda c: ExtensionRoute.BUILD_TIME,
            implement=lambda manifest: replace(_promote(manifest), capability_id="view.calendar"),
            retry=lambda raw: "RETRIED",  # type: ignore[return-value]
        )


def test_build_time_promotion_requires_runtime_reload_before_retry() -> None:
    PROMOTED_CAPABILITIES.clear()
    retried: list[str] = []

    with pytest.raises(ExtensionCycleError, match="cannot be activated in-process"):
        run_extension_cycle(
            _outcome(_candidate()),
            decompose=lambda c: c,
            select_route=lambda c: ExtensionRoute.BUILD_TIME,
            implement=_promote,
            retry=lambda raw: retried.append(raw) or "RETRIED",  # type: ignore[arg-type,return-value]
        )

    assert retried == []
    assert not PROMOTED_CAPABILITIES.is_promoted("view.map")
