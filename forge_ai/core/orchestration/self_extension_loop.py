"""Multi-gap self-extension loop for Forge.

A user request may require more than one missing capability.  One successful
extension must not be mistaken for completion of the whole request.  This module
re-runs the original pipeline after each evidence-gated acquisition until the
request no longer returns ``CognitivePipelineNeedsExtension``.

The loop is deliberately bounded and progress-checked.  If retry returns the
same first gap without acquiring anything new, Forge stops instead of spinning
or silently claiming success.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Protocol

from forge_ai.core.orchestration.extension_cycle import ExtensionCycleResult, run_extension_cycle
from forge_ai.core.orchestration.extension_plan import ExtensionCandidate, ExtensionRoute
from forge_ai.core.orchestration.outcomes import (
    CognitivePipelineNeedsExtension,
    CognitivePipelineOutcome,
)


class CandidateDecomposer(Protocol):
    def __call__(self, candidate: ExtensionCandidate) -> ExtensionCandidate: ...


class CandidateRouteSelector(Protocol):
    def __call__(self, candidate: ExtensionCandidate) -> ExtensionRoute: ...


class CandidateImplementer(Protocol):
    def __call__(self, manifest): ...


class PipelineRetry(Protocol):
    def __call__(self, raw_input: str) -> CognitivePipelineOutcome: ...


@dataclass(frozen=True, slots=True)
class SelfExtensionLoopResult:
    final_outcome: CognitivePipelineOutcome
    cycles: tuple[ExtensionCycleResult, ...]
    acquired_capabilities: tuple[str, ...]


class SelfExtensionLoopError(RuntimeError):
    pass


def run_self_extension_loop(
    initial_outcome: CognitivePipelineOutcome,
    *,
    decompose: CandidateDecomposer,
    select_route: CandidateRouteSelector,
    implement: CandidateImplementer,
    retry: PipelineRetry,
    max_cycles: int = 8,
) -> SelfExtensionLoopResult:
    """Acquire every missing capability one-by-one and retry until resolved.

    ``max_cycles`` is a safety bound, not a product limitation.  The caller may
    choose a larger bound for deliberately complex requests, but an accidental
    recursive extension loop must never run forever.
    """
    if max_cycles < 1:
        raise ValueError("max_cycles must be >= 1")

    outcome = initial_outcome
    cycles: list[ExtensionCycleResult] = []
    acquired: list[str] = []

    for _ in range(max_cycles):
        if not isinstance(outcome, CognitivePipelineNeedsExtension):
            return SelfExtensionLoopResult(
                final_outcome=outcome,
                cycles=tuple(cycles),
                acquired_capabilities=tuple(acquired),
            )
        if not outcome.extension_candidates:
            raise SelfExtensionLoopError("NeedsExtension outcome contains no capability candidates.")

        before_id = outcome.extension_candidates[0].capability_id
        cycle = run_extension_cycle(
            outcome,
            decompose=decompose,
            select_route=select_route,
            implement=implement,
            retry=retry,
        )
        cycles.append(cycle)
        acquired_id = cycle.manifest.capability_id
        if acquired_id in acquired:
            raise SelfExtensionLoopError(
                f"Capability {acquired_id!r} was acquired twice; no forward progress."
            )
        acquired.append(acquired_id)
        outcome = cycle.retry_outcome

        if isinstance(outcome, CognitivePipelineNeedsExtension) and outcome.extension_candidates:
            after_id = outcome.extension_candidates[0].capability_id
            if after_id == before_id:
                raise SelfExtensionLoopError(
                    f"Retry returned the same capability gap {after_id!r} after promotion; "
                    "activation/planner wiring did not make progress."
                )

    if isinstance(outcome, CognitivePipelineNeedsExtension):
        remaining = tuple(c.capability_id for c in outcome.extension_candidates)
        raise SelfExtensionLoopError(
            f"Self-extension exceeded max_cycles={max_cycles}; remaining gaps: {remaining}"
        )

    return SelfExtensionLoopResult(
        final_outcome=outcome,
        cycles=tuple(cycles),
        acquired_capabilities=tuple(acquired),
    )
