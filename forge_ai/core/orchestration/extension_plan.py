"""Structured planning for Forge self-extension candidates.

A Capability Gap is not a template-selection failure.  It is the input to the
next product loop: decompose the missing semantic capability, determine which
managed extension routes are plausible, then implement/validate one of them.

This module intentionally does not invent a second capability catalog.  It reads
only the canonical metadata in ``core.semantics.capabilities`` and therefore
cannot silently drift from SupportLevel/SafetyClass/CapabilityLayer truth.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from forge_ai.core.semantics.capabilities import (
    CapabilityDefinition,
    CapabilityLayer,
    SafetyClass,
    SupportLevel,
    capability,
)


class ExtensionRoute(str, Enum):
    """Managed routes that may satisfy a missing capability.

    The tuple of candidates is deliberately broader than a single guessed route.
    Exact routing requires decomposition/evidence; Forge must not pretend that a
    semantic label alone proves the implementation mechanism.
    """

    COMPOSITION = "composition"
    DECLARATIVE = "declarative"
    BUILD_TIME = "build_time"
    SERVICE = "service"
    NATIVE_PRIVILEGED = "native_privileged"
    NEEDS_DECOMPOSITION = "needs_decomposition"


@dataclass(frozen=True, slots=True)
class ExtensionCandidate:
    capability_id: str
    label_ja: str
    support: SupportLevel | None
    safety: SafetyClass | None
    routes: tuple[ExtensionRoute, ...]
    reason: str
    requires_confirmation: bool


def _routes_for(definition: CapabilityDefinition) -> tuple[ExtensionRoute, ...]:
    """Return plausible managed routes without claiming an unproven exact route."""
    if definition.support is SupportLevel.IMPLEMENTED:
        return (ExtensionRoute.COMPOSITION,)

    if definition.layer is CapabilityLayer.EFFECT:
        # Effects may cross process/device/user boundaries.  Do not auto-select
        # one mechanism from a semantic ID; require privileged decomposition.
        return (
            ExtensionRoute.SERVICE,
            ExtensionRoute.NATIVE_PRIVILEGED,
            ExtensionRoute.BUILD_TIME,
        )

    # Data/View/Interact/Simulate gaps are often expressible after adding a
    # reusable declarative primitive; otherwise the runtime/compiler must gain
    # a build-time primitive.  Keep both until decomposition proves which one.
    return (ExtensionRoute.DECLARATIVE, ExtensionRoute.BUILD_TIME)


def plan_extension_candidate(capability_id: str) -> ExtensionCandidate:
    """Create a truthful extension candidate for one semantic capability ID.

    Unknown IDs are *not* treated as missing product capabilities: that is a
    planner/catalog consistency bug, so the route remains NEEDS_DECOMPOSITION.
    """
    definition = capability(capability_id)
    if definition is None:
        return ExtensionCandidate(
            capability_id=capability_id,
            label_ja=capability_id,
            support=None,
            safety=None,
            routes=(ExtensionRoute.NEEDS_DECOMPOSITION,),
            reason="Capability ID is absent from the canonical catalog; fix/decompose before extension.",
            requires_confirmation=False,
        )

    routes = _routes_for(definition)
    return ExtensionCandidate(
        capability_id=definition.id,
        label_ja=definition.label_ja,
        support=definition.support,
        safety=definition.safety,
        routes=routes,
        reason=(
            "Capability already exists; satisfy by composition."
            if definition.support is SupportLevel.IMPLEMENTED
            else "Capability is partial/missing; preserve the gap and choose a managed extension route after decomposition."
        ),
        requires_confirmation=(
            definition.layer is CapabilityLayer.EFFECT
            or definition.safety is SafetyClass.SENSITIVE
        ),
    )


def plan_extension_candidates(capability_ids: tuple[str, ...]) -> tuple[ExtensionCandidate, ...]:
    """Deterministic, de-duplicated extension candidates in input order."""
    seen: set[str] = set()
    result: list[ExtensionCandidate] = []
    for capability_id in capability_ids:
        if capability_id in seen:
            continue
        seen.add(capability_id)
        result.append(plan_extension_candidate(capability_id))
    return tuple(result)
