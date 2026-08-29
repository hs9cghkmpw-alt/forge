import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:forge_app/json_ui/renderer/forge_runtime_state.dart';
import 'package:forge_app/json_ui/schema/forge_document.dart';
import 'package:forge_app/json_ui/widget_registry/widget_registry.dart';

void main() {
  test('simulation_loop parses as a real Forge node', () {
    final node = ForgeWidgetNode.fromJson(
      const {
        'type': 'simulation_loop',
        'id': 'loop',
        'state_ref': 'ticks',
        'step_ms': 50,
        'max_ticks_per_advance': 8,
      },
      '/body',
    );

    expect(node, isA<ForgeSimulationLoopWidgetNode>());
    final simulation = node as ForgeSimulationLoopWidgetNode;
    expect(simulation.stateRef, 'ticks');
    expect(simulation.stepMilliseconds, 50);
    expect(simulation.maxTicksPerAdvance, 8);
  });

  testWidgets('simulation_loop advances Forge number state and stops on dispose', (tester) async {
    final runtime = ForgeRuntimeState(
      <String, ForgeStateValue>{'ticks': const ForgeNumberState(0)},
    );
    final node = ForgeWidgetNode.fromJson(
      const {'type': 'simulation_loop', 'id': 'loop', 'state_ref': 'ticks', 'step_ms': 50},
      '/body',
    );
    final registry = buildDefaultForgeRegistry();

    await tester.pumpWidget(
      MaterialApp(
        home: Builder(
          builder: (context) => buildForgeWidget(
            context,
            node,
            runtime,
            registry,
            (_) => const SizedBox.shrink(),
          ),
        ),
      ),
    );

    expect(runtime.getNumber('ticks'), 0);
    await tester.pump(const Duration(milliseconds: 120));
    expect(runtime.getNumber('ticks'), 2);

    await tester.pumpWidget(const MaterialApp(home: SizedBox.shrink()));
    final stoppedAt = runtime.getNumber('ticks');
    await tester.pump(const Duration(milliseconds: 200));
    expect(runtime.getNumber('ticks'), stoppedAt);
  });
}
