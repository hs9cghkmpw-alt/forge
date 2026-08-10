// Buttonレイアウト回帰テスト(FORGE-RUNTIME-003 Task 5)。
//
// 根本原因(ForgeTheme.elevatedButtonTheme の旧 `Size.fromHeight(56)` が
// `Size(double.infinity, 56)` を意味し、Row内で「BoxConstraints forces an
// infinite width」を起こしていた)の回帰を防ぐため、`ForgeTheme.theme`を
// 適用した状態でButtonを様々な親レイアウトに置いても安全に描画できることを
// 検証する。すべてのテストで`ForgeTheme.theme`を明示的に使う(既定の
// MaterialAppテーマでは、そもそも今回のバグを再現しないため無意味になる)。
//
// viewport指定について: `tester.view.physicalSize`(非推奨の
// `tester.binding.window.physicalSizeTestValue`ではなく)が現行の正しいAPI。
// 既定のテストviewportサイズは800x600(論理ピクセル)であることを確認済み
// (Flutter公式ドキュメント・Issue #12994等)。そのため「800x600 viewport」の
// シナリオは明示的な指定なしで満たされる。
//
// 注記: Claudeのサンドボックスに Dart SDK が無いため、このファイルは
// 一度も `flutter test` で実行されていない。CEO環境での実行が必須。

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:forge_app/core/theme/forge_theme.dart';

Widget _button({VoidCallback? onPressed}) {
  return ElevatedButton(
    onPressed: onPressed ?? () {},
    child: const Text('追加'),
  );
}

Widget _wrapWithTheme(Widget child) {
  return MaterialApp(
    theme: ForgeTheme.theme,
    home: Scaffold(body: child),
  );
}

void main() {
  testWidgets('1. Button単体(Scaffold body直下)', (tester) async {
    await tester.pumpWidget(_wrapWithTheme(Center(child: _button())));
    expect(find.byType(ElevatedButton), findsOneWidget);
    expect(tester.takeException(), isNull);
    await tester.tap(find.byType(ElevatedButton));
    await tester.pump();
    expect(tester.takeException(), isNull);
  });

  testWidgets('2. ButtonをColumn内へ配置', (tester) async {
    await tester.pumpWidget(_wrapWithTheme(Column(children: [_button()])));
    expect(find.byType(ElevatedButton), findsOneWidget);
    expect(tester.takeException(), isNull);
  });

  testWidgets('3. ButtonをRow内へ配置(根本原因が発生していた組み合わせ)', (tester) async {
    await tester.pumpWidget(_wrapWithTheme(Row(children: [_button()])));
    expect(find.byType(ElevatedButton), findsOneWidget);
    expect(tester.takeException(), isNull);
    await tester.tap(find.byType(ElevatedButton));
    await tester.pump();
    expect(tester.takeException(), isNull);
  });

  testWidgets('4. ButtonをSingleChildScrollView内へ配置', (tester) async {
    await tester.pumpWidget(_wrapWithTheme(SingleChildScrollView(child: _button())));
    expect(find.byType(ElevatedButton), findsOneWidget);
    expect(tester.takeException(), isNull);
  });

  testWidgets('5. Row→Column→ScrollViewの構造(add_rowと同じ入れ子)', (tester) async {
    await tester.pumpWidget(
      _wrapWithTheme(
        SingleChildScrollView(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Row(
                children: [
                  const Expanded(child: TextField()),
                  _button(),
                ],
              ),
            ],
          ),
        ),
      ),
    );
    expect(find.byType(ElevatedButton), findsOneWidget);
    expect(tester.takeException(), isNull);
    await tester.tap(find.byType(ElevatedButton));
    await tester.pump();
    expect(tester.takeException(), isNull);
  });

  testWidgets('6. Buttonを複数個Row内へ配置', (tester) async {
    await tester.pumpWidget(
      _wrapWithTheme(Row(children: [_button(), _button(), _button()])),
    );
    expect(find.byType(ElevatedButton), findsNWidgets(3));
    expect(tester.takeException(), isNull);
  });

  testWidgets('7. 800x600 viewport(flutter testの既定サイズ、明示指定なし)', (tester) async {
    // 既定のテストviewportが800x600であることを前提にした確認テスト。
    await tester.pumpWidget(_wrapWithTheme(Row(children: [_button()])));
    expect(tester.view.physicalSize / tester.view.devicePixelRatio, const Size(800, 600));
    expect(find.byType(ElevatedButton), findsOneWidget);
    expect(tester.takeException(), isNull);
  });

  testWidgets('8. 狭いviewport(320x600)でも致命的に崩れない', (tester) async {
    tester.view.physicalSize = const Size(320, 600);
    tester.view.devicePixelRatio = 1.0;
    addTearDown(tester.view.reset); // このテストで上書きしたview設定を全てリセットする

    await tester.pumpWidget(
      _wrapWithTheme(
        SingleChildScrollView(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Row(children: [const Expanded(child: TextField()), _button()]),
            ],
          ),
        ),
      ),
    );
    expect(find.byType(ElevatedButton), findsOneWidget);
    expect(tester.takeException(), isNull);
  });
}
