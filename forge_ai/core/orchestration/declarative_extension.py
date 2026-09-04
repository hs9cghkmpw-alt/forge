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
from forge_ai.core.promotion.attestation import (
    canonical_permission_manifest_digest,
)
from forge_ai.core.promotion.gate import PromotionRequest, evaluate_promotion
from forge_ai.core.sandbox.policy import (
    CapabilityTier,
    Permission,
    PermissionManifest,
)


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


def declarative_permission_manifest(capability_id: str) -> PermissionManifest:
    """宣言 Capability の Permission を**導出する**（自己申告ではない）。

    DECLARATIVE 経路が作るのは Forge 自身の Runtime が解釈する **data** であり、
    生成された host code を実行しない。したがって外界への作用は Forge 本体の
    解釈器が持つものに限られ、Permission は `LOCAL_COMPUTE` のみ＝Tier A になる。

    **将来 declarative artifact が effect を表現できるようになったら、この導出は
    嘘になる。** その時点で明示 Manifest を要求へ切り替えること（TD118）。
    """
    return PermissionManifest(
        capability_id=capability_id,
        permissions=frozenset({Permission.LOCAL_COMPUTE}),
        declared_tier=CapabilityTier.A,
    )


def implement_declarative_extension(
    manifest: ExtensionManifest,
    artifact: DeclarativeCapabilityArtifact,
    probes: DeclarativeExtensionProbes,
    *,
    permission_manifest: PermissionManifest | None = None,
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

    # **Promotion Gate を通す。** 宣言経路は生成 host code を実行しないので
    # sandbox / build / runtime probe は要求しないが、**Permission Manifest は
    # 経路に関わらず必須**である（非交渉条件 3）。
    permissions = permission_manifest or declarative_permission_manifest(
        manifest.capability_id
    )
    decision = evaluate_promotion(
        PromotionRequest(
            capability_id=manifest.capability_id,
            requires_generated_source=False,
            permission_manifest=permissions,
            verified_manifest_digest=canonical_permission_manifest_digest(permissions),
            promoted_manifest_digest=canonical_permission_manifest_digest(permissions),
            extra_evidence={
                "route": manifest.route.value,
                "permission_manifest_source": (
                    "explicit" if permission_manifest is not None else "derived"
                ),
            },
        )
    )
    return implementing.verified().promoted(decision)
