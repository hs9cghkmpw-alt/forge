"""Runtime registry for evidence-gated Forge capability acquisition.

The canonical catalog remains the source of semantic truth.  This registry is an
overlay for capabilities that were already known as PARTIAL/MISSING and have
completed a managed self-extension lifecycle.

Only PROMOTED declarative/composition extensions may become immediately visible
inside the current process.  BUILD_TIME/SERVICE/NATIVE extensions require their
new runtime to be loaded before retry and therefore are not silently activated
here.
"""

from __future__ import annotations

from dataclasses import dataclass

from forge_ai.core.orchestration.extension_manifest import ExtensionManifest, ExtensionStatus
from forge_ai.core.orchestration.extension_plan import ExtensionRoute


_IMMEDIATE_ROUTES = frozenset({ExtensionRoute.COMPOSITION, ExtensionRoute.DECLARATIVE})


@dataclass(frozen=True, slots=True)
class PromotedCapability:
    capability_id: str
    route: ExtensionRoute
    manifest: ExtensionManifest


class PromotedCapabilityRegistry:
    """Process-local overlay of capabilities that passed promotion evidence."""

    def __init__(self) -> None:
        self._items: dict[str, PromotedCapability] = {}

    def install(self, manifest: ExtensionManifest) -> PromotedCapability:
        if manifest.status is not ExtensionStatus.PROMOTED:
            raise ValueError("Only PROMOTED extensions may be installed for reuse.")
        if manifest.promotion_blockers():
            raise ValueError("PROMOTED manifest still has evidence blockers; refusing install.")
        if manifest.route not in _IMMEDIATE_ROUTES:
            raise ValueError(
                f"Extension route {manifest.route.value!r} cannot be activated in-process; "
                "load the produced runtime/build before retrying."
            )
        item = PromotedCapability(
            capability_id=manifest.capability_id,
            route=manifest.route,
            manifest=manifest,
        )
        self._items[manifest.capability_id] = item
        return item

    def is_promoted(self, capability_id: str) -> bool:
        return capability_id in self._items

    def get(self, capability_id: str) -> PromotedCapability | None:
        return self._items.get(capability_id)

    def clear(self) -> None:
        """Test/process reset. Persistent promotion belongs to a durable artifact store."""
        self._items.clear()


PROMOTED_CAPABILITIES = PromotedCapabilityRegistry()


def is_promoted_capability(capability_id: str) -> bool:
    return PROMOTED_CAPABILITIES.is_promoted(capability_id)
