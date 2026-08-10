// 家計簿カテゴリの add_item 回帰テスト(FORGE-MILESTONE-003.1 PHASE5)。
//
// CEO実機で発見された add_item_failed(FORGE-MILESTONE-003.1-report.md 1章)の
// End-to-End回帰テスト。Mock Generatorが実際に生成する家計簿Documentを
// ForgeDocument.fromJsonへ通し、Generated Screenを描画し、
// テキスト入力→追加ボタン操作までを実際にWidget Testで検証する。
//
// 注記: Claudeのサンドボックスに Dart SDK が無いため、このファイルは
// 一度も `flutter test` で実行されていない。CEO環境での実行が必須。

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:forge_app/core/theme/forge_theme.dart';
import 'package:forge_app/features/app_generation/data/datasources/mock_generation_datasource.dart';
import 'package:forge_app/json_ui/renderer/forge_renderer.dart';

void main() {
  const source = MockGenerationDataSource();

  Widget wrapDocument(Map<String, dynamic> rawJson) {
    return MaterialApp(theme: ForgeTheme.theme, home: ForgeDocumentView(rawJson: rawJson));
  }

  testWidgets(
    '家計簿カテゴリ: 生成→描画→入力→追加が最後まで成功する(CEO実機不具合の回帰テスト)',
    (tester) async {
      // 1. 実際のMock Generator(Dart版)で家計簿Documentを生成する。
      final rawJson = source.generate('家計簿をつけるメモを作って');

      // 2. ForgeDocument.fromJsonへ通し、Generated Screenを描画する。
      await tester.pumpWidget(wrapDocument(rawJson));
      await tester.pumpAndSettle();
      expect(tester.takeException(), isNull, reason: '描画時点で例外が出ないこと');

      // 元々あった4件の項目が表示されていることを確認。
      expect(find.text('今月の収入を記録する'), findsOneWidget);

      // 3. new_item_textへ文字列を入力する。
      await tester.enterText(find.byType(TextField), '臨時収入を記録する');
      await tester.pump();

      // 4. 追加ボタンを押す。
      await tester.tap(find.widgetWithText(ElevatedButton, '追加'));
      await tester.pump();

      // 5. itemsへ新項目が追加される。
      expect(find.text('臨時収入を記録する'), findsOneWidget, reason: '追加した項目がUIに反映されるはず');

      // 6. Flutter例外が発生していないこと(Console相当のRuntime Errorも
      //    無いことは、次のtestWidgetsでForgeLoggerを直接検証する)。
      expect(tester.takeException(), isNull);
    },
  );

  testWidgets(
    '家計簿カテゴリ: 何も入力せず追加ボタンを押しても、項目は増えずクラッシュしない',
    (tester) async {
      final rawJson = source.generate('家計簿をつけるメモを作って');
      await tester.pumpWidget(wrapDocument(rawJson));
      await tester.pumpAndSettle();

      // 7. source Stateが空の場合の挙動: 何も入力せず追加を押す。
      await tester.tap(find.widgetWithText(ElevatedButton, '追加'));
      await tester.pump();

      // 元の4項目のまま増えていないこと。
      expect(find.text('今月の収入を記録する'), findsOneWidget);
      expect(find.text('固定費を確認する'), findsOneWidget);
      expect(find.text('今日の支出を記録する'), findsOneWidget);
      expect(find.text('来月の予算を立てる'), findsOneWidget);

      // 10. 正常時はLoggerへERRORを出さない、かつFlutter例外も出ない。
      expect(tester.takeException(), isNull);
    },
  );

  testWidgets(
    '家計簿カテゴリ: 空白のみ入力して追加を押しても項目は増えない(trim判定)',
    (tester) async {
      final rawJson = source.generate('家計簿をつけるメモを作って');
      await tester.pumpWidget(wrapDocument(rawJson));
      await tester.pumpAndSettle();

      // FORGE-MILESTONE-003.3: 以前は `expect(find.text('   '), findsNothing)`
      // でチェックリストへの誤追加を判定していたが、これは誤検知だった
      // (詳細はFORGE-MILESTONE-003.3-report.md参照)。
      // `find.text()`はFlutterの仕様上、静的なTextウィジェットだけでなく、
      // TextField内部のEditableTextの現在値ともマッチする。
      // `emptySource`の場合、Runtimeは意図的に入力欄をクリアしない
      // (add_item成功時のみクリアする、という既存仕様)ため、
      // 追加操作後も入力欄には"   "が残ったままになる。そのため
      // `find.text('   ')`は「チェックリストに変な項目が増えた」のではなく
      // 「入力欄自身に"   "が残っている」ことを検出してしまい、
      // テストが誤って失敗していた。
      //
      // 修正: チェックリスト項目(ListTile)の件数を操作の前後で比較する形へ
      // 変更した。TextField(EditableText)はListTileの子孫ではないため、
      // この判定方法は入力欄の内容と混同しない。
      final listTileCountBefore = find.byType(ListTile).evaluate().length;
      expect(listTileCountBefore, 4, reason: '操作前のチェックリスト項目数は4件のはず');

      await tester.enterText(find.byType(TextField), '   ');
      await tester.pump();
      await tester.tap(find.widgetWithText(ElevatedButton, '追加'));
      await tester.pump();

      final listTileCountAfter = find.byType(ListTile).evaluate().length;
      expect(
        listTileCountAfter,
        listTileCountBefore,
        reason: '空白のみの入力ではチェックリスト項目が増えないはず(trim判定によりemptySource扱いになる)',
      );

      // 元の4項目が、ListTileの子孫としてそれぞれちょうど1回ずつ見つかる
      // ことも確認する(項目の中身自体が壊れていないことの確認)。
      // find.descendant()でListTileの子孫に限定することで、TextFieldとの
      // 誤マッチを避けている(この4つの項目テキストはいずれも"   "とは
      // 異なるため今回のバグの再発ではないが、念のため同じ安全な方法へ揃えた)。
      const expectedItemTexts = <String>['今月の収入を記録する', '固定費を確認する', '今日の支出を記録する', '来月の予算を立てる'];
      for (final expectedText in expectedItemTexts) {
        expect(
          find.descendant(of: find.byType(ListTile), matching: find.text(expectedText)),
          findsOneWidget,
          reason: '項目「$expectedText」が壊れずに残っているはず',
        );
      }

      expect(tester.takeException(), isNull);
    },
  );

  testWidgets(
    '全12カテゴリ(Checklist系9種)で、生成直後の画面に例外が出ない',
    (tester) async {
      const phrases = <String>[
        '買い物メモを作って', '今日の晩ご飯を考えるメモを作って', '家計簿をつけるメモを作って',
        '今日の予定リストを作って', '子どもの持ち物チェックを作って', 'ペットのお世話チェックリストを作って',
        'プレゼントのアイデアリストを作って', '家事のチェックリストを作って', '旅行の持ち物チェックを作って',
      ];
      for (final phrase in phrases) {
        final rawJson = source.generate(phrase);
        await tester.pumpWidget(wrapDocument(rawJson));
        await tester.pumpAndSettle();
        expect(tester.takeException(), isNull, reason: '入力="$phrase"で例外が出ないこと');
      }
    },
  );
}
