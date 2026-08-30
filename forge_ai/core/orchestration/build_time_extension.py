"""Managed BUILD_TIME self-extension for Forge.

BUILD_TIME is the route for a genuinely missing primitive whose implementation
requires generated/modified source and a new runtime build.  Promotion alone is
not enough: the built runtime must be loaded and fingerprint-matched before the
capability can be exposed to the planner.
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
        safety_review=build.safety_review if manifest.requires_confirmation else True,
    )
    implementing = replace(manifest, status=ExtensionStatus.IMPLEMENTING, evidence=evidence)
    if not implementing.can_promote:
        return ExtensionImplementation(manifest=implementing, activation=None)

    promoted = implementing.verified().promoted()
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
