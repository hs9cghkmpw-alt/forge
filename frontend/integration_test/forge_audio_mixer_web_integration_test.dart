import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:integration_test/integration_test.dart';

import 'package:forge_app/json_ui/renderer/forge_runtime_state.dart';
import 'package:forge_app/json_ui/schema/forge_document.dart';
import 'package:forge_app/json_ui/widget_registry/widget_registry.dart';

void main() {
  IntegrationTestWidgetsFlutterBinding.ensureInitialized();

  testWidgets('real compiled web app can layer two bundled audio tracks', (tester) async {
    final node = ForgeWidgetNode.fromJson(const {
      'type': 'audio_mixer',
      'id': 'mixer',
      'title': 'Web audio integration probe',
      'tracks': ['pulse', 'chime'],
    }, '/body');
    final runtime = ForgeRuntimeState(const <String, ForgeStateValue>{});

    await tester.pumpWidget(MaterialApp(
      home: Scaffold(
        body: Builder(
          builder: (context) => buildForgeWidget(
            context,
            node,
            runtime,
            buildDefaultForgeRegistry(),
            (_) => const SizedBox.shrink(),
          ),
        ),
      ),
    ));
    await tester.pumpAndSettle();

    final pulse = find.byKey(const ValueKey('audio_mixer_pulse'));
    final chime = find.byKey(const ValueKey('audio_mixer_chime'));
    expect(pulse, findsOneWidget);
    expect(chime, findsOneWidget);

    await tester.tap(pulse);
    await tester.pump(const Duration(seconds: 2));
    final pulseChip = tester.widget<FilterChip>(pulse);
    final pulseError = find.text('音を再生できませんでした').evaluate().isNotEmpty;
    // stdout is deliberately objective evidence in Actions even when matcher
    // output is abbreviated by the web driver.
    // ignore: avoid_print
    print('FORGE_AUDIO_E2E pulse selected=${pulseChip.selected} error=$pulseError');
    expect(pulseError, isFalse, reason: 'pulse playback surfaced the Forge audio error state');
    expect(pulseChip.selected, isTrue, reason: 'pulse did not enter active playback state');

    await tester.tap(chime);
    await tester.pump(const Duration(seconds: 2));
    final pulseStillSelected = tester.widget<FilterChip>(pulse).selected;
    final chimeChip = tester.widget<FilterChip>(chime);
    final chimeError = find.text('音を再生できませんでした').evaluate().isNotEmpty;
    // ignore: avoid_print
    print('FORGE_AUDIO_E2E layered pulse=$pulseStillSelected chime=${chimeChip.selected} error=$chimeError');
    expect(chimeError, isFalse, reason: 'chime playback surfaced the Forge audio error state');
    expect(pulseStillSelected, isTrue, reason: 'starting chime stopped the already-active pulse layer');
    expect(chimeChip.selected, isTrue, reason: 'chime did not enter active playback state');

    await tester.pumpWidget(const SizedBox.shrink());
    await tester.pump();
  });
}
