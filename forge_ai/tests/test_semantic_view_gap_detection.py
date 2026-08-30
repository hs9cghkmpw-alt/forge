from __future__ import annotations

from forge_ai.core.orchestration.extension_plan import (
    ExtensionRoute,
    plan_extension_candidates,
)
from forge_ai.core.orchestration.extension_registry import PROMOTED_CAPABILITIES
from forge_ai.core.semantics.capability_plan import StructuralMode, plan_capabilities


def test_map_only_request_survives_as_exact_capability_gap() -> None:
    PROMOTED_CAPABILITIES.clear()
    plan = plan_capabilities("地図で見たい")

    assert plan.structure is StructuralMode.UNKNOWN
    assert plan.requested == ("view.map",)
    assert plan.missing == ("view.map",)
    assert plan.views == ()

    candidates = plan_extension_candidates(plan.missing)
    assert len(candidates) == 1
    assert candidates[0].capability_id == "view.map"
    assert candidates[0].routes == (
        ExtensionRoute.DECLARATIVE,
        ExtensionRoute.BUILD_TIME,
    )


def test_record_request_with_map_keeps_record_semantics_and_gap() -> None:
    PROMOTED_CAPABILITIES.clear()
    plan = plan_capabilities("釣った魚の場所を地図で見たい")

    assert plan.structure is StructuralMode.RECORD_ENTITY
    assert "data.text" in plan.requested
    assert "view.list" in plan.requested
    assert "view.map" in plan.requested
    assert "view.map" in plan.missing
    assert "view.map" not in plan.views


def test_calendar_and_line_chart_are_detected_without_role_pattern_duplication() -> None:
    PROMOTED_CAPABILITIES.clear()
    calendar = plan_capabilities("カレンダーで見たい")
    line = plan_capabilities("折れ線で見たい")

    assert calendar.missing == ("view.calendar",)
    assert line.missing == ("view.line_chart",)
