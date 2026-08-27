"""Canonical semantic capability catalog.

This module owns capability identity and semantic implementation status. Runtime
packages may bind these ids to widgets, but may not invent semantic ids.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class CapabilityStatus(str, Enum):
    IMPLEMENTED = "implemented"
    PARTIAL = "partial"
    MISSING = "missing"


@dataclass(frozen=True, slots=True)
class SemanticCapability:
    id: str
    status: CapabilityStatus
    description: str
    runtime_binding_required: bool = False
    requires_confirmation: bool = False


_CATALOG = (
    SemanticCapability("record.entity", CapabilityStatus.IMPLEMENTED, "typed record entity"),
    SemanticCapability("record.text", CapabilityStatus.IMPLEMENTED, "text field", True),
    SemanticCapability("record.number", CapabilityStatus.IMPLEMENTED, "number field", True),
    SemanticCapability("record.date", CapabilityStatus.IMPLEMENTED, "date field", True),
    SemanticCapability("record.choice", CapabilityStatus.IMPLEMENTED, "choice field", True),
    SemanticCapability("record.boolean", CapabilityStatus.IMPLEMENTED, "boolean field", True),
    SemanticCapability("record.photo", CapabilityStatus.PARTIAL, "photo metadata only", True),
    SemanticCapability("record.sound", CapabilityStatus.PARTIAL, "sound metadata only", True),
    SemanticCapability("view.list", CapabilityStatus.IMPLEMENTED, "record list", True),
    SemanticCapability("view.total", CapabilityStatus.IMPLEMENTED, "aggregate total", True),
    SemanticCapability("view.group_compare", CapabilityStatus.IMPLEMENTED, "group comparison", True),
    SemanticCapability("view.trend", CapabilityStatus.PARTIAL, "ordered trend approximation", True),
    SemanticCapability("interact.check_off", CapabilityStatus.IMPLEMENTED, "check off", True),
    SemanticCapability("effect.notify", CapabilityStatus.MISSING, "OS notification", requires_confirmation=True),
    SemanticCapability("simulate.loop", CapabilityStatus.MISSING, "game/time loop"),
    SemanticCapability("media.compose", CapabilityStatus.MISSING, "media composition"),
    SemanticCapability("view.grid", CapabilityStatus.IMPLEMENTED, "grid", True),
    SemanticCapability("view.tabs", CapabilityStatus.IMPLEMENTED, "tabs", True),
    SemanticCapability("view.map", CapabilityStatus.MISSING, "map"),
    SemanticCapability("view.heatmap", CapabilityStatus.MISSING, "heatmap"),
    SemanticCapability("view.calendar", CapabilityStatus.MISSING, "calendar"),
    SemanticCapability("effect.share", CapabilityStatus.MISSING, "share", requires_confirmation=True),
    SemanticCapability("effect.camera", CapabilityStatus.MISSING, "camera", requires_confirmation=True),
    SemanticCapability("effect.location", CapabilityStatus.MISSING, "location", requires_confirmation=True),
    SemanticCapability("effect.contacts", CapabilityStatus.MISSING, "contacts", requires_confirmation=True),
    SemanticCapability("effect.payment", CapabilityStatus.MISSING, "payment", requires_confirmation=True),
    SemanticCapability("effect.http", CapabilityStatus.MISSING, "http", requires_confirmation=True),
)

CAPABILITIES: dict[str, SemanticCapability] = {item.id: item for item in _CATALOG}
if len(CAPABILITIES) != len(_CATALOG):
    raise RuntimeError("duplicate canonical semantic capability id")


def capability(capability_id: str) -> SemanticCapability | None:
    return CAPABILITIES.get(capability_id)
