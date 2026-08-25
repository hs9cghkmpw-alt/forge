"""Safe typed semantic revisions for Forge Documents (FORGE-019).

Natural language selects an intent.  Only Forge-owned resolution and patching
code can select a document target; callers cannot supply an arbitrary JSON path.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from enum import Enum
from typing import TypeAlias

from app.ai.validators.schema_validator import ValidationResult, validate_forge_document
from forge_ai.core.critic.semantic_design_critic import (
    SemanticDesignFinding,
    evaluate_semantic_design,
)


class SemanticOperationKind(str, Enum):
    SELECT_PRIMARY_METRIC = "select_primary_metric"
    SET_DESIGN_ROLE = "set_design_role"
    SET_EMPHASIS = "set_emphasis"
    SET_VISIBILITY = "set_visibility"
    SET_LAYOUT_VARIANT = "set_layout_variant"
    SET_GROUPING = "set_grouping"
    SET_THEME_TONE = "set_theme_tone"


class TargetResolutionStatus(str, Enum):
    RESOLVED = "resolved"
    AMBIGUOUS = "ambiguous"
    NEEDS_CLARIFICATION = "needs_clarification"
    UNSUPPORTED = "unsupported"


class RevisionMode(str, Enum):
    LOCAL_SEMANTIC_PATCH = "local_semantic_patch"
    FULL_REGEN_FALLBACK = "full_regen_fallback"


@dataclass(frozen=True)
class SemanticTarget:
    screen_id: str
    widget_id: str
    semantic_identity: str


@dataclass(frozen=True)
class SelectPrimaryMetric:
    target: SemanticTarget
    kind: SemanticOperationKind = SemanticOperationKind.SELECT_PRIMARY_METRIC


@dataclass(frozen=True)
class SetDesignRole:
    target: SemanticTarget
    role_id: str
    kind: SemanticOperationKind = SemanticOperationKind.SET_DESIGN_ROLE


SemanticOperation: TypeAlias = SelectPrimaryMetric | SetDesignRole


@dataclass(frozen=True)
class TargetResolution:
    status: TargetResolutionStatus
    target: SemanticTarget | None = None
    reason: str = ""


@dataclass(frozen=True)
class AppliedSemanticRevision:
    document: dict
    operation: SemanticOperation
    changed_widget_ids: tuple[str, ...]
    validation: ValidationResult
    critic: SemanticDesignFinding


def _walk_widgets(node: object):
    if isinstance(node, dict):
        if isinstance(node.get("id"), str):
            yield node
        for value in node.values():
            yield from _walk_widgets(value)
    elif isinstance(node, list):
        for value in node:
            yield from _walk_widgets(value)


def _intent_subject(intent: str) -> str | None:
    normalized = "".join(intent.lower().split())
    if not any(token in normalized for token in ("目立", "強調", "primary", "主指標")):
        return None
    aliases = {
        "残高": "balance",
        "balance": "balance",
        "収入": "income",
        "income": "income",
        "支出": "expense",
        "expense": "expense",
    }
    matches = {identity for token, identity in aliases.items() if token in normalized}
    return next(iter(matches)) if len(matches) == 1 else None


def _semantic_identity(widget: dict) -> str | None:
    text = " ".join(str(widget.get(key, "")).lower() for key in (
        "id", "label", "title", "field", "state_ref", "aggregate",
    ))
    for token, identity in (
        ("残高", "balance"), ("balance", "balance"),
        ("収入", "income"), ("income", "income"),
        ("支出", "expense"), ("expense", "expense"),
    ):
        if token in text:
            return identity
    return None


class TargetResolver:
    """Resolve an intent through semantic metadata, never a caller path."""

    def resolve(self, document: dict, intent: str) -> TargetResolution:
        subject = _intent_subject(intent)
        if subject is None:
            return TargetResolution(TargetResolutionStatus.UNSUPPORTED, reason="unsupported_semantic_intent")
        matches: list[SemanticTarget] = []
        for index, screen in enumerate(document.get("screens", ())):
            screen_id = str(screen.get("id") or f"screen[{index}]")
            for widget in _walk_widgets(screen.get("body")):
                if widget.get("type") == "metric_view" and _semantic_identity(widget) == subject:
                    matches.append(SemanticTarget(screen_id, widget["id"], subject))
        if not matches:
            return TargetResolution(TargetResolutionStatus.NEEDS_CLARIFICATION, reason="semantic_target_not_found")
        if len(matches) > 1:
            return TargetResolution(TargetResolutionStatus.AMBIGUOUS, reason="multiple_semantic_targets")
        return TargetResolution(TargetResolutionStatus.RESOLVED, matches[0])


class SemanticPatchEngine:
    """Apply the closed operation union and always run Validator + Critic."""

    def apply(self, document: dict, operation: SemanticOperation) -> AppliedSemanticRevision:
        after = deepcopy(document)
        changed: list[str] = []
        target_widget: dict | None = None
        target_screen: dict | None = None
        for screen in after.get("screens", ()):
            if screen.get("id") != operation.target.screen_id:
                continue
            target_screen = screen
            for widget in _walk_widgets(screen.get("body")):
                if widget.get("id") == operation.target.widget_id:
                    target_widget = widget
                    break
        if target_widget is None or target_screen is None:
            raise ValueError("resolved semantic target no longer exists")

        desired_role = "metric.primary" if isinstance(operation, SelectPrimaryMetric) else operation.role_id
        if desired_role == "metric.primary":
            for widget in _walk_widgets(target_screen.get("body")):
                if widget is not target_widget and widget.get("style_role") == "metric.primary":
                    identity = _semantic_identity(widget)
                    widget["style_role"] = {
                        "income": "finance.income", "expense": "finance.expense",
                    }.get(identity, "metric.secondary")
                    changed.append(widget["id"])
        if target_widget.get("style_role") != desired_role:
            target_widget["style_role"] = desired_role
            changed.append(target_widget["id"])

        validation = validate_forge_document(after)
        critic = evaluate_semantic_design(after)
        if not validation.valid:
            raise ValueError("semantic patch failed Forge validation")
        if any(issue.severity == "high" for issue in critic.issues):
            raise ValueError("semantic patch failed Semantic Design Critic")
        return AppliedSemanticRevision(after, operation, tuple(changed), validation, critic)


def apply_semantic_intent(document: dict, intent: str) -> AppliedSemanticRevision | TargetResolution:
    resolution = TargetResolver().resolve(document, intent)
    if resolution.status is not TargetResolutionStatus.RESOLVED:
        return resolution
    assert resolution.target is not None
    return SemanticPatchEngine().apply(document, SelectPrimaryMetric(resolution.target))
