from forge_ai.core.orchestration.extension_registry import PROMOTED_CAPABILITIES
from forge_ai.core.semantics.capability_plan import plan_capabilities


def test_requested_missing_map_is_not_promoted_by_planning():
    PROMOTED_CAPABILITIES.clear()
    plan = plan_capabilities("釣った場所を地図に残して魚の種類を記録したい")
    assert "view.map" in plan.requested
    assert "view.map" in plan.missing
    assert not PROMOTED_CAPABILITIES.is_promoted("view.map")
