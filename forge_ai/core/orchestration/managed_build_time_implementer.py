"""Concrete BUILD_TIME builder/loader bridge backed by managed workspace evidence.

`implement_build_time_extension()` deliberately depends on small Builder/Loader
protocols.  This module provides the production-grade bridge for those protocols:
commands actually execute through `ManagedBuildWorkspaceRunner`, and runtime
activation is issued only for the exact build whose runtime probe and sandbox
preflight passed.

The class is capability-agnostic.  It does not know map/calendar/game semantics;
callers provide a reusable artifact plus an explicit command plan.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from forge_ai.core.orchestration.build_time_extension import (
    BuildTimeBuildResult,
    BuildTimeCapabilityArtifact,
    BuildTimeExtensionError,
    LoadedBuildActivation,
)
from forge_ai.core.orchestration.build_time_workspace import (
    BuildCommand,
    ManagedBuildExecution,
    ManagedBuildWorkspaceRunner,
)


@dataclass(slots=True)
class ManagedBuildTimeImplementer:
    """Concrete implementation of the BUILD_TIME builder + runtime loader contracts.

    A loader call is accepted only for the most recent exact build produced by
    this instance.  This prevents a caller from presenting metadata for some
    other successful build and turning it into a capability activation.
    """

    capability_id: str
    commands: tuple[BuildCommand, ...]
    runner: ManagedBuildWorkspaceRunner = field(default_factory=ManagedBuildWorkspaceRunner)
    _last_execution: ManagedBuildExecution | None = field(default=None, init=False, repr=False)

    def __post_init__(self) -> None:
        if not self.capability_id.strip():
            raise ValueError("managed build-time implementer requires capability_id")
        if not self.commands:
            raise ValueError("managed build-time implementer requires commands")

    def build(self, artifact: BuildTimeCapabilityArtifact) -> BuildTimeBuildResult:
        if artifact.capability_id != self.capability_id:
            raise BuildTimeExtensionError("managed builder changed capability identity")
        execution = self.runner.run(artifact, self.commands)
        self._last_execution = execution
        return execution.result

    def load_runtime(self, build: BuildTimeBuildResult) -> LoadedBuildActivation:
        execution = self._last_execution
        if execution is None:
            raise BuildTimeExtensionError("runtime load requested before managed build execution")
        exact = execution.result
        if build != exact:
            raise BuildTimeExtensionError("runtime load does not reference the exact managed build")
        if not (build.tests_pass and build.build_pass and build.runtime_evidence):
            raise BuildTimeExtensionError("unverified managed build cannot become a loaded runtime")
        if not build.sandbox_preflight:
            raise BuildTimeExtensionError("build without sandbox preflight cannot become a loaded runtime")
        if not build.sandbox_policy_version or not build.sandbox_policy_digest:
            raise BuildTimeExtensionError("sandbox attestation is incomplete")

        evidence = execution.evidence
        if evidence.build_id != build.build_id:
            raise BuildTimeExtensionError("managed evidence build id mismatch")
        if evidence.source_digest != build.source_digest:
            raise BuildTimeExtensionError("managed evidence source digest mismatch")
        if evidence.runtime_fingerprint != build.runtime_fingerprint:
            raise BuildTimeExtensionError("managed evidence runtime fingerprint mismatch")
        if not evidence.sandbox_preflight_pass:
            raise BuildTimeExtensionError("managed evidence has no sandbox preflight pass")
        if evidence.sandbox_policy_version != build.sandbox_policy_version:
            raise BuildTimeExtensionError("sandbox policy version differs from verified build")
        if evidence.sandbox_policy_digest != build.sandbox_policy_digest:
            raise BuildTimeExtensionError("sandbox policy digest differs from verified build")

        return LoadedBuildActivation(
            capability_id=self.capability_id,
            build_id=build.build_id,
            runtime_fingerprint=build.runtime_fingerprint,
            source_digest=build.source_digest,
            loaded=True,
        )

    @property
    def last_execution(self) -> ManagedBuildExecution | None:
        """Concrete command evidence for audit/report generation."""
        return self._last_execution