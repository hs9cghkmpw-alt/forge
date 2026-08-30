from forge_ai.core.semantics.capability_plan import plan_capabilities


def test_simulation_is_serialized_in_plan_evidence() -> None:
    plan = plan_capabilities("植物を育てながら音を組み合わせるゲームを作りたい")
    assert plan.simulations == ("simulate.loop",)
    assert plan.to_dict()["simulations"] == ["simulate.loop"]
