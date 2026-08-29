from forge_ai.core.ir.capability_ir import entity_spec_from_plan
from forge_ai.core.ir.forge_language_compiler import ForgeLanguageCompiler
from forge_ai.core.ir.ir_generator import IRGenerator
from forge_ai.core.semantics.capability_plan import plan_capabilities

GAME = "植物を育てながら音を組み合わせるゲームを作りたい"


def _walk(node):
    yield node
    for child in node.get("children", []):
        yield from _walk(child)


def test_sound_combine_is_audio_mix_not_generic_media_export():
    plan = plan_capabilities(GAME)
    assert "interact.audio_mix" in plan.interactions
    assert "effect.media_compose" not in plan.requested
    assert all(field.capability != "data.audio" for field in plan.fields)


def test_audio_mix_materializes_real_v114_widget():
    plan = plan_capabilities(GAME)
    spec = entity_spec_from_plan(plan)
    assert spec is not None
    ir = IRGenerator().build_from_spec(spec)
    doc = ForgeLanguageCompiler().compile(
        ir, domain_category="generic", title="育成ゲーム",
        simulation_capabilities=plan.simulations,
        interaction_capabilities=plan.interactions,
    ).to_json_dict()
    assert doc["version"] == "1.14"
    widgets = [w for screen in doc["screens"] for w in _walk(screen["body"])]
    assert sum(w.get("type") == "simulation_loop" for w in widgets) == 1
    assert sum(w.get("type") == "audio_mixer" for w in widgets) == 1
