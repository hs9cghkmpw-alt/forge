"""Executable orchestration for Forge's self-extension loop.

This module does not generate arbitrary code itself.  It closes the control-flow
contract around a capability gap:

NeedsExtension -> exact decomposition -> managed route -> implementation ->
evidence-gated promotion -> retry the original request.

The implementation/decomposition hooks are injected deliberately.  Their output
is not trusted: this coordinator verifies that the manifest is PROMOTED before
retrying, and refuses semantic drift between the original candidate and the
implemented capability.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Protocol

from forge_ai.core.orchestration.extension_manifest import (
    ExtensionManifest,
    ExtensionStatus,
    create_extension_manifest,
)
from forge_ai.core.orchestration.extension_plan import ExtensionCandidate, ExtensionRoute
from forge_ai.core.orchestration.outcomes import (
    CognitivePipelineNeedsExtension,
    CognitivePipelineOutcome,
)


class ExtensionDecomposer(Protocol):
    def __call__(self, candidate: ExtensionCandidate) -> ExtensionCandidate: ...


class ExtensionRouteSelector(Protocol):
    def __call__(self, candidate: ExtensionCandidate) -> ExtensionRoute: ...


class ExtensionImplementer(Protocol):
    def __call__(self, manifest: ExtensionManifest) -> ExtensionManifest: ...


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
    """Run one complete, fail-closed self-extension attempt.

    The first candidate is handled per cycle so failures remain attributable.
    Multi-gap requests can call this repeatedly; Forge must not silently mark a
    bundle complete when only one capability was acquired.
    """
    if not outcome.extension_candidates:
        raise ExtensionCycleError("NeedsExtension outcome contains no extension candidate.")

    original = outcome.extension_candidates[0]
    resolved = decompose(original)

    if not resolved.capability_id or resolved.capability_id == "semantic_structure_unresolved":
        raise ExtensionCycleError("Extension decomposition did not resolve an exact reusable capability.")
    if resolved.routes == (ExtensionRoute.NEEDS_DECOMPOSITION,):
        raise ExtensionCycleError("Resolved candidate still requires decomposition.")

    route = select_route(resolved)
    manifest = create_extension_manifest(resolved, route)
    implemented = implement(manifest)

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

    raw_input = outcome.partial_context.raw_input
    retry_outcome = retry(raw_input)
    return ExtensionCycleResult(
        original_candidate=original,
        resolved_candidate=resolved,
        manifest=implemented,
        retry_outcome=retry_outcome,
    )
