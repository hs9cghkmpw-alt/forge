"""Executable activation for promoted declarative capabilities.

Declarative self-extension may only compose primitives already understood by the
loaded Forge Language/runtime.  The activation therefore applies a deliberately
small, validated document transform; it never evaluates generated Python/Dart or
fabricates an unknown widget type at runtime.

This is the executable half of a promoted declarative extension.  The manifest
proves evidence; this activation is what makes the capability affect the retried
Forge document.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from forge_ai.core.compiler import ForgeIRDocument, ForgeIRScreen, ForgeIRWidget
from forge_ai.core.orchestration.declarative_extension import DeclarativeCapabilityArtifact


class DeclarativeActivationError(ValueError):
    pass


def _widget_from_fragment(value: object) -> ForgeIRWidget:
    if not isinstance(value, Mapping):
        raise DeclarativeActivationError("append_widget requires a widget object.")
    widget_type = value.get("type")
    widget_id = value.get("id")
    if not isinstance(widget_type, str) or not widget_type:
        raise DeclarativeActivationError("declarative widget requires non-empty type.")
    if not isinstance(widget_id, str) or not widget_id:
        raise DeclarativeActivationError("declarative widget requires non-empty id.")
    properties = value.get("properties", {})
    if not isinstance(properties, Mapping):
        raise DeclarativeActivationError("declarative widget properties must be an object.")
    children_raw = value.get("children", ())
    if not isinstance(children_raw, (list, tuple)):
        raise DeclarativeActivationError("declarative widget children must be a list.")
    return ForgeIRWidget(
        type=widget_type,
        id=widget_id,
        properties=dict(properties),
        children=tuple(_widget_from_fragment(child) for child in children_raw),
    )


def _contains_id(node: ForgeIRWidget, widget_id: str) -> bool:
    return node.id == widget_id or any(_contains_id(child, widget_id) for child in node.children)


@dataclass(frozen=True, slots=True)
class DeclarativeDocumentActivation:
    """In-process executable activation backed by a validated language fragment.

    Supported fragment v1:
      {"op": "append_widget", "widget": {...}}

    The fragment deliberately composes an existing Forge Language widget.  A
    request needing a genuinely new runtime primitive belongs to BUILD_TIME,
    not this route.
    """

    artifact: DeclarativeCapabilityArtifact

    @property
    def capability_id(self) -> str:
        return self.artifact.capability_id

    def apply(self, document: ForgeIRDocument) -> ForgeIRDocument:
        fragment = self.artifact.language_fragment
        if fragment.get("op") != "append_widget":
            raise DeclarativeActivationError(
                "Loaded declarative runtime supports only append_widget composition; "
                "new primitive behavior requires BUILD_TIME extension."
            )
        widget = _widget_from_fragment(fragment.get("widget"))

        screens: list[ForgeIRScreen] = []
        for screen in document.screens:
            if _contains_id(screen.body, widget.id):
                raise DeclarativeActivationError(
                    f"declarative widget id collision: {widget.id}"
                )
            if screen.body.type == "column":
                body = ForgeIRWidget(
                    type=screen.body.type,
                    id=screen.body.id,
                    properties=dict(screen.body.properties),
                    children=(*screen.body.children, widget),
                )
            else:
                body = ForgeIRWidget(
                    type="column",
                    id=f"extension_root_{widget.id}",
                    children=(screen.body, widget),
                )
            screens.append(ForgeIRScreen(
                id=screen.id,
                title=screen.title,
                state=dict(screen.state),
                body=body,
            ))

        return ForgeIRDocument(
            version=document.version,
            initial_screen_id=document.initial_screen_id,
            screens=tuple(screens),
            app_title=document.app_title,
            record_schemas=dict(document.record_schemas),
            design_tokens=dict(document.design_tokens),
        )


def activation_from_artifact(
    artifact: DeclarativeCapabilityArtifact,
) -> DeclarativeDocumentActivation:
    artifact.validate()
    return DeclarativeDocumentActivation(artifact=artifact)


def apply_promoted_document_activations(
    document: ForgeIRDocument,
    capability_ids: tuple[str, ...],
) -> ForgeIRDocument:
    """Apply requested promoted activations in deterministic request order.

    Registry presence alone is insufficient: an activation must expose the
    executable ``apply`` contract.  This prevents metadata-only capability
    promotion from changing planner truth without changing the generated app.
    """
    from forge_ai.core.orchestration.extension_registry import PROMOTED_CAPABILITIES

    current = document
    seen: set[str] = set()
    for capability_id in capability_ids:
        if capability_id in seen:
            continue
        seen.add(capability_id)
        item = PROMOTED_CAPABILITIES.get(capability_id)
        if item is None:
            continue
        activation = item.activation
        apply = getattr(activation, "apply", None)
        if not callable(apply):
            raise DeclarativeActivationError(
                f"Promoted capability {capability_id!r} has no executable document activation."
            )
        current = apply(current)
    return current
