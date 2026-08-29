import 'dart:convert';
import 'dart:io';
import 'dart:ui' as ui;

import 'package:flutter/material.dart';
import 'package:flutter/rendering.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:forge_app/json_ui/renderer/forge_renderer.dart';

void main() {
  final fixturePath = Platform.environment['FORGE_GOLDEN_DOC_PATH'];
  final screenshotPath = Platform.environment['FORGE_GOLDEN_SCREENSHOT_PATH'];

  if (fixturePath == null || screenshotPath == null) {
    test(
      'Golden render probe is workflow-only',
      () {},
      skip: 'requires exact production-generated Forge Document and screenshot path',
    );
    return;
  }

  testWidgets('exact production Golden game renders at phone viewport', (tester) async {
    final raw = jsonDecode(File(fixturePath).readAsStringSync()) as Map<String, dynamic>;
    const captureKey = ValueKey('golden_game_capture');

    await tester.binding.setSurfaceSize(const Size(390, 844));
    addTearDown(() => tester.binding.setSurfaceSize(null));

    await tester.pumpWidget(
      MaterialApp(
        home: RepaintBoundary(
          key: captureKey,
          child: ForgeDocumentView(rawJson: raw),
        ),
      ),
    );
    // Do not pumpAndSettle: a real simulation_loop intentionally owns a periodic timer.
    await tester.pump(const Duration(milliseconds: 500));

    expect(find.byType(ErrorWidget), findsNothing);
    expect(find.byType(FilterChip), findsAtLeastNWidgets(2),
        reason: 'interactive audio layers must be visibly controllable');
    // Assert the actual public audio affordance rather than coupling the visual gate
    // to a Japanese copy choice made upstream. These labels are the concrete controls
    // rendered by the runtime-backed audio_mixer widget.
    expect(find.text('Pulse'), findsOneWidget);
    expect(find.text('Chime'), findsOneWidget);

    final boundary = tester.renderObject<RenderRepaintBoundary>(find.byKey(captureKey));
    final image = await boundary.toImage(pixelRatio: 2.0);
    final bytes = await image.toByteData(format: ui.ImageByteFormat.png);
    if (bytes == null) {
      fail('rendered Golden game could not be encoded as PNG');
    }
    File(screenshotPath).writeAsBytesSync(bytes.buffer.asUint8List());
    expect(File(screenshotPath).lengthSync(), greaterThan(1000));

    // Dispose lifecycle-owned timers/audio widgets before test teardown.
    await tester.pumpWidget(const SizedBox.shrink());
    await tester.pump();
  });
}
