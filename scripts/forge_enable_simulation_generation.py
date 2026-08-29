from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def replace_once(rel: str, old: str, new: str) -> None:
    path = ROOT / rel
    text = path.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{rel}: expected exactly one target, got {count}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


# 1) Carry the semantic simulation axis into Forge Language compilation and
# materialize a real v1.13 simulation_loop + numeric runtime state.
compiler = "forge_ai/core/ir/forge_language_compiler.py"
replace_once(
    compiler,
    '''    def compile(\n        self, ir: ForgeIR, *, domain_category: str, title: str,\n        design_intent: "DesignIntent | None" = None,\n        layout_emphasis: str = "",\n    ) -> ForgeIRDocument:\n''',
    '''    def compile(\n        self, ir: ForgeIR, *, domain_category: str, title: str,\n        design_intent: "DesignIntent | None" = None,\n        layout_emphasis: str = "",\n        simulation_capabilities: tuple[str, ...] = (),\n    ) -> ForgeIRDocument:\n''',
)
replace_once(
    compiler,
    '''        shape = select_solution_shape(entity)\n        if shape is SolutionShape.CHECKLIST:\n            return self._compile_checklist_screen(entity, safe_title, domain_category=domain_category)\n\n        return self._compile_single_screen(\n                entity, safe_title, layout_emphasis=layout_emphasis,\n            include_crud=edit_form_view is not None, domain_category=domain_category,\n            design_intent=design_intent,\n        )\n\n    def _compile_checklist_screen(\n''',
    '''        shape = select_solution_shape(entity)\n        if shape is SolutionShape.CHECKLIST:\n            document = self._compile_checklist_screen(entity, safe_title, domain_category=domain_category)\n        else:\n            document = self._compile_single_screen(\n                entity, safe_title, layout_emphasis=layout_emphasis,\n                include_crud=edit_form_view is not None, domain_category=domain_category,\n                design_intent=design_intent,\n            )\n\n        if "simulate.loop" in simulation_capabilities:\n            document = self._attach_simulation_loop(document)\n        return document\n\n    @staticmethod\n    def _attach_simulation_loop(document: ForgeIRDocument) -> ForgeIRDocument:\n        """Attach the deterministic v1.13 simulation driver to every screen.\n\n        The semantic plan decides *whether* time progression is required; this\n        compiler decides the concrete Forge Language primitive.  The driver is\n        intentionally invisible and writes only to a bounded number state.\n        Reserved identifiers fail closed instead of silently overwriting\n        generated state.\n        """\n        state_ref = "simulation_tick"\n        widget_id = "simulation_loop_driver"\n\n        def contains_id(node: ForgeIRWidget) -> bool:\n            return node.id == widget_id or any(contains_id(child) for child in node.children)\n\n        screens: list[ForgeIRScreen] = []\n        for screen in document.screens:\n            if state_ref in screen.state:\n                raise ForgeLanguageCompilationError(\n                    f"simulation state id collision: {state_ref}"\n                )\n            if contains_id(screen.body):\n                raise ForgeLanguageCompilationError(\n                    f"simulation widget id collision: {widget_id}"\n                )\n\n            driver = ForgeIRWidget(\n                type="simulation_loop",\n                id=widget_id,\n                properties={\n                    "state_ref": state_ref,\n                    "step_ms": 250,\n                    "max_ticks_per_advance": 40,\n                },\n            )\n            if screen.body.type == "column":\n                body = ForgeIRWidget(\n                    type=screen.body.type,\n                    id=screen.body.id,\n                    properties=dict(screen.body.properties),\n                    children=(driver, *screen.body.children),\n                )\n            else:\n                body = ForgeIRWidget(\n                    type="column", id="simulation_root",\n                    children=(driver, screen.body),\n                )\n            screens.append(ForgeIRScreen(\n                id=screen.id,\n                title=screen.title,\n                state={\n                    **screen.state,\n                    state_ref: ForgeIRStateValue(type="number", value=0),\n                },\n                body=body,\n            ))\n\n        return ForgeIRDocument(\n            version="1.13",\n            initial_screen_id=document.initial_screen_id,\n            screens=tuple(screens),\n            app_title=document.app_title,\n            record_schemas=dict(document.record_schemas),\n            design_tokens=dict(document.design_tokens),\n        )\n\n    def _compile_checklist_screen(\n''',
)

# 2) Production orchestration passes the simulation axis into the compiler.
replace_once(
    "forge_ai/core/orchestration/pipeline_orchestrator.py",
    '''                    layout_emphasis=compose_layout(capability_plan).value,\n                )\n''',
    '''                    layout_emphasis=compose_layout(capability_plan).value,\n                    simulation_capabilities=capability_plan.simulations,\n                )\n''',
)

# 3) Runtime adapter binds the semantic capability to the real widget.
replace_once(
    "backend/app/ai/runtime/capability.py",
    '''    "interact.edit": ("form", "record_list_view"),\n    # PARTIAL のものは**近いもので代用している**という結び付きを持つ。\n''',
    '''    "interact.edit": ("form", "record_list_view"),\n    "simulate.loop": ("simulation_loop",),\n    # PARTIAL のものは**近いもので代用している**という結び付きを持つ。\n''',
)

# 4) Only now that production generation + runtime exist, flip the SoT support.
replace_once(
    "forge_ai/core/semantics/capabilities.py",
    '''    _c("simulate.loop", _L.SIMULATE, "時間を進める・ゲームとして動かす",\n       "放っておいても状態が変わる", _S.MISSING,\n       detection_keywords=("ゲーム", "育て", "育成"),\n       limitation="時間経過やゲームループは作れません"),\n''',
    '''    _c("simulate.loop", _L.SIMULATE, "時間を進める・ゲームとして動かす",\n       "放っておいても状態が変わる", _S.IMPLEMENTED,\n       detection_keywords=("ゲーム", "育て", "育成")),\n''',
)
replace_once(
    "forge_ai/core/semantics/capabilities.py",
    '''    SIMULATE = "simulate"\n    """時間経過・生成的な振る舞い。Forge はまだ1つも持っていない。"""\n''',
    '''    SIMULATE = "simulate"\n    """時間経過・生成的な振る舞い。`simulate.loop` は実Runtimeまで実装済み。"""\n''',
)

# 5) Update focused truth tests that encoded the old missing state.
replace_once(
    "forge_ai/tests/test_semantic_roles_and_capability_plan.py",
    '''        self.assertIn("simulate.loop", plan.missing)\n''',
    '''        self.assertIn("simulate.loop", plan.requested)\n        self.assertIn("simulate.loop", plan.simulations)\n        self.assertNotIn("simulate.loop", plan.missing)\n''',
)
replace_once(
    "backend/tests/test_forge_020a3b_capability_id_integrity.py",
    '''        self.assertIn("simulate.loop", missing)\n''',
    '''        self.assertIn("simulate.loop", ok)\n        self.assertNotIn("simulate.loop", missing)\n''',
)
replace_once(
    "backend/tests/test_forge_qg_v2_r4_capability_planning.py",
    '''        self.assertIn("unsupported:simulate.loop", record.capabilities)\n        self.assertIn("unsupported:effect.media_compose", record.capabilities)\n''',
    '''        self.assertIn("simulate.loop", record.capabilities)\n        self.assertIn("unsupported:effect.media_compose", record.capabilities)\n''',
)
replace_once(
    "backend/tests/test_forge_020a3b_partial_is_not_success.py",
    '''        self.assertIn("unsupported:simulate.loop", record.capabilities)\n        self.assertNotIn("simulate.loop", record.capabilities)\n''',
    '''        self.assertIn("unsupported:effect.media_compose", record.capabilities)\n        self.assertNotIn("effect.media_compose", record.capabilities)\n''',
)
replace_once(
    "backend/tests/test_forge_020a3b_partial_is_not_success.py",
    '''        loop = next(\n            u for u in record.capability_usage if u.capability_id == "simulate.loop"\n        )\n        self.assertTrue(loop.requested)\n        self.assertFalse(loop.used)\n        self.assertIs(loop.status, CapabilityUsageStatus.MISSING)\n''',
    '''        media = next(\n            u for u in record.capability_usage if u.capability_id == "effect.media_compose"\n        )\n        self.assertTrue(media.requested)\n        self.assertFalse(media.used)\n        self.assertIs(media.status, CapabilityUsageStatus.MISSING)\n''',
)
replace_once(
    "backend/tests/test_forge_020a2_capability_disclosure.py",
    '''        self.assertIn("simulate.loop", gap["missing"])\n        self.assertIn("effect.media_compose", gap["missing"])\n''',
    '''        self.assertNotIn("simulate.loop", gap["missing"])\n        self.assertIn("effect.media_compose", gap["missing"])\n''',
)
replace_once(
    "backend/tests/test_forge_020a2_capability_disclosure.py",
    '''        self.assertIn("simulate.loop", missing)\n        self.assertIn("effect.media_compose", missing)\n''',
    '''        self.assertNotIn("simulate.loop", missing)\n        self.assertIn("effect.media_compose", missing)\n''',
)
replace_once(
    "backend/tests/test_forge_020a2_capability_disclosure.py",
    '''        self.assertTrue(by_id["simulate.loop"].requested)\n        self.assertFalse(by_id["simulate.loop"].used)\n''',
    '''        self.assertTrue(by_id["simulate.loop"].requested)\n        self.assertTrue(by_id["simulate.loop"].used)\n        self.assertIs(by_id["simulate.loop"].status, CapabilityUsageStatus.IMPLEMENTED)\n''',
)

# 6) Strong production binding proof: the game request must actually use the
# simulation widget, not merely declare support.
replace_once(
    "backend/tests/test_forge_020a2_capability_sot.py",
    '''            ("旅行の写真を日付ごとに残してメモを付けたい",\n             ("data.date", "data.photo", "view.list")),\n''',
    '''            ("旅行の写真を日付ごとに残してメモを付けたい",\n             ("data.date", "data.photo", "view.list")),\n            ("植物を育てながら音を組み合わせるゲームを作りたい",\n             ("simulate.loop",)),\n''',
)

# 7) Direct compiler-level proof independent of API/evidence plumbing.
test_path = ROOT / "forge_ai/tests/test_simulation_capability_generation.py"
test_path.write_text(
    '''from forge_ai.core.ir.capability_ir import entity_spec_from_plan\nfrom forge_ai.core.ir.forge_language_compiler import ForgeLanguageCompiler\nfrom forge_ai.core.ir.ir_generator import IRGenerator\nfrom forge_ai.core.semantics.capability_plan import plan_capabilities\n\n\nGAME = "植物を育てながら音を組み合わせるゲームを作りたい"\n\n\ndef _walk(node):\n    yield node\n    for child in node.get("children", []):\n        yield from _walk(child)\n\n\ndef test_game_plan_materializes_real_simulation_loop():\n    plan = plan_capabilities(GAME)\n    assert plan.simulations == ("simulate.loop",)\n    spec = entity_spec_from_plan(plan)\n    assert spec is not None\n    ir = IRGenerator().build_from_spec(spec)\n    doc = ForgeLanguageCompiler().compile(\n        ir, domain_category="generic", title="育成ゲーム",\n        simulation_capabilities=plan.simulations,\n    ).to_json_dict()\n\n    assert doc["version"] == "1.13"\n    for screen in doc["screens"]:\n        assert screen["state"]["simulation_tick"] == {"type": "number", "value": 0}\n        loops = [n for n in _walk(screen["body"]) if n.get("type") == "simulation_loop"]\n        assert len(loops) == 1\n        assert loops[0]["state_ref"] == "simulation_tick"\n''',
    encoding="utf-8",
)
