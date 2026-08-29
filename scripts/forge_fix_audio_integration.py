from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def replace_once(rel: str, old: str, new: str) -> None:
    path = ROOT / rel
    text = path.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{rel}: expected one target, got {count}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")

replace_once(
    "forge_ai/tests/test_semantic_roles_and_capability_plan.py",
    '''    def test_a_game_names_what_is_missing(self) -> None:\n        """**無いものを checklist で代用して黙らない。**"""\n        plan = plan_capabilities(GAME)\n        self.assertIn("simulate.loop", plan.requested)\n        self.assertIn("simulate.loop", plan.simulations)\n        self.assertNotIn("simulate.loop", plan.missing)\n        self.assertIn("effect.media_compose", plan.missing)\n''',
    '''    def test_a_game_keeps_partial_audio_truth_explicit(self) -> None:\n        """実装済みsimulationとPARTIALな内蔵音源mixを混同しない。"""\n        plan = plan_capabilities(GAME)\n        self.assertIn("simulate.loop", plan.requested)\n        self.assertIn("simulate.loop", plan.simulations)\n        self.assertNotIn("simulate.loop", plan.missing)\n        self.assertIn("interact.audio_mix", plan.interactions)\n        self.assertIn("interact.audio_mix", plan.partial)\n        self.assertNotIn("effect.media_compose", plan.requested)\n''',
)

replace_once(
    "frontend/lib/json_ui/widget_registry/widget_registry_v1_14.dart",
    '''        if (mounted) setState(() => _active.remove(track));\n''',
    '''        if (mounted) {\n          setState(() => _active.remove(track));\n        }\n''',
)
replace_once(
    "frontend/lib/json_ui/widget_registry/widget_registry_v1_14.dart",
    '''      if (mounted) setState(() => _error = '音を再生できませんでした');\n''',
    '''      if (mounted) {\n        setState(() => _error = '音を再生できませんでした');\n      }\n''',
)
