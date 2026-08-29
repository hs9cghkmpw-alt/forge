import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:forge_app/json_ui/renderer/forge_runtime_state.dart';
import 'package:forge_app/json_ui/schema/forge_document.dart';
import 'package:forge_app/json_ui/widget_registry/widget_registry.dart';

void main() {
  testWidgets('real web audio backend can start two bundled layers', (tester) async {
    final node = ForgeWidgetNode.fromJson(const {
      'type': 'audio_mixer',
      'id': 'mixer',
      'title': 'Web audio probe',
      'tracks': ['pulse', 'chime'],
    }, '/body');
    final runtime = ForgeRuntimeState(const <String, ForgeStateValue>{});

    await tester.pumpWidget(MaterialApp(
      home: Builder(
        builder: (context) => buildForgeWidget(
          context,
          node,
          runtime,
          buildDefaultForgeRegistry(),
          (_) => const SizedBox.shrink(),
        ),
      ),
    ));

    final pulse = find.byKey(const ValueKey('audio_mixer_pulse'));
    final chime = find.byKey(const ValueKey('audio_mixer_chime'));
    expect(pulse, findsOneWidget);
    expect(chime, findsOneWidget);

    await tester.tap(pulse);
    await tester.pump(const Duration(milliseconds: 800));
    expect(tester.widget<FilterChip>(pulse).selected, isTrue,
        reason: 'pulse must become active only after AudioPlayer.play succeeds');
    expect(find.text('音を再生できませんでした'), findsNothing);

    await tester.tap(chime);
    await tester.pump(const Duration(milliseconds: 800));
    expect(tester.widget<FilterChip>(pulse).selected, isTrue);
    expect(tester.widget<FilterChip>(chime).selected, isTrue,
        reason: 'two local AudioPlayers must be able to run simultaneously');
    expect(find.text('音を再生できませんでした'), findsNothing);
  });
}
