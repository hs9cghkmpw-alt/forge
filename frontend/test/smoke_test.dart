// Smoke Test(FORGE-MERGE-003 Task 2)。
//
// 目的はただ1つ: アプリ全体(main.dartのForgeApp)が例外を投げずに起動し、
// 最初の画面(HomeScreen)へ到達することを確認する。ロジックの正しさではなく
// 「そもそも落ちずに立ち上がるか」だけを見る、最も基礎的なテスト。
//
// 注記: Claudeのサンドボックスに Dart SDK が無いため、このファイルは
// 一度も `flutter test` で実行されていない。CEO環境での実行が必須。
// (FORGE-MERGE-003-report.md Test Report参照)
//
// 2026-07-17(FORGE v0.2 P5): HomeScreenが「最近のアプリ」表示のため
// `savedAppsProvider`(→`sharedPreferencesProvider`)を参照するように
// なったため、`SharedPreferences.setMockInitialValues`とoverrideが必要。

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:forge_app/features/app_generation/presentation/screens/home_screen.dart';
import 'package:forge_app/features/app_library/presentation/providers/app_library_provider.dart';
import 'package:forge_app/main.dart';
import 'package:shared_preferences/shared_preferences.dart';

void main() {
  testWidgets('Smoke: ForgeApp boots to HomeScreen without throwing', (WidgetTester tester) async {
    SharedPreferences.setMockInitialValues({});
    final prefs = await SharedPreferences.getInstance();
    await tester.pumpWidget(
      ProviderScope(
        overrides: [sharedPreferencesProvider.overrideWithValue(prefs)],
        child: const ForgeApp(),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.byType(HomeScreen), findsOneWidget);
    expect(tester.takeException(), isNull);
  });
}
