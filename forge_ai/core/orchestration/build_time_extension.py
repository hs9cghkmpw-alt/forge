"""Managed BUILD_TIME self-extension for Forge.

BUILD_TIME is the route for a genuinely missing primitive whose implementation
requires generated/modified source and a new runtime build.  Promotion alone is
not enough: the built runtime must be loaded and fingerprint-matched before the
capability can be exposed to the planner.  Generated host-code execution also
requires explicit sandbox preflight evidence before promotion.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from hashlib import sha256
from pathlib import PurePosixPath
from typing import Protocol

from forge_ai.core.orchestration.extension_activation import ExtensionImplementation
from forge_ai.core.orchestration.extension_manifest import (
    ExtensionEvidence,
    ExtensionManifest,
    ExtensionStatus,
)
from forge_ai.core.orchestration.extension_plan import ExtensionRoute
from forge_ai.core.promotion.effects import EffectKind, inspect_generated_sources
from forge_ai.core.promotion.attestation import (
    canonical_permission_manifest_digest,
)
from forge_ai.core.promotion.dependencies import UnknownSecurityPolicy
from forge_ai.core.promotion.gate import PromotionRequest, evaluate_promotion
from forge_ai.core.sandbox.policy import (
    CapabilityTier,
    Permission,
    PermissionManifest,
)


class BuildTimeExtensionError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class BuildTimeSourceFile:
    path: str
    content: str

    def validate(self) -> None:
        path = PurePosixPath(self.path)
        if path.is_absolute() or ".." in path.parts or not path.parts:
            raise BuildTimeExtensionError(f"unsafe generated source path: {self.path!r}")
        if not self.content.strip():
            raise BuildTimeExtensionError(f"generated source is empty: {self.path!r}")


@dataclass(frozen=True, slots=True)
class BuildTimeCapabilityArtifact:
    capability_id: str
    files: tuple[BuildTimeSourceFile, ...]
    reusable_contract: str
    changed_bindings: tuple[str, ...]

    def validate(self) -> None:
        if not self.capability_id:
            raise BuildTimeExtensionError("build-time artifact requires capability_id")
        if not self.files:
            raise BuildTimeExtensionError("build-time artifact requires generated source files")
        if not self.reusable_contract.strip():
            raise BuildTimeExtensionError("build-time artifact requires reusable contract")
        required = {
            "language",
            "validator",
            "runtime",
            "compiler",
        }
        missing = required.difference(self.changed_bindings)
        if missing:
            raise BuildTimeExtensionError(
                "build-time artifact is missing required binding targets: "
                + ", ".join(sorted(missing))
            )
        seen: set[str] = set()
        for source in self.files:
            source.validate()
            if source.path in seen:
                raise BuildTimeExtensionError(f"duplicate generated source path: {source.path!r}")
            seen.add(source.path)

    @property
    def source_digest(self) -> str:
        self.validate()
        h = sha256()
        for source in sorted(self.files, key=lambda item: item.path):
            h.update(source.path.encode("utf-8"))
            h.update(b"\0")
            h.update(source.content.encode("utf-8"))
            h.update(b"\0")
        return h.hexdigest()


@dataclass(frozen=True, slots=True)
class BuildTimeBuildResult:
    build_id: str
    source_digest: str
    runtime_fingerprint: str
    tests_pass: bool
    build_pass: bool
    runtime_evidence: bool
    safety_review: bool = False
    sandbox_preflight: bool = False
    sandbox_policy_version: str = ""
    sandbox_policy_digest: str = ""
    sandbox_backend: str = ""
    """**どの OS 隔離で走ったか。** 空 = 隔離を通っていない。

    ここが無かったので、Promotion 判定は `policy-only` と
    `windows-appcontainer+job` を区別できなかった（2026-09-04 に発見）。
    """

    generated_sources: tuple[tuple[str, str], ...] = ()
    """静的検査へ渡す `(path, content)`。空なら検査できない＝拒否される。"""

    command_sources: tuple[str, ...] = ()
    """実際に走らせた command。依存の取得行為を走査する対象。"""

    permission_manifest: "PermissionManifest | None" = None
    declared_effects: frozenset[EffectKind] = frozenset()


class BuildTimeBuilder(Protocol):
    def __call__(self, artifact: BuildTimeCapabilityArtifact) -> BuildTimeBuildResult: ...


class BuildTimeRuntimeLoader(Protocol):
    def __call__(self, build: BuildTimeBuildResult) -> "LoadedBuildActivation": ...


@dataclass(frozen=True, slots=True)
class LoadedBuildActivation:
    """Proof that the newly built runtime is the runtime currently loaded."""

    capability_id: str
    build_id: str
    runtime_fingerprint: str
    source_digest: str
    loaded: bool = True


def acquired_capability_permission_manifest(capability_id: str) -> PermissionManifest:
    """獲得 Capability の**意図**を最小権限で書く（Tier A / 純粋計算）。

    Forge が獲得する Capability は「描画する」ものであって、ネットワークや
    ファイルや秘密へ触るものではない。したがって宣言は `LOCAL_COMPUTE` だけ。

    **これは検査を甘くするための既定値ではない。** 逆である——宣言が最小
    なので、生成物が少しでも外界へ触れば `EFFECT_EXCEEDS_PERMISSION` で
    落ちる。Gate は宣言と実測（静的検査）を突き合わせる。
    """
    return PermissionManifest(
        capability_id=capability_id,
        permissions=frozenset({Permission.LOCAL_COMPUTE}),
        declared_tier=CapabilityTier.A,
    )


def implement_build_time_extension(
    manifest: ExtensionManifest,
    artifact: BuildTimeCapabilityArtifact,
    *,
    builder: BuildTimeBuilder,
    load_runtime: BuildTimeRuntimeLoader,
) -> ExtensionImplementation:
    """Generate/build/load one missing reusable primitive and gate promotion.

    The loader must attest the exact build/source fingerprint.  A successful
    compile that has not been loaded cannot be retried as an acquired capability.
    """
    if manifest.route is not ExtensionRoute.BUILD_TIME:
        raise BuildTimeExtensionError("build-time executor only accepts BUILD_TIME manifests")
    if manifest.status not in (ExtensionStatus.DRAFT, ExtensionStatus.IMPLEMENTING):
        raise BuildTimeExtensionError("build-time executor requires draft/implementing manifest")
    if artifact.capability_id != manifest.capability_id:
        raise BuildTimeExtensionError("build-time artifact changed capability identity")

    artifact.validate()
    build = builder(artifact)
    if build.source_digest != artifact.source_digest:
        raise BuildTimeExtensionError("builder source digest does not match generated artifact")
    if not build.build_id or not build.runtime_fingerprint:
        raise BuildTimeExtensionError("builder must return build_id and runtime_fingerprint")
    if build.sandbox_preflight and (
        not build.sandbox_policy_version or not build.sandbox_policy_digest
    ):
        raise BuildTimeExtensionError(
            "sandbox preflight cannot be true without policy version and digest"
        )

    evidence = ExtensionEvidence(
        semantic_decomposition=True,
        reusable_primitive=True,
        language_binding="language" in artifact.changed_bindings,
        validator_binding="validator" in artifact.changed_bindings,
        runtime_binding="runtime" in artifact.changed_bindings,
        compiler_binding="compiler" in artifact.changed_bindings,
        tests_pass=build.tests_pass,
        build_pass=build.build_pass,
        runtime_evidence=build.runtime_evidence,
        sandbox_preflight=(
            build.sandbox_preflight
            and bool(build.sandbox_policy_version)
            and bool(build.sandbox_policy_digest)
        ),
        safety_review=build.safety_review if manifest.requires_confirmation else True,
    )
    implementing = replace(manifest, status=ExtensionStatus.IMPLEMENTING, evidence=evidence)
    if not implementing.can_promote:
        return ExtensionImplementation(manifest=implementing, activation=None)

    # build 時点の Permission Manifest を先に固定する。あとで比べるため
    # であり、**同じ値を 2 回計算して自分と比べる茶番にしない**。
    verified_permission_digest = canonical_permission_manifest_digest(
        build.permission_manifest
    )

    # **Promotion Gate。** ここを通らずに PROMOTED にはできない
    # （`promoted()` が決定を必須引数で要求する）。
    inspection = (
        inspect_generated_sources(build.generated_sources)
        if build.generated_sources
        else inspect_generated_sources(
            tuple((source.path, source.content) for source in artifact.files)
        )
    )
    decision = evaluate_promotion(
        PromotionRequest(
            capability_id=manifest.capability_id,
            requires_generated_source=True,
            permission_manifest=build.permission_manifest,
            inspection=inspection,
            declared_effects=build.declared_effects,
            sandbox_backend=build.sandbox_backend,
            sandbox_policy_version=build.sandbox_policy_version,
            sandbox_policy_digest=build.sandbox_policy_digest,
            tests_pass=build.tests_pass,
            build_pass=build.build_pass,
            runtime_probe_pass=build.runtime_evidence,
            verified_source_digest=build.source_digest,
            promoted_source_digest=artifact.source_digest,
            verified_artifact_digest=build.runtime_fingerprint,
            promoted_artifact_digest=build.runtime_fingerprint,
            # **Manifest digest を production で必須にする**（001A / Major 2）。
            #
            # verified = builder が返した Permission Manifest（build 時点）
            # promoted = いま昇格しようとしている Permission Manifest
            #
            # 両者が違えば、build と昇格の間に権限・承認・出所が
            # 書き換えられたということである。
            verified_manifest_digest=verified_permission_digest,
            promoted_manifest_digest=canonical_permission_manifest_digest(
                build.permission_manifest
            ),
            command_sources=build.command_sources,
            # 生成 Capability の依存は「Forge が既に同梱していて、生成物の
            # ために新規取得が発生しないもの」に限る。**それでも
            # 「脆弱性が無いと確認した」ではない**（SEC-06 は PARTIAL のまま）。
            unknown_security_policy=UnknownSecurityPolicy.ALLOW_IF_BUNDLED,
            extra_evidence={"route": manifest.route.value, "build_id": build.build_id},
        )
    )
    promoted = implementing.verified().promoted(decision)
    activation = load_runtime(build)
    if not activation.loaded:
        raise BuildTimeExtensionError("new build was not loaded; refusing capability activation")
    if activation.capability_id != artifact.capability_id:
        raise BuildTimeExtensionError("loaded build changed capability identity")
    if activation.build_id != build.build_id:
        raise BuildTimeExtensionError("loaded build id does not match verified build")
    if activation.runtime_fingerprint != build.runtime_fingerprint:
        raise BuildTimeExtensionError("loaded runtime fingerprint does not match verified build")
    if activation.source_digest != artifact.source_digest:
        raise BuildTimeExtensionError("loaded source digest does not match generated artifact")

    return ExtensionImplementation(manifest=promoted, activation=activation)