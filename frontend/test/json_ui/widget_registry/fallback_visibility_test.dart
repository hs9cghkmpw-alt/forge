// TD92: **Release で、描けなかった部分が黙って消えない**こと。
//
// ---
//
// ## 何が起きていたか
//
// `ForgeFallbackWidget.build()` は `!kDebugMode` のとき
// `SizedBox.shrink()` を返していた。つまり Release ビルドでは、
// Registry が解決できなかった Widget や構築中に例外を出した Widget が
// **何の痕跡も残さず消えていた**。
//
// 利用者から見ると「元から無い」と「作られなかった」の区別が付かず、
// 画面は成功したように見える。Universal Quality Invariant §3
// 「未対応Capabilityを黙って削り、生成成功として表示する」の禁止事項
// そのものである。
//
// ## 配線破壊試験
//
// `widget_registry_core.dart` の Release 分岐を `SizedBox.shrink()` へ
// 戻すと、このファイルの `Release相当` の group が落ちる。

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:forge_app/json_ui/widget_registry/widget_registry_core.dart';

void main() {
  Future<void> pump(WidgetTester tester, {required bool debug}) async {
    await tester.pumpWidget(MaterialApp(
      home: Scaffold(
        body: ForgeFallbackWidget(
          reason: '未知のWidget type: acquired_grid_view',
          showTechnicalReason: debug,
        ),
      ),
    ));
    await tester.pump();
  }

  group('Release相当', () {
    testWidgets('黙って消えない（利用者に見える本文がある）', (tester) async {
      await pump(tester, debug: false);

      expect(find.text(ForgeFallbackWidget.unavailableMessage), findsOneWidget);
      expect(find.text(ForgeFallbackWidget.unavailableDetail), findsOneWidget);

      // 何も描かない実装（`SizedBox.shrink()`）なら面積が 0 になる。
      final size = tester.getSize(find.byType(ForgeFallbackWidget));
      expect(size.height, greaterThan(0));
      expect(size.width, greaterThan(0));
    });

    testWidgets('内部語彙（Widget type 名・例外文字列）は出さない', (tester) async {
      await pump(tester, debug: false);

      expect(find.textContaining('acquired_grid_view'), findsNothing);
      expect(find.textContaining('未知のWidget type'), findsNothing);
    });

    testWidgets('読み上げでも「まだ表示できていない」と伝わる', (tester) async {
      final handle = tester.ensureSemantics();
      await pump(tester, debug: false);

      expect(find.bySemanticsLabel(ForgeFallbackWidget.unavailableMessage), findsWidgets);
      handle.dispose();
    });
  });

  group('Debug相当', () {
    testWidgets('開発者には技術的な理由をそのまま見せる', (tester) async {
      await pump(tester, debug: true);
      expect(find.textContaining('acquired_grid_view'), findsOneWidget);
    });
  });
}
