from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def replace_once(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{path}: expected exactly one target, got {count}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


plan = ROOT / "forge_ai/core/semantics/capability_plan.py"
replace_once(
    plan,
    '''    interactions: tuple[str, ...] = ()\n    effects: tuple[str, ...] = ()\n\n    structure_capabilities: tuple[str, ...] = ()\n''',
    '''    interactions: tuple[str, ...] = ()\n    effects: tuple[str, ...] = ()\n    simulations: tuple[str, ...] = ()\n    """時間経過・生成的な振る舞い。View/Effectへ混ぜず独立軸で保持する。"""\n\n    structure_capabilities: tuple[str, ...] = ()\n''',
)
replace_once(
    plan,
    '''    effects = tuple(c for c in ok if c.startswith("effect."))\n    field_capabilities = {f.capability for f in field_tuple}\n''',
    '''    effects = tuple(c for c in ok if c.startswith("effect."))\n    simulations = tuple(c for c in ok if c.startswith("simulate."))\n    field_capabilities = {f.capability for f in field_tuple}\n''',
)
replace_once(
    plan,
    '''        views=views, interactions=interactions, effects=effects,\n        structure_capabilities=structure_capabilities,\n''',
    '''        views=views, interactions=interactions, effects=effects, simulations=simulations,\n        structure_capabilities=structure_capabilities,\n''',
)

sot = ROOT / "backend/tests/test_forge_020a2_capability_sot.py"
replace_once(
    sot,
    '''                set(plan.requested) | set(plan.views) | set(plan.interactions)\n                | set(plan.effects) | set(plan.missing) | set(plan.partial)\n''',
    '''                set(plan.requested) | set(plan.views) | set(plan.interactions)\n                | set(plan.effects) | set(plan.simulations) | set(plan.missing) | set(plan.partial)\n''',
)

# Dedicated regression: currently simulate.loop remains MISSING, so the axis is empty.
# Once support flips to IMPLEMENTED the same plan shape will retain it rather than drop it.
test_path = ROOT / "forge_ai/tests/test_simulation_capability_plan_axis.py"
test_path.write_text(
    '''from dataclasses import replace\n\nfrom forge_ai.core.semantics import capability_plan as plan_module\nfrom forge_ai.core.semantics.capabilities import CapabilityDefinition, SupportLevel\n\n\ndef test_simulation_is_a_first_class_plan_axis(monkeypatch):\n    original = plan_module.SEMANTIC_CAPABILITIES["simulate.loop"]\n    implemented = replace(original, support=SupportLevel.IMPLEMENTED, limitation="")\n    monkeypatch.setitem(plan_module.SEMANTIC_CAPABILITIES, "simulate.loop", implemented)\n\n    plan = plan_module.plan_capabilities("植物を育てながら音を組み合わせるゲームを作りたい")\n\n    assert "simulate.loop" in plan.requested\n    assert plan.simulations == ("simulate.loop",)\n    assert "simulate.loop" not in plan.missing\n''',
    encoding="utf-8",
)

print("simulation capability plan axis staged")
