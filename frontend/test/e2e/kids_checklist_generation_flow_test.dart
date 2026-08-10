// E2E相当のWidget Test(FORGE-RUNTIME-002 Task 6、2026-07-17 UI刷新に伴い更新)。
//
// Home → 入力欄へ直接入力 → 送信 → 生成中 → 完成画面 → 「アプリを開く」→
// Generated Screen(Renderer) → チェックリスト表示・操作、までを1つの
// テストで通す。
//
// 2026-07-17: CEO提示のUIモックアップに合わせてHomeScreen・生成フローの
// 画面構成が変わったことに伴い、更新した。
// * 旧: Home(Inspiration Cardタップ)→Confirm(内容確認)→GeneratedAppScreen
// * 新: Home(入力欄へ直接入力)→GenerationFlowScreen(生成中→完成画面→
//   「アプリを開く」でRendererを表示)
// 「子ども」Inspiration Cardは新ExamplePickerSheetの5例には無い
// (ToDo/家計簿/日記/釣果記録/子どもの成長記録のみ)ため、実際の
// ユーザー入力を模して`enterText()`で同じ文言を直接入力する形にした
// (Mock Generatorが受け取る文言・返す結果は変更していない。UIの入力
// 経路が変わっただけ)。
//
// 重要な実装上の注意: GenerationFlowScreenの生成中状態には
// `RotationTransition`(無期限に回転し続けるアニメーション)があるため、
// その状態を経由する間は`pumpAndSettle()`を使ってはならない
// (アニメーションが終わらない = 永遠にsettleしない = タイムアウトする)。
// 代わりに`pump(Duration)`で時間を明示的に進める。
//
// 注記: Claudeのサンドボックスに Dart SDK が無いため、このファイルは
// 一度も `flutter test` で実行されていない。CEO環境での実行が必須
// (タイミング関連のテストは特に、実行してみないと確信が持てない)。
//
// 2026-07-17(FORGE v0.2 P0/P5): 完成画面の「アプリを開く」「保存して
// あとで見る」が実際に`SharedPreferences`へ保存するようになったため、
// `SharedPreferences.setMockInitialValues({})`でテスト用の空ストアを
// 用意し、`sharedPreferencesProvider`を`overrideWithValue`する必要が
// 生じた(していないと`UnimplementedError`が飛び、テストが失敗する)。
//
// 2026-07-17(FORGE v0.2 Backend接続): `AppConfig.mockMode`の既定値が
// `false`(実Backend接続が既定)へ変わったため、このE2Eテストが
// 検証しているMock Generatorの決定的な挙動(「子どもの持ち物チェックを
// 作って」で特定のチェックリストが返る)を保つには、コンパイル時の
// 既定値に頼らず、`appGenerationRepositoryProvider`を明示的に
// `MockAppGenerationRepository`へoverrideする必要がある(テストは
// 常に確定的であるべきという方針、実ネットワークには依存しない)。

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:forge_app/features/app_generation/data/datasources/mock_generation_datasource.dart';
import 'package:forge_app/features/app_generation/data/repositories/mock_app_generation_repository.dart';
import 'package:forge_app/features/app_generation/presentation/providers/app_generation_provider.dart';
import 'package:forge_app/features/app_generation/presentation/screens/home_screen.dart';
import 'package:forge_app/features/app_library/presentation/providers/app_library_provider.dart';
import 'package:forge_app/main.dart';
import 'package:shared_preferences/shared_preferences.dart';

void main() {
  testWidgets(
    'E2E: Home -> 直接入力 -> 送信 -> 生成中 -> 完成 -> アプリを開く -> チェックリスト表示・操作',
    (tester) async {
      // 0. マイアプリ・履歴の保存先(SharedPreferences)をテスト用の
      //    空ストアで初期化する(FORGE v0.2 P0/P5対応)。
      SharedPreferences.setMockInitialValues({});
      final prefs = await SharedPreferences.getInstance();

      // 1. 起動(Mock Generatorを明示的に使う。実ネットワークには依存しない)。
      await tester.pumpWidget(
        ProviderScope(
          overrides: [
            sharedPreferencesProvider.overrideWithValue(prefs),
            appGenerationRepositoryProvider.overrideWithValue(
              const MockAppGenerationRepository(MockGenerationDataSource()),
            ),
          ],
          child: const ForgeApp(),
        ),
      );
      await tester.pumpAndSettle();
      expect(find.byType(HomeScreen), findsOneWidget);

      // 2. 入力欄へ直接入力する(新UIには「子ども」Inspiration Cardが
      //    無いため、ユーザーの入力を模して直接enterTextする)。
      await tester.enterText(find.byType(TextField), '子どもの持ち物チェックを作って');
      await tester.pump();

      final homeField = tester.widget<TextField>(find.byType(TextField));
      expect(homeField.controller?.text, '子どもの持ち物チェックを作って');

      // 3. 送信ボタン(丸いアイコンボタン、入力があるためアクティブ)を
      //    タップ → GenerationFlowScreenへ(生成中状態にRotationTransition
      //    による無期限アニメーションがあるためpumpAndSettle禁止)。
      await tester.tap(find.byIcon(Icons.arrow_upward_rounded));
      await tester.pump(); // 画面遷移開始
      await tester.pump(const Duration(milliseconds: 300)); // 画面遷移アニメーション相当

      // この時点で生成中画面(「アプリを作成しています…」)のはず。
      expect(find.text('アプリを作成しています…'), findsOneWidget);

      // 4. Mock Modeの人工遅延(650ms)を明示的に進める
      await tester.pump(const Duration(milliseconds: 700));
      await tester.pump(); // FutureProviderの結果反映を1フレーム分進める

      // 5. 完成画面(「✨ アプリが完成しました！」)が表示されるはず。
      expect(find.text('✨ アプリが完成しました！'), findsOneWidget);

      // 6. 「アプリを開く」をタップ → Renderer(ForgeDocumentView)を表示。
      await tester.tap(find.widgetWithText(ElevatedButton, 'アプリを開く'));
      await tester.pumpAndSettle();

      // 7. Generated Screenのタイトルとチェックリスト項目を確認
      //    (Renderer自体は今回のUI変更で触れていないため、旧テストと同じ
      //    項目名で確認する)。
      expect(find.widgetWithText(AppBar, '子どもの持ち物チェック'), findsOneWidget);
      expect(find.text('着替え'), findsOneWidget);
      expect(find.text('オムツ'), findsOneWidget);
      expect(find.text('水筒'), findsOneWidget);
      expect(find.text('タオル'), findsOneWidget);
      expect(find.text('お気に入りのおもちゃ'), findsOneWidget);

      // 8. 最初の項目(item_1 = 着替え)をタップしてチェック状態を確認
      final firstItemTile = find.byKey(const ValueKey('checklist_item_item_1'));
      expect(firstItemTile, findsOneWidget);
      expect(
        find.descendant(of: firstItemTile, matching: find.byIcon(Icons.circle_outlined)),
        findsOneWidget,
        reason: 'タップ前は未チェック状態のアイコンのはず',
      );

      await tester.tap(
        find.descendant(of: firstItemTile, matching: find.byIcon(Icons.circle_outlined)),
      );
      await tester.pump();

      expect(
        find.descendant(of: firstItemTile, matching: find.byIcon(Icons.check_circle_rounded)),
        findsOneWidget,
        reason: 'タップ後はチェック済み状態のアイコンに変わるはず',
      );

      // 9. Flutter例外が一切発生していないこと
      expect(tester.takeException(), isNull);
    },
  );
}
