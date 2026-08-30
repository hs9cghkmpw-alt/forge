"""Executable declarative self-extension for Forge.

A declarative extension is not arbitrary code generation.  It is a reusable
capability artifact composed from already-approved runtime primitives.  The
artifact is validated structurally, bound through explicit adapters, and only
then may produce evidence for an ExtensionManifest.

This module deliberately separates:
- semantic capability identity,
- reusable primitive composition,
- binding/evidence probes,
- promotion.

That prevents a Golden app or one-off template from being mistaken for a new
Forge capability.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Callable, Mapping, Protocol

from forge_ai.core.orchestration.extension_manifest import (
    ExtensionEvidence,
    ExtensionManifest,
    ExtensionStatus,
)
from forge_ai.core.orchestration.extension_plan import ExtensionRoute


_ALLOWED_PRIMITIVE_KINDS = frozenset({
    "data",
    "transform",
    "view",
    "encoding",
    "interact",
    "simulate",
})


@dataclass(frozen=True, slots=True)
class DeclarativePrimitiveRef:
    kind: str
    primitive_id: str
    config: Mapping[str, object]


@dataclass(frozen=True, slots=True)
class DeclarativeCapabilityArtifact:
    capability_id: str
    primitives: tuple[DeclarativePrimitiveRef, ...]
    reusable_contract: str
    language_fragment: Mapping[str, object]

    def validate(self) -> None:
        if not self.capability_id:
            raise ValueError("Declarative capability artifact requires capability_id.")
        if not self.primitives:
            raise ValueError("Declarative capability artifact requires at least one primitive.")
        if not self.reusable_contract.strip():
            raise ValueError("Declarative capability artifact requires a reusable contract.")
        if not self.language_fragment:
            raise ValueError("Declarative capability artifact requires a Forge Language fragment.")

        for primitive in self.primitives:
            if primitive.kind not in _ALLOWED_PRIMITIVE_KINDS:
                raise ValueError(f"Unsupported primitive kind: {primitive.kind!r}")
            if not primitive.primitive_id:
                raise ValueError("Primitive reference requires primitive_id.")


class DeclarativeBindingProbe(Protocol):
    def __call__(self, artifact: DeclarativeCapabilityArtifact) -> bool: ...


@dataclass(frozen=True, slots=True)
class DeclarativeExtensionProbes:
    language_binding: DeclarativeBindingProbe
    validator_binding: DeclarativeBindingProbe
    runtime_binding: DeclarativeBindingProbe
    compiler_binding: DeclarativeBindingProbe
    tests_pass: DeclarativeBindingProbe
    build_pass: DeclarativeBindingProbe
    runtime_evidence: DeclarativeBindingProbe
    safety_review: DeclarativeBindingProbe | None = None


def implement_declarative_extension(
    manifest: ExtensionManifest,
    artifact: DeclarativeCapabilityArtifact,
    probes: DeclarativeExtensionProbes,
) -> ExtensionManifest:
    """Validate/bind one declarative artifact and return evidence-gated manifest.

    This function never claims success from artifact creation alone.  Every
    binding/evidence probe must explicitly pass.  Sensitive capabilities also
    require a safety probe.
    """
    if manifest.route is not ExtensionRoute.DECLARATIVE:
        raise ValueError("Declarative executor may only handle DECLARATIVE manifests.")
    if manifest.status not in (ExtensionStatus.DRAFT, ExtensionStatus.IMPLEMENTING):
        raise ValueError("Declarative executor requires a draft/implementing manifest.")
    if artifact.capability_id != manifest.capability_id:
        raise ValueError("Declarative artifact changed capability identity.")

    artifact.validate()

    evidence = ExtensionEvidence(
        semantic_decomposition=True,
        reusable_primitive=True,
        language_binding=bool(probes.language_binding(artifact)),
        validator_binding=bool(probes.validator_binding(artifact)),
        runtime_binding=bool(probes.runtime_binding(artifact)),
        compiler_binding=bool(probes.compiler_binding(artifact)),
        tests_pass=bool(probes.tests_pass(artifact)),
        build_pass=bool(probes.build_pass(artifact)),
        runtime_evidence=bool(probes.runtime_evidence(artifact)),
        safety_review=(
            bool(probes.safety_review(artifact))
            if manifest.requires_confirmation and probes.safety_review is not None
            else not manifest.requires_confirmation
        ),
    )

    implementing = replace(
        manifest,
        status=ExtensionStatus.IMPLEMENTING,
        evidence=evidence,
    )
    if not implementing.can_promote:
        return implementing
    return implementing.verified().promoted()
