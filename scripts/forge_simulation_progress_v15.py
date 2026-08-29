from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def replace_once(rel: str, old: str, new: str) -> None:
    p = ROOT / rel
    text = p.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{rel}: expected one target, got {count}")
    p.write_text(text.replace(old, new, 1), encoding="utf-8")

# Dart parser/model.
schema = "frontend/lib/json_ui/schema/forge_document.dart"
replace_once(
    schema,
    '''      case 'audio_mixer':\n        final rawTracks = json['tracks'];\n''',
    '''      case 'simulation_progress':\n        final progressStateRef = json['state_ref'];\n        if (progressStateRef is! String || progressStateRef.isEmpty) {\n          throw ForgeParseException('$path/state_ref', 'simulation_progress.state_ref is required');\n        }\n        final rawStages = json['stages'];\n        if (rawStages is! List || rawStages.isEmpty) {\n          throw ForgeParseException('$path/stages', 'simulation_progress.stages is required');\n        }\n        final ticksPerStage = json['ticks_per_stage'];\n        if (ticksPerStage is! num || ticksPerStage.toInt() <= 0) {\n          throw ForgeParseException('$path/ticks_per_stage', 'simulation_progress.ticks_per_stage must be positive');\n        }\n        return ForgeSimulationProgressWidgetNode(\n          id,\n          stateRef: progressStateRef,\n          title: json['title'] as String? ?? '進行',\n          stages: rawStages.cast<String>(),\n          ticksPerStage: ticksPerStage.toInt(),\n        );\n      case 'audio_mixer':\n        final rawTracks = json['tracks'];\n''',
)
replace_once(
    schema,
    '''/// v1.14: user-driven local sound-layer mixer. Track identifiers are a closed\n/// Forge vocabulary and never arbitrary paths or URLs.\nclass ForgeAudioMixerWidgetNode extends ForgeWidgetNode {\n''',
    '''/// v1.15: visible projection of deterministic simulation state. The widget\n/// never advances time itself; it only renders the number state driven by\n/// simulation_loop, keeping scheduling and presentation separate.\nclass ForgeSimulationProgressWidgetNode extends ForgeWidgetNode {\n  final String stateRef;\n  final String title;\n  final List<String> stages;\n  final int ticksPerStage;\n  const ForgeSimulationProgressWidgetNode(\n    super.id, {\n    required this.stateRef,\n    required this.title,\n    required this.stages,\n    required this.ticksPerStage,\n  });\n}\n\n/// v1.14: user-driven local sound-layer mixer. Track identifiers are a closed\n/// Forge vocabulary and never arbitrary paths or URLs.\nclass ForgeAudioMixerWidgetNode extends ForgeWidgetNode {\n''',
)

core = "frontend/lib/json_ui/widget_registry/widget_registry_core.dart"
replace_once(
    core,
    '''      ForgeMetricViewWidgetNode() => 'metric_view',\n      ForgeAudioMixerWidgetNode() => 'audio_mixer',\n''',
    '''      ForgeMetricViewWidgetNode() => 'metric_view',\n      ForgeSimulationProgressWidgetNode() => 'simulation_progress',\n      ForgeAudioMixerWidgetNode() => 'audio_mixer',\n''',
)

main = "frontend/lib/json_ui/widget_registry/widget_registry.dart"
replace_once(main, "import 'widget_registry_v1_14.dart';\n", "import 'widget_registry_v1_14.dart';\nimport 'widget_registry_v1_15.dart';\n")
replace_once(main, "  registerV1_14Widgets(registry);\n  return registry;\n", "  registerV1_14Widgets(registry);\n  registerV1_15Widgets(registry);\n  return registry;\n")

(ROOT / "frontend/lib/json_ui/widget_registry/widget_registry_v1_15.dart").write_text(
'''library;\n\nimport 'package:flutter/material.dart';\n\nimport '../renderer/forge_runtime_state.dart';\nimport '../schema/forge_document.dart';\nimport 'widget_registry_core.dart';\n\nvoid registerV1_15Widgets(ForgeWidgetRegistry registry) {\n  registry.register('simulation_progress', _buildSimulationProgress);\n}\n\nWidget _buildSimulationProgress(\n  BuildContext context,\n  ForgeWidgetNode node,\n  ForgeRuntimeState state,\n  Widget Function(ForgeWidgetNode) build,\n) {\n  final n = node as ForgeSimulationProgressWidgetNode;\n  return AnimatedBuilder(\n    animation: state,\n    builder: (context, _) {\n      final tick = state.getNumber(n.stateRef).floor().clamp(0, 1 << 30);\n      final rawStage = tick ~/ n.ticksPerStage;\n      final stageIndex = rawStage.clamp(0, n.stages.length - 1);\n      final stage = n.stages[stageIndex];\n      final terminal = stageIndex == n.stages.length - 1;\n      final within = tick % n.ticksPerStage;\n      final progress = terminal ? 1.0 : within / n.ticksPerStage;\n      return Card(\n        key: const ValueKey('simulation_progress'),\n        child: Padding(\n          padding: const EdgeInsets.all(16),\n          child: Column(\n            crossAxisAlignment: CrossAxisAlignment.stretch,\n            children: [\n              Text(n.title, style: Theme.of(context).textTheme.titleMedium),\n              const SizedBox(height: 8),\n              Text(stage, key: const ValueKey('simulation_stage'),\n                   style: Theme.of(context).textTheme.headlineSmall),\n              const SizedBox(height: 10),\n              LinearProgressIndicator(\n                key: const ValueKey('simulation_stage_progress'),\n                value: progress.clamp(0.0, 1.0),\n              ),\n            ],\n          ),\n        ),\n      );\n    },\n  );\n}\n''', encoding="utf-8")

# Exhaustive duplicated contract.
replace_once(
    "frontend/test/features/app_generation/data/datasources/mock_generator_renderer_contract_test.dart",
    "      ForgeAudioMixerWidgetNode() => 'audio_mixer',\n",
    "      ForgeAudioMixerWidgetNode() => 'audio_mixer',\n      ForgeSimulationProgressWidgetNode() => 'simulation_progress',\n",
)

# Backend Validator v1.15.
validator = "backend/app/ai/validators/schema_validator.py"
replace_once(validator,
'''SUPPORTED_VERSIONS = {"1.0", "1.1", "1.2", "1.3", "1.4", "1.5", "1.6", "1.7", "1.8", "1.9", "1.10", "1.11", "1.12", "1.13", "1.14"}\n''',
'''SUPPORTED_VERSIONS = {"1.0", "1.1", "1.2", "1.3", "1.4", "1.5", "1.6", "1.7", "1.8", "1.9", "1.10", "1.11", "1.12", "1.13", "1.14", "1.15"}\n''')
replace_once(validator,
'''_VERSION_ORDER = ("1.0", "1.1", "1.2", "1.3", "1.4", "1.5", "1.6", "1.7", "1.8", "1.9", "1.10", "1.11", "1.12", "1.13", "1.14")\n''',
'''_VERSION_ORDER = ("1.0", "1.1", "1.2", "1.3", "1.4", "1.5", "1.6", "1.7", "1.8", "1.9", "1.10", "1.11", "1.12", "1.13", "1.14", "1.15")\n''')
replace_once(validator,
'''WIDGET_TYPES_V1_14_ADDITIONS = {"audio_mixer"}\n\nWIDGET_TYPES_BY_VERSION''',
'''WIDGET_TYPES_V1_14_ADDITIONS = {"audio_mixer"}\nWIDGET_TYPES_V1_15_ADDITIONS = {"simulation_progress"}\n\nWIDGET_TYPES_BY_VERSION''')
replace_once(validator,
'''    "1.14": (\n        WIDGET_TYPES_V1_0 | WIDGET_TYPES_V1_1_ADDITIONS | WIDGET_TYPES_V1_3_ADDITIONS\n        | WIDGET_TYPES_V1_5_ADDITIONS | WIDGET_TYPES_V1_6_ADDITIONS | WIDGET_TYPES_V1_7_ADDITIONS\n        | WIDGET_TYPES_V1_8_ADDITIONS | WIDGET_TYPES_V1_11_ADDITIONS | WIDGET_TYPES_V1_13_ADDITIONS\n        | WIDGET_TYPES_V1_14_ADDITIONS\n    ),\n}\nWIDGET_TYPES_ALL = (\n''',
'''    "1.14": (\n        WIDGET_TYPES_V1_0 | WIDGET_TYPES_V1_1_ADDITIONS | WIDGET_TYPES_V1_3_ADDITIONS\n        | WIDGET_TYPES_V1_5_ADDITIONS | WIDGET_TYPES_V1_6_ADDITIONS | WIDGET_TYPES_V1_7_ADDITIONS\n        | WIDGET_TYPES_V1_8_ADDITIONS | WIDGET_TYPES_V1_11_ADDITIONS | WIDGET_TYPES_V1_13_ADDITIONS\n        | WIDGET_TYPES_V1_14_ADDITIONS\n    ),\n    "1.15": (\n        WIDGET_TYPES_V1_0 | WIDGET_TYPES_V1_1_ADDITIONS | WIDGET_TYPES_V1_3_ADDITIONS\n        | WIDGET_TYPES_V1_5_ADDITIONS | WIDGET_TYPES_V1_6_ADDITIONS | WIDGET_TYPES_V1_7_ADDITIONS\n        | WIDGET_TYPES_V1_8_ADDITIONS | WIDGET_TYPES_V1_11_ADDITIONS | WIDGET_TYPES_V1_13_ADDITIONS\n        | WIDGET_TYPES_V1_14_ADDITIONS | WIDGET_TYPES_V1_15_ADDITIONS\n    ),\n}\nWIDGET_TYPES_ALL = (\n''')
replace_once(validator,
'''    | WIDGET_TYPES_V1_14_ADDITIONS\n)  # 未知Widget判定用\n''',
'''    | WIDGET_TYPES_V1_14_ADDITIONS | WIDGET_TYPES_V1_15_ADDITIONS\n)  # 未知Widget判定用\n''')
replace_once(validator,
'''    "1.14": ACTION_TYPES_V1_0 | ACTION_TYPES_V1_2_ADDITIONS | ACTION_TYPES_V1_3_ADDITIONS,\n}\n''',
'''    "1.14": ACTION_TYPES_V1_0 | ACTION_TYPES_V1_2_ADDITIONS | ACTION_TYPES_V1_3_ADDITIONS,\n    "1.15": ACTION_TYPES_V1_0 | ACTION_TYPES_V1_2_ADDITIONS | ACTION_TYPES_V1_3_ADDITIONS,\n}\n''')
replace_once(validator,
'''    "1.14": STATE_TYPES_V1_0 | STATE_TYPES_V1_2_ADDITIONS | STATE_TYPES_V1_3_ADDITIONS,\n}\n''',
'''    "1.14": STATE_TYPES_V1_0 | STATE_TYPES_V1_2_ADDITIONS | STATE_TYPES_V1_3_ADDITIONS,\n    "1.15": STATE_TYPES_V1_0 | STATE_TYPES_V1_2_ADDITIONS | STATE_TYPES_V1_3_ADDITIONS,\n}\n''')
replace_once(validator,
'''    elif t == "audio_mixer":\n''',
'''    elif t == "simulation_progress":\n        errors.extend(_check_additional_properties(widget, {"type", "id", "state_ref", "title", "stages", "ticks_per_stage"}, path))\n        if not _is_identifier(widget.get("state_ref")):\n            errors.append(_err(f"{path}/state_ref", Category.SCHEMA, "required", "simulation_progress.state_refは必須です。"))\n        if not _is_nonempty_str(widget.get("title"), 80):\n            errors.append(_err(f"{path}/title", Category.SCHEMA, "string_length", "simulation_progress.titleは1〜80文字です。"))\n        stages = widget.get("stages")\n        if not isinstance(stages, list) or not (2 <= len(stages) <= 8) or not all(_is_nonempty_str(s, 40) for s in stages):\n            errors.append(_err(f"{path}/stages", Category.SCHEMA, "array_bounds", "simulation_progress.stagesは2〜8件の短い文字列です。"))\n        ticks = widget.get("ticks_per_stage")\n        if isinstance(ticks, bool) or not isinstance(ticks, int) or not (1 <= ticks <= 10000):\n            errors.append(_err(f"{path}/ticks_per_stage", Category.SCHEMA, "range", "ticks_per_stageは1〜10000の整数です。"))\n\n    elif t == "audio_mixer":\n''')

# Compiler: attach visible progress beside driver and preserve v1.15 through audio attachment.
compiler = "forge_ai/core/ir/forge_language_compiler.py"
replace_once(compiler,
'''            driver = ForgeIRWidget(\n                type="simulation_loop",\n                id=widget_id,\n                properties={\n                    "state_ref": state_ref,\n                    "step_ms": 250,\n                    "max_ticks_per_advance": 40,\n                },\n            )\n            if screen.body.type == "column":\n''',
'''            driver = ForgeIRWidget(\n                type="simulation_loop",\n                id=widget_id,\n                properties={\n                    "state_ref": state_ref,\n                    "step_ms": 250,\n                    "max_ticks_per_advance": 40,\n                },\n            )\n            progress = ForgeIRWidget(\n                type="simulation_progress",\n                id="simulation_progress",\n                properties={\n                    "state_ref": state_ref,\n                    "title": "${entity_label}",\n                    "stages": ["はじまり", "成長中", "育ってきた", "完成"],\n                    "ticks_per_stage": 8,\n                },\n            )\n            if screen.body.type == "column":\n'''.replace('${entity_label}', '進行'))
replace_once(compiler,
'''                    children=(driver, *screen.body.children),\n''',
'''                    children=(driver, progress, *screen.body.children),\n''')
replace_once(compiler,
'''                    children=(driver, screen.body),\n''',
'''                    children=(driver, progress, screen.body),\n''')
replace_once(compiler,
'''            version="1.13",\n''',
'''            version="1.15",\n''')
replace_once(compiler,
'''            version="1.14", initial_screen_id=document.initial_screen_id,\n''',
'''            version=("1.15" if document.version == "1.15" else "1.14"),\n            initial_screen_id=document.initial_screen_id,\n''')

# Widget tests.
(ROOT / "frontend/test/json_ui/forge_simulation_progress_widget_test.dart").write_text(
'''import 'package:flutter/material.dart';\nimport 'package:flutter_test/flutter_test.dart';\nimport 'package:forge_app/json_ui/renderer/forge_runtime_state.dart';\nimport 'package:forge_app/json_ui/schema/forge_document.dart';\nimport 'package:forge_app/json_ui/widget_registry/widget_registry.dart';\n\nvoid main() {\n  testWidgets('simulation progress visibly follows the existing number state', (tester) async {\n    final runtime = ForgeRuntimeState(<String, ForgeStateValue>{'ticks': const ForgeNumberState(0)});\n    final node = ForgeWidgetNode.fromJson(const {\n      'type': 'simulation_progress', 'id': 'progress', 'state_ref': 'ticks',\n      'title': '成長', 'stages': ['種', '芽', '花'], 'ticks_per_stage': 2,\n    }, '/body');\n    await tester.pumpWidget(MaterialApp(home: Builder(builder: (context) =>\n      buildForgeWidget(context, node, runtime, buildDefaultForgeRegistry(), (_) => const SizedBox.shrink()))));\n    expect(find.text('種'), findsOneWidget);\n    runtime.setNumber('ticks', 2);\n    await tester.pump();\n    expect(find.text('芽'), findsOneWidget);\n    runtime.setNumber('ticks', 50);\n    await tester.pump();\n    expect(find.text('花'), findsOneWidget);\n  });\n}\n''', encoding="utf-8")

(ROOT / "backend/tests/test_forge_v1_15_simulation_progress.py").write_text(
'''from app.ai.validators.schema_validator import validate_forge_document\n\ndef _doc(version="1.15"):\n    return {"version": version, "initial_screen_id": "home", "screens": [{\n      "id": "home", "title": "Game",\n      "state": {"tick": {"type": "number", "value": 0}},\n      "body": {"type": "simulation_progress", "id": "progress", "state_ref": "tick",\n               "title": "成長", "stages": ["種", "芽", "花"], "ticks_per_stage": 2}}]}\n\ndef test_v115_accepts_visible_simulation_projection():\n    assert validate_forge_document(_doc()).valid\n\ndef test_v114_rejects_v115_progress_widget():\n    result = validate_forge_document(_doc("1.14"))\n    assert not result.valid\n    assert any(e.rule == "widget_not_allowed_in_version" for e in result.errors)\n''', encoding="utf-8")

# Strengthen direct production test: simulation capability must result in visible projection too.
replace_once(
    "forge_ai/tests/test_simulation_capability_generation.py",
    '''        loops = [n for n in _walk(screen["body"]) if n.get("type") == "simulation_loop"]\n        assert len(loops) == 1\n        assert loops[0]["state_ref"] == "simulation_tick"\n''',
    '''        loops = [n for n in _walk(screen["body"]) if n.get("type") == "simulation_loop"]\n        progress = [n for n in _walk(screen["body"]) if n.get("type") == "simulation_progress"]\n        assert len(loops) == 1\n        assert len(progress) == 1\n        assert loops[0]["state_ref"] == "simulation_tick"\n        assert progress[0]["state_ref"] == "simulation_tick"\n''')
replace_once(
    "forge_ai/tests/test_simulation_capability_generation.py",
    '''    assert doc["version"] == "1.13"\n''',
    '''    assert doc["version"] == "1.15"\n''')
replace_once(
    "forge_ai/tests/test_audio_mix_capability_generation.py",
    '''    assert doc["version"] == "1.14"\n''',
    '''    assert doc["version"] == "1.15"\n''')
replace_once(
    "forge_ai/tests/test_audio_mix_capability_generation.py",
    '''    assert sum(w.get("type") == "simulation_loop" for w in widgets) == 1\n    assert sum(w.get("type") == "audio_mixer" for w in widgets) == 1\n''',
    '''    assert sum(w.get("type") == "simulation_loop" for w in widgets) == 1\n    assert sum(w.get("type") == "simulation_progress" for w in widgets) == 1\n    assert sum(w.get("type") == "audio_mixer" for w in widgets) == 1\n''')
