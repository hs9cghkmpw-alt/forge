"""Durable store for evidence-gated declarative capability acquisition.

Process-local activation is useful only until Forge restarts.  This module stores
PROMOTED declarative artifacts together with their evidence manifest, protects
the canonical payload with an integrity digest, and reconstructs the executable
activation before reinstalling the capability on startup.

The store does not turn drafts into capabilities.  Only already-PROMOTED,
blocker-free declarative manifests are serializable, and loading re-validates the
artifact plus manifest invariants before activation.
"""

from __future__ import annotations

from dataclasses import asdict
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

from forge_ai.core.orchestration.declarative_activation import activation_from_artifact
from forge_ai.core.orchestration.declarative_extension import (
    DeclarativeCapabilityArtifact,
    DeclarativePrimitiveRef,
)
from forge_ai.core.orchestration.extension_manifest import (
    ExtensionEvidence,
    ExtensionManifest,
    ExtensionStatus,
)
from forge_ai.core.orchestration.extension_plan import ExtensionRoute
from forge_ai.core.orchestration.extension_registry import PROMOTED_CAPABILITIES, PromotedCapability


_STORE_VERSION = 1


class ExtensionStoreError(ValueError):
    pass


def _canonical_json(payload: Mapping[str, object]) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _digest(payload: Mapping[str, object]) -> str:
    return hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()


def _payload(manifest: ExtensionManifest, artifact: DeclarativeCapabilityArtifact) -> dict[str, object]:
    return {
        "version": _STORE_VERSION,
        "manifest": {
            "capability_id": manifest.capability_id,
            "label_ja": manifest.label_ja,
            "route": manifest.route.value,
            "requires_confirmation": manifest.requires_confirmation,
            "status": manifest.status.value,
            "evidence": asdict(manifest.evidence),
            "source_reason": manifest.source_reason,
        },
        "artifact": {
            "capability_id": artifact.capability_id,
            "reusable_contract": artifact.reusable_contract,
            "language_fragment": dict(artifact.language_fragment),
            "primitives": [
                {
                    "kind": primitive.kind,
                    "primitive_id": primitive.primitive_id,
                    "config": dict(primitive.config),
                }
                for primitive in artifact.primitives
            ],
        },
    }


def save_promoted_declarative_extension(
    path: str | Path,
    manifest: ExtensionManifest,
    artifact: DeclarativeCapabilityArtifact,
) -> None:
    """Persist one installed-capable declarative extension atomically."""
    if manifest.status is not ExtensionStatus.PROMOTED or manifest.promotion_blockers():
        raise ExtensionStoreError("Only blocker-free PROMOTED extensions may be persisted.")
    if manifest.route is not ExtensionRoute.DECLARATIVE:
        raise ExtensionStoreError("Only DECLARATIVE extensions are reloadable in-process.")
    artifact.validate()
    if artifact.capability_id != manifest.capability_id:
        raise ExtensionStoreError("Manifest/artifact capability identity mismatch.")

    payload = _payload(manifest, artifact)
    envelope = {"payload": payload, "sha256": _digest(payload)}
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(target.suffix + ".tmp")
    temporary.write_text(
        json.dumps(envelope, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    temporary.replace(target)


def _mapping(value: object, name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ExtensionStoreError(f"Stored {name} must be an object.")
    return value


def load_promoted_declarative_extension(path: str | Path) -> PromotedCapability:
    """Verify, reconstruct, activate, and install a stored capability."""
    try:
        envelope = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ExtensionStoreError(f"Cannot read extension store: {exc}") from exc
    envelope_map = _mapping(envelope, "envelope")
    payload = _mapping(envelope_map.get("payload"), "payload")
    digest = envelope_map.get("sha256")
    if not isinstance(digest, str) or digest != _digest(payload):
        raise ExtensionStoreError("Extension store integrity digest mismatch.")
    if payload.get("version") != _STORE_VERSION:
        raise ExtensionStoreError("Unsupported extension store version.")

    manifest_raw = _mapping(payload.get("manifest"), "manifest")
    evidence_raw = _mapping(manifest_raw.get("evidence"), "evidence")
    try:
        evidence = ExtensionEvidence(**{key: bool(value) for key, value in evidence_raw.items()})
        manifest = ExtensionManifest(
            capability_id=str(manifest_raw["capability_id"]),
            label_ja=str(manifest_raw["label_ja"]),
            route=ExtensionRoute(str(manifest_raw["route"])),
            requires_confirmation=bool(manifest_raw["requires_confirmation"]),
            status=ExtensionStatus(str(manifest_raw["status"])),
            evidence=evidence,
            source_reason=str(manifest_raw.get("source_reason", "")),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise ExtensionStoreError(f"Invalid stored manifest: {exc}") from exc

    artifact_raw = _mapping(payload.get("artifact"), "artifact")
    primitives_raw = artifact_raw.get("primitives")
    if not isinstance(primitives_raw, list):
        raise ExtensionStoreError("Stored artifact primitives must be a list.")
    try:
        primitives = tuple(
            DeclarativePrimitiveRef(
                kind=str(_mapping(item, "primitive")["kind"]),
                primitive_id=str(_mapping(item, "primitive")["primitive_id"]),
                config=dict(_mapping(_mapping(item, "primitive").get("config", {}), "primitive config")),
            )
            for item in primitives_raw
        )
        artifact = DeclarativeCapabilityArtifact(
            capability_id=str(artifact_raw["capability_id"]),
            primitives=primitives,
            reusable_contract=str(artifact_raw["reusable_contract"]),
            language_fragment=dict(_mapping(artifact_raw["language_fragment"], "language fragment")),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise ExtensionStoreError(f"Invalid stored artifact: {exc}") from exc

    if manifest.status is not ExtensionStatus.PROMOTED or manifest.promotion_blockers():
        raise ExtensionStoreError("Stored manifest is not blocker-free PROMOTED evidence.")
    if manifest.route is not ExtensionRoute.DECLARATIVE:
        raise ExtensionStoreError("Stored extension is not DECLARATIVE.")
    if manifest.capability_id != artifact.capability_id:
        raise ExtensionStoreError("Stored manifest/artifact capability identity mismatch.")
    artifact.validate()
    activation = activation_from_artifact(artifact)
    try:
        return PROMOTED_CAPABILITIES.install(manifest, activation)
    except ValueError as exc:
        raise ExtensionStoreError(str(exc)) from exc
