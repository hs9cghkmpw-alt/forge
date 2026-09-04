"""Runtime registry for evidence-gated Forge capability acquisition.

The canonical catalog remains the source of semantic truth. This registry is an
overlay for capabilities already known as PARTIAL/MISSING and acquired through
a verified self-extension lifecycle.

Declarative/composition capabilities may activate immediately when they carry an
executable activation. BUILD_TIME capabilities may activate only after the newly
built runtime has actually been loaded and fingerprint-attested.
"""

from __future__ import annotations

from dataclasses import dataclass

from forge_ai.core.orchestration.extension_activation import CapabilityActivation
from forge_ai.core.orchestration.promotion_verification import (
    verify_promotion_attestation,
)
from forge_ai.core.orchestration.extension_manifest import ExtensionManifest, ExtensionStatus
from forge_ai.core.orchestration.extension_plan import ExtensionRoute


_IMMEDIATE_ROUTES = frozenset({ExtensionRoute.COMPOSITION, ExtensionRoute.DECLARATIVE})


@dataclass(frozen=True, slots=True)
class PromotedCapability:
    capability_id: str
    route: ExtensionRoute
    manifest: ExtensionManifest
    activation: CapabilityActivation


class PromotedCapabilityRegistry:
    """Process-local overlay of capabilities that passed promotion evidence."""

    def __init__(self) -> None:
        self._items: dict[str, PromotedCapability] = {}

    def install(
        self,
        manifest: ExtensionManifest,
        activation: CapabilityActivation | None,
    ) -> PromotedCapability:
        if manifest.status is not ExtensionStatus.PROMOTED:
            raise ValueError("Only PROMOTED extensions may be installed for reuse.")
        if manifest.promotion_blockers():
            raise ValueError("PROMOTED manifest still has evidence blockers; refusing install.")
        # **「通った」という印を信じない**（001A / Major 1）。
        #
        # 以前はここで `promotion_decision_digest` が非空かだけを見ていた。
        # したがって `replace(manifest, status=PROMOTED,
        # promotion_decision_digest="fake")` で通せた。実際に再現した。
        #
        # いまは Attestation（Gate が使った入力一式）で**もう一度 Gate を
        # 走らせて**から受け入れる。偽造するには「本当に Gate を満たす
        # 入力」を作るしかなく、それは偽造ではない。
        if activation is None:
            raise ValueError(
                "PROMOTED manifest has no executable activation; refusing metadata-only reuse."
            )
        if activation.capability_id != manifest.capability_id:
            raise ValueError("Activation changed capability identity; refusing install.")

        # **「通った」という印を信じない**（001A / Major 1）。
        #
        # 以前はここで `promotion_decision_digest` が非空かだけを見ていた。
        # したがって `replace(manifest, status=PROMOTED,
        # promotion_decision_digest="fake")` で通せた。実際に再現した。
        #
        # いまは Attestation（Gate が使った入力一式）で**もう一度 Gate を
        # 走らせて**から受け入れる。偽造するには「本当に Gate を満たす
        # 入力」を作るしかなく、それは偽造ではない。
        verify_promotion_attestation(manifest, activation=activation)

        if manifest.route in _IMMEDIATE_ROUTES:
            pass
        elif manifest.route is ExtensionRoute.BUILD_TIME:
            # Avoid importing build_time_extension here (it imports the registry
            # through the orchestration loop in normal operation). Structural
            # attestation keeps this layer dependency-light while still requiring
            # an actually loaded verified build.
            if getattr(activation, "loaded", False) is not True:
                raise ValueError("BUILD_TIME capability requires a loaded build activation.")
            if not getattr(activation, "build_id", ""):
                raise ValueError("BUILD_TIME activation requires build_id.")
            if not getattr(activation, "runtime_fingerprint", ""):
                raise ValueError("BUILD_TIME activation requires runtime_fingerprint.")
            if not getattr(activation, "source_digest", ""):
                raise ValueError("BUILD_TIME activation requires source_digest.")
        else:
            raise ValueError(
                f"Extension route {manifest.route.value!r} cannot be activated in-process."
            )

        item = PromotedCapability(
            capability_id=manifest.capability_id,
            route=manifest.route,
            manifest=manifest,
            activation=activation,
        )
        self._items[manifest.capability_id] = item
        return item

    def is_promoted(self, capability_id: str) -> bool:
        return capability_id in self._items

    def get(self, capability_id: str) -> PromotedCapability | None:
        return self._items.get(capability_id)

    def items(self) -> tuple[PromotedCapability, ...]:
        """Snapshot of everything promoted, for read-only overlays."""
        return tuple(self._items.values())

    def clear(self) -> None:
        self._items.clear()


PROMOTED_CAPABILITIES = PromotedCapabilityRegistry()


def is_promoted_capability(capability_id: str) -> bool:
    return PROMOTED_CAPABILITIES.is_promoted(capability_id)
