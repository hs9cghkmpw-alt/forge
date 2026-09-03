"""Shared projection from generated BUILD_TIME paths to installed host paths.

A generated artifact is verified in an isolated workspace, but some files are
installed under a different relative layout.  Security checks and the installer
must use the *same* projection contract; otherwise a relative import can be
validated against one layout and executed from another.

This module is intentionally generic.  It knows no Flutter widget or capability
identity.  A language build plan supplies only structural facts:

* ``host_prefix``: a generated prefix removed when files enter the host app;
* ``excluded_paths``: harness files used for verification but never installed.

Forge also reserves a very small set of generated metadata paths.  They are part
of the verified artifact and are scanned by the sandbox, but they are not host
source and therefore never enter the installed Flutter source tree.

Projection is fail-closed: unsafe paths and two sources collapsing onto the same
installed path are rejected before execution or installation.
"""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from pathlib import PurePosixPath
from typing import Iterable

from forge_ai.core.orchestration.build_time_extension import BuildTimeExtensionError

__all__ = [
    "BUILD_TIME_METADATA_PATHS",
    "BuildTimeHostProjection",
    "HostProjectionError",
]


class HostProjectionError(BuildTimeExtensionError):
    """The declared generated-to-host layout is unsafe or ambiguous."""


#: Declarative evidence/metadata that is verified with the artifact but is not
#: executable host source.  Keep this list intentionally tiny; adding an entry
#: changes what generated files can exist without being installed into the host.
BUILD_TIME_METADATA_PATHS = frozenset({"capability_contribution.json"})


def _normalize_relative(path: str, *, label: str) -> str:
    value = path.replace("\\", "/").strip()
    candidate = PurePosixPath(value)
    if (
        not value
        or candidate.is_absolute()
        or ".." in candidate.parts
        or candidate.as_posix() in {"", "."}
    ):
        raise HostProjectionError(f"unsafe {label}: {path!r}")
    return candidate.as_posix()


@dataclass(frozen=True, slots=True)
class BuildTimeHostProjection:
    """Deterministic generated-path -> installed-host-path projection."""

    host_prefix: str = ""
    excluded_paths: frozenset[str] = frozenset()

    def __post_init__(self) -> None:
        prefix = self.host_prefix.replace("\\", "/").strip()
        if prefix:
            normalized_prefix = _normalize_relative(
                prefix.rstrip("/"),
                label="host projection prefix",
            ) + "/"
        else:
            normalized_prefix = ""

        normalized_excluded = {
            _normalize_relative(path, label="host projection excluded path")
            for path in self.excluded_paths
        }
        normalized_excluded.update(BUILD_TIME_METADATA_PATHS)
        object.__setattr__(self, "host_prefix", normalized_prefix)
        object.__setattr__(self, "excluded_paths", frozenset(normalized_excluded))

    @property
    def digest(self) -> str:
        encoded = json.dumps(
            {
                "host_prefix": self.host_prefix,
                "excluded_paths": sorted(self.excluded_paths),
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return sha256(encoded).hexdigest()

    def project(self, path: str) -> str | None:
        """Return installed path, or ``None`` for verification-only files."""
        source = _normalize_relative(path, label="generated source path")
        if source in self.excluded_paths:
            return None
        if self.host_prefix and source.startswith(self.host_prefix):
            projected = source[len(self.host_prefix):]
            if not projected:
                raise HostProjectionError(
                    f"generated source {path!r} projects to an empty host path"
                )
            return _normalize_relative(projected, label="projected host path")
        return source

    def projected_paths(self, paths: Iterable[str]) -> dict[str, str]:
        """Project all paths and reject many-to-one installation collisions."""
        projected: dict[str, str] = {}
        owner_by_target: dict[str, str] = {}
        for raw in paths:
            source = _normalize_relative(raw, label="generated source path")
            target = self.project(source)
            if target is None:
                continue
            previous = owner_by_target.get(target)
            if previous is not None and previous != source:
                raise HostProjectionError(
                    "host projection collision: "
                    f"{previous!r} and {source!r} both project to {target!r}"
                )
            owner_by_target[target] = source
            projected[source] = target
        return projected
