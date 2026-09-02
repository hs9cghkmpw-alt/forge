// ホーム画面に **Provider の身元が出ていない**こと（Constitution §4・§9）。
//
// ---
//
// ## この試験が落ちる条件
//
// 変更前の `home_screen.dart` には `_ProviderToggle` があり、画面に
// `Gemini` または `Mock` という文字と、
// 「Gemini APIを使用中(タップでMockへ切り替え)」という Tooltip を出して
// いた。**このファイルは変更前のコードでは落ちる。**
//
// ## 文字を消しただけでは通らない
//
// もう1つ検査するのは「利用者が AI 経路を選ぶ操作が無い」ことである。
// 表示名を `AIモード` に変えても、タップで Provider が切り替わるなら
// 方針違反は残る（§4「利用者に Provider 選択を担当させない」）。

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:forge_app/features/app_generation/presentation/providers/app_generation_provider.dart';
import 'package:forge_app/features/app_generation/presentation/screens/home_screen.dart';
import 'package:forge_app/features/app_generation/presentation/widgets/developer_provider_override.dart';
import 'package:forge_app/features/app_library/presentation/providers/app_library_provider.dart';
import 'package:forge_app/shared_widgets/ai_mode.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../../../../shared_widgets/ai_mode_test.dart' show mentionsProviderIdentity;

void main() {
  Future<Widget> wrap(Widget child) async {
    SharedPreferences.setMockInitialValues({});
    final prefs = await SharedPreferences.getInstance();
    return ProviderScope(
      overrides: [sharedPreferencesProvider.overrideWithValue(prefs)],
      child: MaterialApp(home: child),
    );
  }

  /// 画面に描かれている全ての文字を集める。
  ///
  /// **「Gemini という Text を探す」ではなく「全ての文字を見る」。**
  /// 前者は、別の書き方で身元が戻ってきたときに気づけない。
  List<String> visibleTexts(WidgetTester tester) => tester
      .widgetList<Text>(find.byType(Text))
      .map((t) => t.data ?? t.textSpan?.toPlainText() ?? '')
      .where((s) => s.isNotEmpty)
      .toList();

  List<String> tooltipMessages(WidgetTester tester) => tester
      .widgetList<Tooltip>(find.byType(Tooltip))
      .map((t) => t.message ?? '')
      .where((s) => s.isNotEmpty)
      .toList();

  testWidgets('通常画面のどの文字にも Provider の身元が出ない', (tester) async {
    await tester.pumpWidget(await wrap(const HomeScreen()));
    await tester.pump();

    for (final text in visibleTexts(tester)) {
      expect(
        mentionsProviderIdentity(text),
        isFalse,
        reason: '通常画面に Provider の身元が出ている: "$text"',
      );
    }
  });

  testWidgets('Tooltip にも Provider の身元が出ない（隠れた文言も UI である）', (tester) async {
    await tester.pumpWidget(await wrap(const HomeScreen()));
    await tester.pump();

    for (final message in tooltipMessages(tester)) {
      expect(
        mentionsProviderIdentity(message),
        isFalse,
        reason: 'Tooltip に Provider の身元が出ている: "$message"',
      );
    }
  });

  testWidgets('読み上げ（Semantics）にも Provider の身元が出ない', (tester) async {
    final handle = tester.ensureSemantics();
    await tester.pumpWidget(await wrap(const HomeScreen()));
    await tester.pump();

    for (final semantics in tester.widgetList<Semantics>(find.byType(Semantics))) {
      final spoken = '${semantics.properties.label ?? ''} '
          '${semantics.properties.hint ?? ''} '
          '${semantics.properties.tooltip ?? ''}';
      expect(
        mentionsProviderIdentity(spoken),
        isFalse,
        reason: '読み上げに Provider の身元が出ている: "$spoken"',
      );
    }
    handle.dispose();
  });

  testWidgets('「AIモード」の状態表示が出ている', (tester) async {
    await tester.pumpWidget(await wrap(const HomeScreen()));
    await tester.pump();

    expect(find.byType(AiModeIndicator), findsOneWidget);
    expect(find.text(kAiModeName), findsOneWidget);
  });

  testWidgets('利用者が AI 経路を選ぶ操作が無い（既定ビルド）', (tester) async {
    await tester.pumpWidget(await wrap(const HomeScreen()));
    await tester.pump();

    // 開発者向け UI は既定ビルドでは何も描かない。
    expect(find.byType(DropdownButton<String?>), findsNothing);
    expect(
      find.descendant(
        of: find.byType(DeveloperProviderOverride),
        matching: find.byType(Widget),
      ),
      findsNothing,
    );

    // 状態表示自体が押せない。
    expect(
      find.descendant(of: find.byType(AiModeIndicator), matching: find.byType(InkWell)),
      findsNothing,
    );
  });

  testWidgets('起動直後の Provider 選択は空である（Forge が内部で決める）', (tester) async {
    late WidgetRef captured;
    await tester.pumpWidget(await wrap(
      Consumer(builder: (context, ref, _) {
        captured = ref;
        return const HomeScreen();
      }),
    ));
    await tester.pump();

    expect(
      captured.read(selectedAiProviderProvider),
      isNull,
      reason: 'Frontend が Provider を指定すると Backend の Router を迂回する。'
          ' 通常ビルドでは Forge 自身が経路を決めるべきである。',
    );
  });
}
