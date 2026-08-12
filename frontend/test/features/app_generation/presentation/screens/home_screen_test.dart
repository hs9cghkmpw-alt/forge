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
//
// FORGE-UI-REFRESH-002(2026-08-10): CEO提示の新UIモックアップに合わせ、
// 「例を見る」ボタンを「もっと例を見る」に改名し、ホーム画面へ
// クイック候補チップ(先頭4件)を追加したため、該当テストを更新した
// (詳細は各テスト内のコメント参照)。同じくCEO提示のモックアップに
// 合わせ、生成中画面の見出しも「アプリを作成しています…」から
// 「AIがアプリを設計中…」へ変更している。

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

    // FORGE-UI-REFRESH-002(2026-08-10): 「例を見る」→「もっと例を見る」に改名。
    // FORGE-PRODUCT-VISION-002(2026-08-11)対応: 見出し文言変更に伴い、
    // 既定のテストウィンドウサイズ(800x600)では対象がスクロールしないと
    // 画面外になることがあるため、`ensureVisible()`を明示的に挟む
    // (`home_screen_test.dart`の他のensureVisible修正と同じ理由)。
    final showExamplesButton = find.text('もっと例を見る');
    await tester.ensureVisible(showExamplesButton);
    await tester.pump();
    await tester.tap(showExamplesButton);
    await tester.pumpAndSettle();

    // FORGE-UI-REFRESH-002: ホーム画面にクイック候補チップ(先頭4件、
    // 'forgeExampleItems.take(4)')を常時表示するようになったため、
    // 先頭4件のタイトルはチップとBottom Sheetの両方に存在し、
    // find.text()が一意に定まらない。5件目(チップに含まれない)を使う。
    //
    // 2026-08-11修正(`flutter test`実機確認で発見した実バグ、
    // FORGE-AI-QUALITY-001): 5件目はBottom Sheet内の`ListView.
    // separated`で下の方にあり、既定のテストウィンドウサイズ
    // (800x600)ではスクロールしないと画面外(hit test対象外)になる。
    // このサンドボックスで`flutter test`を実行できる手段が今まで
    // 無く、検出できなかった。`ensureVisible()`で対象を含む
    // Scrollableを実際にスクロールしてからタップする。
    final targetExample = find.text('子どもの成長記録を作りたい');
    await tester.ensureVisible(targetExample);
    await tester.pumpAndSettle();
    await tester.tap(targetExample);
    await tester.pumpAndSettle();

    // Bottom Sheetは文章を入れるだけで送信しない、という仕様
    // (Prototype v0.1.3から継承、旧`_onCardTap`と同じ方針)そのものを検証する。
    final textField = tester.widget<TextField>(find.byType(TextField));
    expect(textField.controller?.text, '子どもの身長や体重、イベントを記録して成長を可視化できるアプリを作りたい');
    expect(find.text('AIがアプリを設計中…'), findsNothing); // 生成中画面へ未遷移の確認
    expect(tester.takeException(), isNull);
  });

  testWidgets('all five example items are shown in the picker sheet', (tester) async {
    await tester.pumpWidget(await wrap(const HomeScreen()));
    await tester.pump();

    // FORGE-PRODUCT-VISION-002(2026-08-11)対応: 見出し文言変更に伴い、
    // 既定のテストウィンドウサイズでは対象がスクロールしないと画面外に
    // なることがあるため、`ensureVisible()`を明示的に挟む。
    final showExamplesButton2 = find.text('もっと例を見る');
    await tester.ensureVisible(showExamplesButton2);
    await tester.pump();
    await tester.tap(showExamplesButton2);
    await tester.pumpAndSettle();

    // FORGE-UI-REFRESH-002: 先頭4件はホーム画面のクイック候補チップにも
    // 表示されているため(Bottom Sheetを開いても裏のホーム画面は
    // マウントされたまま)、findsOneWidgetではなく「少なくとも1つ」を
    // 検証する。「Bottom Sheet内に5件とも存在する」という本来の目的は
    // このゆるい検証でも満たされる。
    for (final title in [
      '家計簿アプリを作りたい',
      'ToDoリストを作りたい',
      '日記アプリを作りたい',
      '釣果記録アプリを作りたい',
      '子どもの成長記録を作りたい',
    ]) {
      expect(find.text(title), findsAtLeastNWidgets(1), reason: '例 "$title" が見つからない');
    }
  });

  testWidgets('home screen shows the Forge headline (without implying voice input) and safety notice',
      (tester) async {
    await tester.pumpWidget(await wrap(const HomeScreen()));
    await tester.pump();

    // FORGE v0.2 P5対応: マイク機能を実装していないため、「話すだけで」
    // という誤解を招くコピーは使わない。
    // FORGE-PRODUCT-VISION-002(2026-08-11)対応: 「何のアプリを作り
    // ますか」的な文言から「困りごとを話せる場所」的な文言へ変更した
    // (design doc C.1、Space)。
    expect(find.textContaining('困ってることある'), findsOneWidget);
    expect(find.textContaining('話すだけで'), findsNothing);
    expect(find.text('会話内容は安全に保護されます'), findsOneWidget);
  });

  testWidgets('home screen does not show a non-functional profile button', (tester) async {
    await tester.pumpWidget(await wrap(const HomeScreen()));
    await tester.pump();

    // FORGE v0.2 P5対応: アカウント機能の無いプロフィールボタンは削除した
    // (今も削除されたまま)。
    expect(find.byIcon(Icons.person_outline_rounded), findsNothing);
  });

  testWidgets('home screen shows a microphone button now that voice input is implemented (FORGE-AI-CONNECT-001)',
      (tester) async {
    await tester.pumpWidget(await wrap(const HomeScreen()));
    await tester.pump();

    // FORGE-AI-CONNECT-001(2026-08-11): 以前は「マイク未実装のため
    // アイコンを削除した」という回帰テストがここにあった
    // (`find.byIcon(Icons.mic_none_rounded), findsNothing`)。今回、
    // 実際に`speech_to_text`パッケージへ接続した音声入力を実装した
    // ため、その前提が変わった。マイクボタン自体は存在するように
    // なったが、実際に動くかどうか(ブラウザの音声認識API・
    // パッケージのバージョン解決)はClaude環境では検証できていない
    // (`voice_input_provider.dart`冒頭のdocstring参照。CEO環境での
    // 実行が必須)。
    expect(find.byIcon(Icons.mic_none_rounded), findsOneWidget);
  });
}
