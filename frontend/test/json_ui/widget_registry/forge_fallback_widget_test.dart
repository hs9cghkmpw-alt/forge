// ForgeFallbackWidget Widget Test(FORGE-MERGE-003 Task 2)。
//
// json_ui/ 側の中で最も依存の少ない(ForgeRuntimeStateもRiverpodも不要な)
// Widgetを選び、Runtime層に対するWidget Testの足がかりとした。
// `flutter test` はdebugモード相当で実行される(kDebugMode = true)という
// 前提に立っている。この前提はClaude環境では検証していない。
//
// 注記: Claudeのサンドボックスに Dart SDK が無いため、このファイルは
// 一度も `flutter test` で実行されていない。CEO環境での実行が必須。

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:forge_app/json_ui/widget_registry/widget_registry.dart';

void main() {
  testWidgets('ForgeFallbackWidget shows the reason text (debug mode)', (tester) async {
    await tester.pumpWidget(
      const MaterialApp(
        home: Scaffold(
          body: ForgeFallbackWidget(reason: 'テスト用の理由テキスト'),
        ),
      ),
    );

    expect(find.text('テスト用の理由テキスト'), findsOneWidget);
    expect(find.byIcon(Icons.warning_amber_rounded), findsOneWidget);
    expect(tester.takeException(), isNull);
  });

  testWidgets('ForgeFallbackWidget never throws regardless of reason content', (tester) async {
    // 未知Widgetのtype名など、任意の文字列が理由として渡ってくる想定。
    // 特殊文字や長い文字列でもクラッシュしないことを確認する。
    await tester.pumpWidget(
      const MaterialApp(
        home: Scaffold(
          body: ForgeFallbackWidget(reason: r'記号 !@#$%^&*() 長い理由テキストxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx'),
        ),
      ),
    );
    expect(tester.takeException(), isNull);
  });
}
