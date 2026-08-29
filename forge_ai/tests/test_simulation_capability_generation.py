from forge_ai.core.ir.capability_ir import entity_spec_from_plan
from forge_ai.core.ir.forge_language_compiler import ForgeLanguageCompiler
from forge_ai.core.ir.ir_generator import IRGenerator
from forge_ai.core.semantics.capability_plan import plan_capabilities


GAME = "植物を育てながら音を組み合わせるゲームを作りたい"


def _walk(node):
    yield node
    for child in node.get("children", []):
        yield from _walk(child)


def test_game_plan_materializes_real_simulation_loop():
    plan = plan_capabilities(GAME)
    assert plan.simulations == ("simulate.loop",)
    spec = entity_spec_from_plan(plan)
    assert spec is not None
    ir = IRGenerator().build_from_spec(spec)
    doc = ForgeLanguageCompiler().compile(
        ir, domain_category="generic", title="育成ゲーム",
        simulation_capabilities=plan.simulations,
    ).to_json_dict()

    assert doc["version"] == "1.15"
    for screen in doc["screens"]:
        assert screen["state"]["simulation_tick"] == {"type": "number", "value": 0}
        loops = [n for n in _walk(screen["body"]) if n.get("type") == "simulation_loop"]
        progress = [n for n in _walk(screen["body"]) if n.get("type") == "simulation_progress"]
        assert len(loops) == 1
        assert len(progress) == 1
        assert loops[0]["state_ref"] == "simulation_tick"
        assert progress[0]["state_ref"] == "simulation_tick"
