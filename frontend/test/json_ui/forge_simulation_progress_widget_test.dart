import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:forge_app/json_ui/renderer/forge_runtime_state.dart';
import 'package:forge_app/json_ui/schema/forge_document.dart';
import 'package:forge_app/json_ui/widget_registry/widget_registry.dart';

void main() {
  testWidgets('simulation progress visibly follows the existing number state', (tester) async {
    final runtime = ForgeRuntimeState(<String, ForgeStateValue>{'ticks': const ForgeNumberState(0)});
    final node = ForgeWidgetNode.fromJson(const {
      'type': 'simulation_progress', 'id': 'progress', 'state_ref': 'ticks',
      'title': '成長', 'stages': ['種', '芽', '花'], 'ticks_per_stage': 2,
    }, '/body');
    await tester.pumpWidget(MaterialApp(home: Builder(builder: (context) =>
      buildForgeWidget(context, node, runtime, buildDefaultForgeRegistry(), (_) => const SizedBox.shrink()))));
    expect(find.text('種'), findsOneWidget);
    runtime.setNumber('ticks', 2);
    await tester.pump();
    expect(find.text('芽'), findsOneWidget);
    runtime.setNumber('ticks', 50);
    await tester.pump();
    expect(find.text('花'), findsOneWidget);
  });
}
