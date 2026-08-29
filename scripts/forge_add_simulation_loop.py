from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def replace_once(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{path}: expected exactly one replacement target, got {count}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


# ---------------------------------------------------------------------------
# Flutter language model: parse + node
# ---------------------------------------------------------------------------
forge_document = ROOT / "frontend/lib/json_ui/schema/forge_document.dart"
replace_once(
    forge_document,
    """        return ForgeSliderWidgetNode(\n          id,\n          stateRef: sliderStateRef,\n          label: json['label'] as String? ?? '',\n          min: rawMin.toDouble(),\n          max: rawMax.toDouble(),\n        );\n      default:\n""",
    """        return ForgeSliderWidgetNode(\n          id,\n          stateRef: sliderStateRef,\n          label: json['label'] as String? ?? '',\n          min: rawMin.toDouble(),\n          max: rawMax.toDouble(),\n        );\n      case 'simulation_loop':\n        // v1.13: deterministic fixed-step simulation lifecycle. The widget owns\n        // scheduling only; arithmetic remains in runtime/forge_simulation.dart.\n        final simulationStateRef = json['state_ref'];\n        if (simulationStateRef is! String || simulationStateRef.isEmpty) {\n          throw ForgeParseException(\n            '$path/state_ref',\n            'simulation_loop.state_ref is required',\n          );\n        }\n        final rawStepMs = json['step_ms'];\n        final rawMaxTicks = json['max_ticks_per_advance'];\n        return ForgeSimulationLoopWidgetNode(\n          id,\n          stateRef: simulationStateRef,\n          stepMilliseconds: rawStepMs is num ? rawStepMs.toInt() : 250,\n          maxTicksPerAdvance: rawMaxTicks is num ? rawMaxTicks.toInt() : 40,\n        );\n      default:\n""",
)
replace_once(
    forge_document,
    """/// Validatorをすり抜けた未知typeに対する、クライアント側の最終防衛線。\nclass ForgeUnknownWidgetNode extends ForgeWidgetNode {\n""",
    """/// v1.13: behavior-only fixed-step simulation loop. The referenced state must\n/// be a number and stores the deterministic emitted tick count.\nclass ForgeSimulationLoopWidgetNode extends ForgeWidgetNode {\n  final String stateRef;\n  final int stepMilliseconds;\n  final int maxTicksPerAdvance;\n\n  const ForgeSimulationLoopWidgetNode(\n    super.id, {\n    required this.stateRef,\n    this.stepMilliseconds = 250,\n    this.maxTicksPerAdvance = 40,\n  });\n}\n\n/// Validatorをすり抜けた未知typeに対する、クライアント側の最終防衛線。\nclass ForgeUnknownWidgetNode extends ForgeWidgetNode {\n""",
)

# ---------------------------------------------------------------------------
# Widget registry + real lifecycle scheduler
# ---------------------------------------------------------------------------
core = ROOT / "frontend/lib/json_ui/widget_registry/widget_registry_core.dart"
replace_once(
    core,
    """      ForgeMetricViewWidgetNode() => 'metric_view',\n      ForgeUnknownWidgetNode() => 'unknown',\n""",
    """      ForgeMetricViewWidgetNode() => 'metric_view',\n      ForgeSimulationLoopWidgetNode() => 'simulation_loop',\n      ForgeUnknownWidgetNode() => 'unknown',\n""",
)

registry = ROOT / "frontend/lib/json_ui/widget_registry/widget_registry.dart"
replace_once(
    registry,
    """import 'widget_registry_v1_11.dart';\n""",
    """import 'widget_registry_v1_11.dart';\nimport 'widget_registry_v1_13.dart';\n""",
)
replace_once(
    registry,
    """  registerV1_11Widgets(registry);\n  return registry;\n""",
    """  registerV1_11Widgets(registry);\n  // v1.13: deterministic simulation lifecycle (`simulate.loop`).\n  registerV1_13Widgets(registry);\n  return registry;\n""",
)

(ROOT / "frontend/lib/json_ui/widget_registry/widget_registry_v1_13.dart").write_text(
    """library;\n\nimport 'dart:async';\n\nimport 'package:flutter/material.dart';\n\nimport '../renderer/forge_runtime_state.dart';\nimport '../runtime/forge_simulation.dart';\nimport '../runtime/forge_simulation_binding.dart';\nimport '../schema/forge_document.dart';\nimport 'widget_registry_core.dart';\n\nvoid registerV1_13Widgets(ForgeWidgetRegistry registry) {\n  registry.register('simulation_loop', _buildSimulationLoop);\n}\n\nWidget _buildSimulationLoop(\n  BuildContext context,\n  ForgeWidgetNode node,\n  ForgeRuntimeState state,\n  Widget Function(ForgeWidgetNode) build,\n) {\n  return _ForgeSimulationLoop(\n    node: node as ForgeSimulationLoopWidgetNode,\n    runtimeState: state,\n  );\n}\n\n/// Lifecycle owner for the deterministic simulation primitive.\n///\n/// Wall-clock scheduling is intentionally kept at this edge. Each timer callback\n/// advances the pure engine by exactly one declared fixed step, so replay tests can\n/// drive the same binding with the same deltas without depending on wall-clock time.\nclass _ForgeSimulationLoop extends StatefulWidget {\n  final ForgeSimulationLoopWidgetNode node;\n  final ForgeRuntimeState runtimeState;\n\n  const _ForgeSimulationLoop({required this.node, required this.runtimeState});\n\n  @override\n  State<_ForgeSimulationLoop> createState() => _ForgeSimulationLoopState();\n}\n\nclass _ForgeSimulationLoopState extends State<_ForgeSimulationLoop> {\n  Timer? _timer;\n  late ForgeSimulationBinding _binding;\n\n  Duration get _step => Duration(milliseconds: widget.node.stepMilliseconds);\n\n  @override\n  void initState() {\n    super.initState();\n    _bindAndStart();\n  }\n\n  void _bindAndStart() {\n    _binding = ForgeSimulationBinding(\n      runtimeState: widget.runtimeState,\n      stateRef: widget.node.stateRef,\n      engine: ForgeSimulationEngine(\n        step: _step,\n        maxTicksPerAdvance: widget.node.maxTicksPerAdvance,\n      ),\n    );\n    _binding.start();\n    _timer = Timer.periodic(_step, (_) => _binding.advance(_step));\n  }\n\n  @override\n  void didUpdateWidget(covariant _ForgeSimulationLoop oldWidget) {\n    super.didUpdateWidget(oldWidget);\n    if (oldWidget.runtimeState != widget.runtimeState ||\n        oldWidget.node.stateRef != widget.node.stateRef ||\n        oldWidget.node.stepMilliseconds != widget.node.stepMilliseconds ||\n        oldWidget.node.maxTicksPerAdvance != widget.node.maxTicksPerAdvance) {\n      _timer?.cancel();\n      _binding.pause();\n      _bindAndStart();\n    }\n  }\n\n  @override\n  void dispose() {\n    _timer?.cancel();\n    _binding.pause();\n    super.dispose();\n  }\n\n  @override\n  Widget build(BuildContext context) {\n    // Behavior-only node: state changes are consumed by ordinary Forge widgets.\n    return SizedBox.shrink(key: ValueKey('simulation_loop_${widget.node.id}'));\n  }\n}\n""",
    encoding="utf-8",
)

# ---------------------------------------------------------------------------
# Production backend validator: language v1.13 + simulation_loop contract
# ---------------------------------------------------------------------------
validator = ROOT / "backend/app/ai/validators/schema_validator.py"
replace_once(
    validator,
    'SUPPORTED_VERSIONS = {"1.0", "1.1", "1.2", "1.3", "1.4", "1.5", "1.6", "1.7", "1.8", "1.9", "1.10", "1.11", "1.12"}',
    'SUPPORTED_VERSIONS = {"1.0", "1.1", "1.2", "1.3", "1.4", "1.5", "1.6", "1.7", "1.8", "1.9", "1.10", "1.11", "1.12", "1.13"}',
)
replace_once(
    validator,
    '_VERSION_ORDER = ("1.0", "1.1", "1.2", "1.3", "1.4", "1.5", "1.6", "1.7", "1.8", "1.9", "1.10", "1.11", "1.12")',
    '_VERSION_ORDER = ("1.0", "1.1", "1.2", "1.3", "1.4", "1.5", "1.6", "1.7", "1.8", "1.9", "1.10", "1.11", "1.12", "1.13")',
)
replace_once(
    validator,
    'WIDGET_TYPES_V1_11_ADDITIONS = {"metric_view"}\n\nWIDGET_TYPES_BY_VERSION',
    'WIDGET_TYPES_V1_11_ADDITIONS = {"metric_view"}\n\n# v1.13: runtime-backed deterministic simulation loop for semantic capability simulate.loop.\nWIDGET_TYPES_V1_13_ADDITIONS = {"simulation_loop"}\n\nWIDGET_TYPES_BY_VERSION',
)
replace_once(
    validator,
    '''    "1.12": (\n        WIDGET_TYPES_V1_0 | WIDGET_TYPES_V1_1_ADDITIONS | WIDGET_TYPES_V1_3_ADDITIONS\n        | WIDGET_TYPES_V1_5_ADDITIONS | WIDGET_TYPES_V1_6_ADDITIONS | WIDGET_TYPES_V1_7_ADDITIONS\n        | WIDGET_TYPES_V1_8_ADDITIONS | WIDGET_TYPES_V1_11_ADDITIONS\n    ),\n}\nWIDGET_TYPES_ALL = (\n''',
    '''    "1.12": (\n        WIDGET_TYPES_V1_0 | WIDGET_TYPES_V1_1_ADDITIONS | WIDGET_TYPES_V1_3_ADDITIONS\n        | WIDGET_TYPES_V1_5_ADDITIONS | WIDGET_TYPES_V1_6_ADDITIONS | WIDGET_TYPES_V1_7_ADDITIONS\n        | WIDGET_TYPES_V1_8_ADDITIONS | WIDGET_TYPES_V1_11_ADDITIONS\n    ),\n    "1.13": (\n        WIDGET_TYPES_V1_0 | WIDGET_TYPES_V1_1_ADDITIONS | WIDGET_TYPES_V1_3_ADDITIONS\n        | WIDGET_TYPES_V1_5_ADDITIONS | WIDGET_TYPES_V1_6_ADDITIONS | WIDGET_TYPES_V1_7_ADDITIONS\n        | WIDGET_TYPES_V1_8_ADDITIONS | WIDGET_TYPES_V1_11_ADDITIONS | WIDGET_TYPES_V1_13_ADDITIONS\n    ),\n}\nWIDGET_TYPES_ALL = (\n''',
)
replace_once(
    validator,
    '''    | WIDGET_TYPES_V1_8_ADDITIONS | WIDGET_TYPES_V1_11_ADDITIONS\n)  # 未知Widget判定用\n''',
    '''    | WIDGET_TYPES_V1_8_ADDITIONS | WIDGET_TYPES_V1_11_ADDITIONS | WIDGET_TYPES_V1_13_ADDITIONS\n)  # 未知Widget判定用\n''',
)
replace_once(
    validator,
    '    "1.12": ACTION_TYPES_V1_0 | ACTION_TYPES_V1_2_ADDITIONS | ACTION_TYPES_V1_3_ADDITIONS,\n}',
    '    "1.12": ACTION_TYPES_V1_0 | ACTION_TYPES_V1_2_ADDITIONS | ACTION_TYPES_V1_3_ADDITIONS,\n    "1.13": ACTION_TYPES_V1_0 | ACTION_TYPES_V1_2_ADDITIONS | ACTION_TYPES_V1_3_ADDITIONS,\n}',
)
replace_once(
    validator,
    '    "1.12": STATE_TYPES_V1_0 | STATE_TYPES_V1_2_ADDITIONS | STATE_TYPES_V1_3_ADDITIONS,\n}',
    '    "1.12": STATE_TYPES_V1_0 | STATE_TYPES_V1_2_ADDITIONS | STATE_TYPES_V1_3_ADDITIONS,\n    "1.13": STATE_TYPES_V1_0 | STATE_TYPES_V1_2_ADDITIONS | STATE_TYPES_V1_3_ADDITIONS,\n}',
)
replace_once(
    validator,
    '''    elif t == "divider":\n        errors.extend(_check_additional_properties(widget, {"type", "id"}, path))\n''',
    '''    elif t == "simulation_loop":\n        errors.extend(_check_additional_properties(\n            widget, {"type", "id", "state_ref", "step_ms", "max_ticks_per_advance"}, path\n        ))\n        if not _is_identifier(widget.get("state_ref")):\n            errors.append(_err(f"{path}/state_ref", Category.SCHEMA, "required",\n                               "simulation_loop.state_refは必須です。"))\n        step_ms = widget.get("step_ms", 250)\n        if isinstance(step_ms, bool) or not isinstance(step_ms, int) or not (16 <= step_ms <= 60_000):\n            errors.append(_err(f"{path}/step_ms", Category.RUNTIME_SAFETY, "range",\n                               "simulation_loop.step_msは16〜60000の整数です。"))\n        max_ticks = widget.get("max_ticks_per_advance", 40)\n        if isinstance(max_ticks, bool) or not isinstance(max_ticks, int) or not (1 <= max_ticks <= 1000):\n            errors.append(_err(f"{path}/max_ticks_per_advance", Category.RUNTIME_SAFETY, "range",\n                               "simulation_loop.max_ticks_per_advanceは1〜1000の整数です。"))\n\n    elif t == "divider":\n        errors.extend(_check_additional_properties(widget, {"type", "id"}, path))\n''',
)

# ---------------------------------------------------------------------------
# Tests: parser/registry/lifecycle and backend version gate
# ---------------------------------------------------------------------------
(ROOT / "frontend/test/json_ui/forge_simulation_loop_widget_test.dart").write_text(
    """import 'package:flutter/material.dart';\nimport 'package:flutter_test/flutter_test.dart';\n\nimport 'package:forge_studio/json_ui/renderer/forge_runtime_state.dart';\nimport 'package:forge_studio/json_ui/schema/forge_document.dart';\nimport 'package:forge_studio/json_ui/widget_registry/widget_registry.dart';\n\nvoid main() {\n  test('simulation_loop parses as a real Forge node', () {\n    final node = ForgeWidgetNode.fromJson(\n      const {\n        'type': 'simulation_loop',\n        'id': 'loop',\n        'state_ref': 'ticks',\n        'step_ms': 50,\n        'max_ticks_per_advance': 8,\n      },\n      '/body',\n    );\n\n    expect(node, isA<ForgeSimulationLoopWidgetNode>());\n    final simulation = node as ForgeSimulationLoopWidgetNode;\n    expect(simulation.stateRef, 'ticks');\n    expect(simulation.stepMilliseconds, 50);\n    expect(simulation.maxTicksPerAdvance, 8);\n  });\n\n  testWidgets('simulation_loop advances Forge number state and stops on dispose', (tester) async {\n    final runtime = ForgeRuntimeState(\n      <String, ForgeStateValue>{'ticks': const ForgeNumberState(0)},\n    );\n    final node = ForgeWidgetNode.fromJson(\n      const {'type': 'simulation_loop', 'id': 'loop', 'state_ref': 'ticks', 'step_ms': 50},\n      '/body',\n    );\n    final registry = buildDefaultForgeRegistry();\n\n    await tester.pumpWidget(\n      MaterialApp(\n        home: Builder(\n          builder: (context) => buildForgeWidget(\n            context,\n            node,\n            runtime,\n            registry,\n            (_) => const SizedBox.shrink(),\n          ),\n        ),\n      ),\n    );\n\n    expect(runtime.getNumber('ticks'), 0);\n    await tester.pump(const Duration(milliseconds: 120));\n    expect(runtime.getNumber('ticks'), 2);\n\n    await tester.pumpWidget(const MaterialApp(home: SizedBox.shrink()));\n    final stoppedAt = runtime.getNumber('ticks');\n    await tester.pump(const Duration(milliseconds: 200));\n    expect(runtime.getNumber('ticks'), stoppedAt);\n  });\n}\n""",
    encoding="utf-8",
)

(ROOT / "backend/tests/test_forge_v1_13_simulation_loop.py").write_text(
    """import json\n\nfrom app.ai.validators.schema_validator import validate_forge_document_from_text\n\n\ndef _doc(version: str) -> dict:\n    return {\n        \"version\": version,\n        \"app\": {\"title\": \"Simulation\"},\n        \"initial_screen_id\": \"main\",\n        \"screens\": [\n            {\n                \"id\": \"main\",\n                \"title\": \"Simulation\",\n                \"state\": {\"ticks\": {\"type\": \"number\", \"value\": 0}},\n                \"body\": {\n                    \"type\": \"simulation_loop\",\n                    \"id\": \"loop\",\n                    \"state_ref\": \"ticks\",\n                    \"step_ms\": 50,\n                    \"max_ticks_per_advance\": 8,\n                },\n            }\n        ],\n    }\n\n\ndef test_v1_13_accepts_simulation_loop():\n    result = validate_forge_document_from_text(json.dumps(_doc(\"1.13\")))\n    assert result.valid, [e.to_dict() for e in result.errors]\n\n\ndef test_v1_12_rejects_simulation_loop():\n    result = validate_forge_document_from_text(json.dumps(_doc(\"1.12\")))\n    assert not result.valid\n    assert any(e.rule == \"widget_not_allowed_in_version\" for e in result.errors)\n\n\ndef test_v1_13_rejects_unsafe_simulation_frequency():\n    doc = _doc(\"1.13\")\n    doc[\"screens\"][0][\"body\"][\"step_ms\"] = 1\n    result = validate_forge_document_from_text(json.dumps(doc))\n    assert not result.valid\n    assert any(e.path.endswith(\"/step_ms\") for e in result.errors)\n""",
    encoding="utf-8",
)

print("simulation_loop vertical slice patch staged")
