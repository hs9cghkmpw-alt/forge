import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:forge_studio/json_ui/renderer/forge_runtime_state.dart';
import 'package:forge_studio/json_ui/schema/forge_document.dart';
import 'package:forge_studio/json_ui/widget_registry/widget_registry.dart';

void main() {
  test('audio_mixer parses closed track ids', () {
    final node = ForgeWidgetNode.fromJson(const {
      'type': 'audio_mixer', 'id': 'mixer', 'title': 'Mix',
      'tracks': ['pulse', 'chime', 'bass'],
    }, '/body');
    expect(node, isA<ForgeAudioMixerWidgetNode>());
    final mixer = node as ForgeAudioMixerWidgetNode;
    expect(mixer.tracks, ['pulse', 'chime', 'bass']);
  });

  testWidgets('audio_mixer renders user-driven layer controls', (tester) async {
    final node = ForgeWidgetNode.fromJson(const {
      'type': 'audio_mixer', 'id': 'mixer', 'title': 'Mix',
      'tracks': ['pulse', 'chime', 'bass'],
    }, '/body');
    final runtime = ForgeRuntimeState(const <String, ForgeStateValue>{});
    await tester.pumpWidget(MaterialApp(home: Builder(builder: (context) =>
      buildForgeWidget(context, node, runtime, buildDefaultForgeRegistry(), (_) => const SizedBox.shrink())
    )));
    expect(find.text('Mix'), findsOneWidget);
    expect(find.byKey(const ValueKey('audio_mixer_pulse')), findsOneWidget);
    expect(find.byKey(const ValueKey('audio_mixer_chime')), findsOneWidget);
    expect(find.byKey(const ValueKey('audio_mixer_bass')), findsOneWidget);
  });
}
