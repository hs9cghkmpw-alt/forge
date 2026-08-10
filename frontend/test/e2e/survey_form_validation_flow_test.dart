// E2E: Survey(Form + Validation)フルフロー(FORGE-MILESTONE-003)。
//
// 指示書5章E2Eの8ステップを、実際のMock Generator(Survey/Formテンプレート)を
// 使って検証する: Homeから開く→Text Field入力→Checkbox操作→Submit→
// Validationが通る→次画面へ遷移→処理結果が保持されている→戻る操作後も状態維持。
//
// FORGE-MILESTONE-002の`kids_checklist_generation_flow_test.dart`が
// Checklist系フローを検証しているのに対し、本ファイルはMILESTONE-003で新設した
// Form Validation経路(submit_form Action)を実際に通す。
//
// 2026-07-17: CEO提示のUIモックアップに合わせてHomeScreen・生成フローの
// 画面構成が変わったことに伴い、更新した(`kids_checklist_generation_
// flow_test.dart`と同じ変更: Confirm画面を経由せず、HomeScreenから直接
// GenerationFlowScreen(生成中→完成画面→「アプリを開く」)へ進む)。
//
// 注記: Claudeのサンドボックスに Dart SDK が無いため、このファイルは
// 一度も `flutter test` で実行されていない。CEO環境での実行が必須
// (タイミング関連のテストは特に、実行してみないと確信が持てない)。
//
// 2026-07-17(FORGE v0.2 P0/P5): 完成画面の「アプリを開く」が実際に
// `SharedPreferences`へ保存するようになったため、モックストアの初期化と
// `sharedPreferencesProvider`のoverrideが必要になった。
//
// 2026-07-17(FORGE v0.2 Backend接続): `AppConfig.mockMode`の既定値が
// `false`(実Backend接続が既定)へ変わったため、`appGenerationRepository
// Provider`を明示的に`MockAppGenerationRepository`へoverrideし、この
// テストが検証しているMock Generatorの決定的な挙動(Survey/Form
// テンプレート)を、コンパイル時の既定値に頼らず保つ。

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
    'E2E: Home -> アンケート入力 -> 送信 -> 生成中 -> 完成 -> アプリを開く -> Form回答 -> Submit(Validation)-> 送信完了 -> 戻る',
    (tester) async {
      // 1. 起動(Mock Generatorを明示的に使う。実ネットワークには依存しない)。
      SharedPreferences.setMockInitialValues({});
      final prefs = await SharedPreferences.getInstance();
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

      // 2. Text Fieldへ「アンケート」を含む文言を手入力する
      //    (ExamplePickerSheetの5例には「アンケート」カテゴリが無いため、
      //    手入力で検証する)。
      await tester.enterText(find.byType(TextField), 'アンケートを作って');
      await tester.pump();

      // 3. 送信ボタン(丸いアイコンボタン)をタップ → GenerationFlowScreenへ
      //    (生成中状態にRotationTransitionによる無期限アニメーションが
      //    あるためpumpAndSettle禁止)。
      await tester.tap(find.byIcon(Icons.arrow_upward_rounded));
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 300));
      expect(find.text('アプリを作成しています…'), findsOneWidget);

      await tester.pump(const Duration(milliseconds: 700)); // Mock Modeの人工遅延(650ms)を進める
      await tester.pump();

      // 4. 完成画面 → 「アプリを開く」をタップしてRendererを表示。
      expect(find.text('✨ アプリが完成しました！'), findsOneWidget);
      await tester.tap(find.widgetWithText(ElevatedButton, 'アプリを開く'));
      await tester.pumpAndSettle();

      expect(find.widgetWithText(AppBar, '満足度アンケート'), findsOneWidget);

      // 5. Checkbox 2件を操作する(State Bindingの確認)。
      final satisfiedTile = find.widgetWithText(CheckboxListTile, '今回のサービスに満足しましたか');
      final recommendTile = find.widgetWithText(CheckboxListTile, '友人に勧めたいと思いますか');
      expect(satisfiedTile, findsOneWidget);
      expect(recommendTile, findsOneWidget);
      await tester.tap(satisfiedTile);
      await tester.tap(recommendTile);
      await tester.pump();

      // 6. Text Field(コメント欄、任意)へ200文字以内のコメントを入力する
      //    (Validation: max_lengthルールに合格する入力)。
      await tester.enterText(find.byType(TextField), 'とても良かったです');
      await tester.pump();

      // 7. 「送信する」をタップ → submit_form Actionが発火し、Validation通過後
      //    success_action(navigate)が実行されるはず。
      await tester.tap(find.widgetWithText(ElevatedButton, '送信する'));
      await tester.pumpAndSettle();

      // 8. 送信完了画面へ遷移し、メッセージが表示されていることを確認する
      //    (処理結果が反映されている ≒ 検証通過後のsuccess_actionが実行された証拠)。
      expect(find.widgetWithText(AppBar, '送信完了'), findsOneWidget);
      expect(find.text('ご協力ありがとうございました。'), findsOneWidget);
      expect(tester.takeException(), isNull);

      // 9. 戻る操作後も(元のフォーム画面の)状態が維持されていることを確認する。
      await tester.tap(find.widgetWithText(ElevatedButton, '戻る'));
      await tester.pumpAndSettle();

      expect(find.widgetWithText(AppBar, '満足度アンケート'), findsOneWidget);
      final satisfiedCheckbox = tester.widget<Checkbox>(
        find.descendant(of: satisfiedTile, matching: find.byType(Checkbox)),
      );
      expect(satisfiedCheckbox.value, isTrue, reason: '戻った後もチェック状態が保持されているはず');
      expect(tester.takeException(), isNull);
    },
  );
}

