from dataclasses import replace

from forge_ai.core.semantics import capability_plan as plan_module
from forge_ai.core.semantics.capabilities import CapabilityDefinition, SupportLevel


def test_simulation_is_a_first_class_plan_axis(monkeypatch):
    original = plan_module.SEMANTIC_CAPABILITIES["simulate.loop"]
    implemented = replace(original, support=SupportLevel.IMPLEMENTED, limitation="")
    monkeypatch.setitem(plan_module.SEMANTIC_CAPABILITIES, "simulate.loop", implemented)

    plan = plan_module.plan_capabilities("植物を育てながら音を組み合わせるゲームを作りたい")

    assert "simulate.loop" in plan.requested
    assert plan.simulations == ("simulate.loop",)
    assert "simulate.loop" not in plan.missing
