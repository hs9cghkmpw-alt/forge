"""Executable orchestration for Forge's self-extension loop.

This module closes the control-flow contract around a capability gap:

NeedsExtension -> exact decomposition -> managed route -> implementation ->
evidence-gated promotion -> executable activation -> retry original request.

A manifest proves evidence; it is not itself executable.  Immediate retry is
allowed only when the implementer returns a matching activation that can be
installed into the current process.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from forge_ai.core.orchestration.extension_activation import ExtensionImplementation
from forge_ai.core.orchestration.extension_manifest import (
    ExtensionManifest,
    ExtensionStatus,
    create_extension_manifest,
)
from forge_ai.core.orchestration.extension_plan import ExtensionCandidate, ExtensionRoute
from forge_ai.core.orchestration.extension_registry import PROMOTED_CAPABILITIES
from forge_ai.core.orchestration.outcomes import (
    CognitivePipelineNeedsExtension,
    CognitivePipelineOutcome,
)


class ExtensionDecomposer(Protocol):
    def __call__(self, candidate: ExtensionCandidate) -> ExtensionCandidate: ...


class ExtensionRouteSelector(Protocol):
    def __call__(self, candidate: ExtensionCandidate) -> ExtensionRoute: ...


class ExtensionImplementer(Protocol):
    def __call__(self, manifest: ExtensionManifest) -> ExtensionImplementation: ...


class ExtensionRetry(Protocol):
    def __call__(self, raw_input: str) -> CognitivePipelineOutcome: ...


@dataclass(frozen=True, slots=True)
class ExtensionCycleResult:
    original_candidate: ExtensionCandidate
    resolved_candidate: ExtensionCandidate
    manifest: ExtensionManifest
    retry_outcome: CognitivePipelineOutcome


class ExtensionCycleError(RuntimeError):
    pass


def run_extension_cycle(
    outcome: CognitivePipelineNeedsExtension,
    *,
    decompose: ExtensionDecomposer,
    select_route: ExtensionRouteSelector,
    implement: ExtensionImplementer,
    retry: ExtensionRetry,
) -> ExtensionCycleResult:
    """Run one complete, fail-closed self-extension attempt."""
    if not outcome.extension_candidates:
        raise ExtensionCycleError("NeedsExtension outcome contains no extension candidate.")

    original = outcome.extension_candidates[0]
    resolved = decompose(original)

    if not resolved.capability_id or resolved.capability_id == "semantic_structure_unresolved":
        raise ExtensionCycleError("Extension decomposition did not resolve an exact reusable capability.")
    if resolved.routes == (ExtensionRoute.NEEDS_DECOMPOSITION,):
        raise ExtensionCycleError("Resolved candidate still requires decomposition.")

    route = select_route(resolved)
    draft = create_extension_manifest(resolved, route)
    implementation = implement(draft)
    implemented = implementation.manifest

    if implemented.capability_id != resolved.capability_id:
        raise ExtensionCycleError(
            "Extension implementer changed capability identity; refusing semantic substitution."
        )
    if implemented.route is not route:
        raise ExtensionCycleError("Extension implementer changed the approved managed route.")
    if implemented.status is not ExtensionStatus.PROMOTED:
        blockers = ", ".join(implemented.promotion_blockers()) or implemented.status.value
        raise ExtensionCycleError(
            "Extension was not evidence-gated PROMOTED; refusing retry as if capability existed: "
            + blockers
        )

    try:
        PROMOTED_CAPABILITIES.install(implemented, implementation.activation)
    except ValueError as exc:
        raise ExtensionCycleError(str(exc)) from exc

    raw_input = outcome.partial_context.raw_input
    retry_outcome = retry(raw_input)
    return ExtensionCycleResult(
        original_candidate=original,
        resolved_candidate=resolved,
        manifest=implemented,
        retry_outcome=retry_outcome,
    )
