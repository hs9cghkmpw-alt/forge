from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def replace_once(rel: str, old: str, new: str) -> None:
    p = ROOT / rel
    text = p.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{rel}: expected one target, got {count}")
    p.write_text(text.replace(old, new, 1), encoding="utf-8")

replace_once(
    "backend/app/ai/runtime/prompt_pipeline.py",
    '''    names.extend(getattr(plan, "interactions", ()) or ())\n    names.extend(getattr(plan, "effects", ()) or ())\n''',
    '''    names.extend(getattr(plan, "interactions", ()) or ())\n    names.extend(getattr(plan, "effects", ()) or ())\n    names.extend(getattr(plan, "simulations", ()) or ())\n''',
)

replace_once(
    "frontend/test/features/app_generation/data/datasources/mock_generator_renderer_contract_test.dart",
    '''      ForgeMetricViewWidgetNode() => 'metric_view',\n      ForgeUnknownWidgetNode() => 'unknown',\n''',
    '''      ForgeMetricViewWidgetNode() => 'metric_view',\n      // v1.13: deterministic simulation driver. Keep this deliberately\n      // duplicated black-box contract exhaustive when the sealed vocabulary grows.\n      ForgeSimulationLoopWidgetNode() => 'simulation_loop',\n      ForgeUnknownWidgetNode() => 'unknown',\n''',
)
