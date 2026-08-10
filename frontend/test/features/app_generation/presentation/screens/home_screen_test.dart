// HomeScreen Widget Test(FORGE-MERGE-003 Task 2、2026-07-16 UI刷新に伴い更新)。
//
// 2026-07-17(FORGE v0.2 P5): HomeScreenへ「最近のアプリ」表示
// (`ref.watch(savedAppsProvider)`)を追加したため、`ProviderScope`と
// `sharedPreferencesProvider`のoverrideが必須になった(以前は
// Riverpodを一切使わずテストできていたが、今回の変更で前提が変わった)。
// また、「話すだけで」というコピー(マイク機能が無いのに音声入力を
// 示唆していた、指示書P5「マイク未実装なら削除」)を
// 「アイデアを入力するだけで」へ変更したため、該当テストも更新した。
//
// 注記: Claudeのサンドボックスに Dart SDK が無いため、このファイルは
// 一度も `flutter test` で実行されていない。CEO環境での実行が必須。

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:forge_app/features/app_generation/presentation/screens/home_screen.dart';
import 'package:forge_app/features/app_library/presentation/providers/app_library_provider.dart';
import 'package:shared_preferences/shared_preferences.dart';

void main() {
  Future<Widget> wrap(Widget child) async {
    SharedPreferences.setMockInitialValues({});
    final prefs = await SharedPreferences.getInstance();
    return ProviderScope(
      overrides: [sharedPreferencesProvider.overrideWithValue(prefs)],
      child: MaterialApp(home: child),
    );
  }

  testWidgets('send button is disabled when input is empty', (tester) async {
    await tester.pumpWidget(await wrap(const HomeScreen()));
    await tester.pump();

    final sendInkWell = tester.widget<InkWell>(
      find.ancestor(of: find.byIcon(Icons.arrow_upward_rounded), matching: find.byType(InkWell)),
    );
    expect(sendInkWell.onTap, isNull);
  });

  testWidgets('send button becomes enabled after typing text', (tester) async {
    await tester.pumpWidget(await wrap(const HomeScreen()));
    await tester.pump();

    await tester.enterText(find.byType(TextField), '買い物メモを作って');
    await tester.pump();

    final sendInkWell = tester.widget<InkWell>(
      find.ancestor(of: find.byIcon(Icons.arrow_upward_rounded), matching: find.byType(InkWell)),
    );
    expect(sendInkWell.onTap, isNotNull);
  });

  testWidgets('tapping an example in the picker sheet fills the field but does not auto-navigate', (tester) async {
    await tester.pumpWidget(await wrap(const HomeScreen()));
    await tester.pump();

    await tester.tap(find.text('例を見る'));
    await tester.pumpAndSettle();

    await tester.tap(find.text('ToDoリストを作りたい'));
    await tester.pumpAndSettle();

    // Bottom Sheetは文章を入れるだけで送信しない、という仕様
    // (Prototype v0.1.3から継承、旧`_onCardTap`と同じ方針)そのものを検証する。
    final textField = tester.widget<TextField>(find.byType(TextField));
    expect(textField.controller?.text, 'ToDoリストを作りたい');
    expect(find.text('アプリを作成しています…'), findsNothing); // 生成中画面へ未遷移の確認
    expect(tester.takeException(), isNull);
  });

  testWidgets('all five example items are shown in the picker sheet', (tester) async {
    await tester.pumpWidget(await wrap(const HomeScreen()));
    await tester.pump();

    await tester.tap(find.text('例を見る'));
    await tester.pumpAndSettle();

    for (final title in [
      '家計簿アプリを作りたい',
      'ToDoリストを作りたい',
      '日記アプリを作りたい',
      '釣果記録アプリを作りたい',
      '子どもの成長記録を作りたい',
    ]) {
      expect(find.text(title), findsOneWidget, reason: '例 "$title" が見つからない');
    }
  });

  testWidgets('home screen shows the Forge headline (without implying voice input) and safety notice',
      (tester) async {
    await tester.pumpWidget(await wrap(const HomeScreen()));
    await tester.pump();

    // FORGE v0.2 P5対応: マイク機能を実装していないため、「話すだけで」
    // という誤解を招くコピーは使わない。実際のコピーへ更新した。
    expect(find.textContaining('アイデアを入力するだけで'), findsOneWidget);
    expect(find.textContaining('話すだけで'), findsNothing);
    expect(find.text('会話内容は安全に保護されます'), findsOneWidget);
  });

  testWidgets('home screen does not show a microphone icon or a non-functional profile button', (tester) async {
    await tester.pumpWidget(await wrap(const HomeScreen()));
    await tester.pump();

    // FORGE v0.2 P5対応: マイク未実装のためアイコンを削除。
    // アカウント機能の無いプロフィールボタンも削除した。
    expect(find.byIcon(Icons.mic_none_rounded), findsNothing);
    expect(find.byIcon(Icons.person_outline_rounded), findsNothing);
  });
}
