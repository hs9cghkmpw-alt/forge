from __future__ import annotations

from dataclasses import dataclass, replace
from types import SimpleNamespace

import pytest

from forge_ai.core.orchestration.extension_activation import ExtensionImplementation
from forge_ai.core.orchestration.extension_manifest import ExtensionEvidence
from forge_ai.core.orchestration.extension_plan import ExtensionCandidate, ExtensionRoute
from forge_ai.core.orchestration.extension_registry import PROMOTED_CAPABILITIES
from forge_ai.core.orchestration.outcomes import CognitivePipelineNeedsExtension
from forge_ai.core.orchestration.self_extension_loop import (
    SelfExtensionLoopError,
    run_self_extension_loop,
)
from forge_ai.core.semantics.capabilities import SafetyClass, SupportLevel


@dataclass(frozen=True)
class _Activation:
    capability_id: str


def _candidate(capability_id: str) -> ExtensionCandidate:
    return ExtensionCandidate(
        capability_id=capability_id,
        label_ja=capability_id,
        support=SupportLevel.MISSING,
        safety=SafetyClass.SAFE,
        routes=(ExtensionRoute.DECLARATIVE,),
        reason="test gap",
        requires_confirmation=False,
    )


def _needs(*capability_ids: str) -> CognitivePipelineNeedsExtension:
    return CognitivePipelineNeedsExtension(
        error=Exception("gap"),
        reached_stage="capability_gap",
        partial_context=SimpleNamespace(raw_input="複数の不足能力が必要なアプリ"),
        extension_candidates=tuple(_candidate(c) for c in capability_ids),
        decision_trace=(),
    )


def _implement(manifest) -> ExtensionImplementation:
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
    promoted = replace(manifest, evidence=evidence).verified().promoted()
    return ExtensionImplementation(
        manifest=promoted,
        activation=_Activation(promoted.capability_id),
    )


def test_multi_gap_request_acquires_every_gap_before_completion() -> None:
    PROMOTED_CAPABILITIES.clear()
    retries = iter([
        _needs("view.map"),
        "SUCCESS",
    ])

    result = run_self_extension_loop(
        _needs("interact.filter", "view.map"),
        decompose=lambda c: c,
        select_route=lambda c: ExtensionRoute.DECLARATIVE,
        implement=_implement,
        retry=lambda raw: next(retries),  # type: ignore[return-value]
    )

    assert result.final_outcome == "SUCCESS"
    assert result.acquired_capabilities == ("interact.filter", "view.map")
    assert len(result.cycles) == 2
    assert PROMOTED_CAPABILITIES.is_promoted("interact.filter")
    assert PROMOTED_CAPABILITIES.is_promoted("view.map")


def test_same_gap_after_promotion_is_rejected_as_no_progress() -> None:
    PROMOTED_CAPABILITIES.clear()

    with pytest.raises(SelfExtensionLoopError, match="same capability gap"):
        run_self_extension_loop(
            _needs("interact.filter"),
            decompose=lambda c: c,
            select_route=lambda c: ExtensionRoute.DECLARATIVE,
            implement=_implement,
            retry=lambda raw: _needs("interact.filter"),
        )


def test_max_cycle_bound_preserves_remaining_gap_in_error() -> None:
    PROMOTED_CAPABILITIES.clear()

    with pytest.raises(SelfExtensionLoopError, match="remaining gaps"):
        run_self_extension_loop(
            _needs("interact.filter"),
            decompose=lambda c: c,
            select_route=lambda c: ExtensionRoute.DECLARATIVE,
            implement=_implement,
            retry=lambda raw: _needs("view.map"),
            max_cycles=1,
        )


def test_non_extension_outcome_returns_without_mutation() -> None:
    PROMOTED_CAPABILITIES.clear()
    result = run_self_extension_loop(
        "ALREADY_SUCCESS",  # type: ignore[arg-type]
        decompose=lambda c: c,
        select_route=lambda c: ExtensionRoute.DECLARATIVE,
        implement=_implement,
        retry=lambda raw: "UNUSED",  # type: ignore[return-value]
    )
    assert result.final_outcome == "ALREADY_SUCCESS"
    assert result.cycles == ()
    assert result.acquired_capabilities == ()
