"""Activation contract for promoted Forge capabilities.

A PROMOTED manifest proves that an implementation passed evidence gates, but it
does not by itself make that implementation executable in the current process.
Immediate reuse therefore requires an activation payload as well as the manifest.

This closes a Whole Scan false-success gap where the planner could treat a
promoted declarative capability as available while only its metadata had been
installed.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from forge_ai.core.orchestration.extension_manifest import ExtensionManifest


@runtime_checkable
class CapabilityActivation(Protocol):
    """Minimal executable identity exposed by an in-process extension."""

    @property
    def capability_id(self) -> str: ...


@dataclass(frozen=True, slots=True)
class ExtensionImplementation:
    """Evidence result plus the executable activation loaded by this process."""

    manifest: ExtensionManifest
    activation: CapabilityActivation | None
