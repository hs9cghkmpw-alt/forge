import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:forge_app/json_ui/renderer/forge_runtime_state.dart';
import 'package:forge_app/json_ui/schema/forge_document.dart';
import 'package:forge_app/json_ui/widget_registry/widget_registry.dart';

Future<void> _waitForBrowserAudio(WidgetTester tester) async {
  // Web plugins complete through real browser promises/events, not only the
  // widget-test fake clock. Give those callbacks real wall-clock time, then
  // pump once so the resulting setState is reflected in the widget tree.
  await tester.runAsync(() async {
    await Future<void>.delayed(const Duration(milliseconds: 1000));
  });
  await tester.pump();
}

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
    await _waitForBrowserAudio(tester);
    final pulseException = tester.takeException();
    if (pulseException != null) {
      fail('pulse web-audio exception: $pulseException');
    }
    final pulseChip = tester.widget<FilterChip>(pulse);
    if (!pulseChip.selected) {
      final userErrorVisible = find.text('音を再生できませんでした').evaluate().isNotEmpty;
      fail('pulse playback did not activate; userErrorVisible=$userErrorVisible');
    }

    await tester.tap(chime);
    await _waitForBrowserAudio(tester);
    final chimeException = tester.takeException();
    if (chimeException != null) {
      fail('chime web-audio exception: $chimeException');
    }
    expect(tester.widget<FilterChip>(pulse).selected, isTrue);
    final chimeChip = tester.widget<FilterChip>(chime);
    if (!chimeChip.selected) {
      final userErrorVisible = find.text('音を再生できませんでした').evaluate().isNotEmpty;
      fail('chime playback did not activate; userErrorVisible=$userErrorVisible');
    }
    expect(find.text('音を再生できませんでした'), findsNothing);

    await tester.pumpWidget(const SizedBox.shrink());
    await tester.pump();
  });
}
