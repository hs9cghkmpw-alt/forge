// Product Quality Sprint1 Widget Test + Integration Test(FORGE v1.0、
// Sprint1 Patch1でFinderを堅牢化)。
//
// section_header・grid layout・design_tokensが実際にForgeDocumentView
// 経由で描画できることを確認する。指示書の目標「1画面でも、単純な
// Widget縦並びではなく、視覚的階層とドメインらしい情報設計を持つ
// アプリを生成できること」を直接検証する。
//
// **Sprint1 Patch1での修正**:
// 1. `_todoDoc()`の作成フォームが`add_record`単体のままで、実際の
//    Compiler(`composite([add_record, reset_state])`)と乖離していた。
//    このため送信後も作成欄に入力値が残り続け、`find.textContaining`が
//    「作成欄のEditableText」と「一覧のCardのText」の両方へヒットして
//    `findsOneWidget`が2件検出で失敗していた。作成フォームを実際の
//    Compiler出力と同じ形(reset_state付き)へ修正した。
// 2. Card内のテキストだけを対象にした`_findInCards()`ヘルパーを導入し、
//    入力欄を誤って拾わない、より頑健なFinderへ置き換えた。
//
// 注記: Claudeのサンドボックスに Dart SDK が無いため、このファイルは
// 一度も `flutter test` で実行されていない。CEO環境での実行が必須。

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:forge_app/core/theme/forge_theme.dart';
import 'package:forge_app/json_ui/renderer/forge_renderer.dart';

Widget _wrap(Map<String, dynamic> doc) {
  return MaterialApp(theme: ForgeTheme.theme, home: ForgeDocumentView(rawJson: doc));
}

/// Card(一覧のRecord表示)の中に表示されているテキストだけを対象にした
/// finder。入力欄(TextField/EditableText)を誤って拾わないようにする
/// (Sprint1 Patch1で導入、指示書「Card/List表示対象をWidget階層・
/// descendant finderで限定する」への対応)。
Finder _findInCards(String text) => find.descendant(
      of: find.byType(Card),
      matching: find.textContaining(text),
    );

/// `ForgeLanguageCompiler`が実際に生成する、Sprint1後のTODO文書
/// (grid layout、3つのsection_header、design_tokens付き)を模した
/// 文書。
Map<String, dynamic> _todoDoc() {
  return {
    'version': '1.5',
    'initial_screen_id': 's1',
    'design_tokens': {
      'color_scheme': {'primary': '#6366F1', 'secondary': '#EC4899', 'success': '#10B981', 'error': '#EF4444'},
      'corner_radius': {'small': 12, 'medium': 18, 'large': 28},
      'spacing_scale': {'xs': 4, 'sm': 8, 'md': 16, 'lg': 24, 'xl': 32},
    },
    'screens': [
      {
        'id': 's1', 'title': 'TODO',
        'state': {
          'records': {'type': 'record_list', 'value': <dynamic>[]},
          'field_title': {'type': 'string', 'value': ''},
        },
        'body': {
          'type': 'column', 'id': 'root',
          'children': [
            {'type': 'section_header', 'id': 'sec_create', 'title': 'TODOを追加', 'subtitle': '必要な情報を入力してください'},
            {
              'type': 'form', 'id': 'record_form', 'submit_label': '保存',
              'submit_action': {
                // Sprint1 Patch1で修正: 実際のCompilerと同じ
                // composite([add_record, reset_state])の形にする。
                'type': 'composite',
                'actions': [
                  {
                    'type': 'add_record', 'target_state_ref': 'records',
                    'field_bindings': {'title': 'field_title'},
                  },
                  {'type': 'reset_state', 'state_ref': 'field_title'},
                ],
              },
              'children': [
                {'type': 'text_field', 'id': 't1', 'state_ref': 'field_title', 'placeholder': 'やること'},
              ],
            },
            {'type': 'divider', 'id': 'd1'},
            {'type': 'section_header', 'id': 'sec_list', 'title': 'TODO一覧'},
            {
              'type': 'record_list_view', 'id': 'rlv1', 'state_ref': 'records',
              'layout': 'grid', 'display_fields': ['title'],
              'empty_state_text': 'まだTODOがありません',
            },
          ],
        },
      },
    ],
  };
}

Future<void> _addTodo(WidgetTester tester, String title) async {
  await tester.enterText(find.byType(TextField), title);
  await tester.tap(find.widgetWithText(ElevatedButton, '保存'));
  await tester.pumpAndSettle();
}

void main() {
  group('section_header表示', () {
    testWidgets('section_headerのtitle/subtitleが表示される', (tester) async {
      await tester.pumpWidget(_wrap(_todoDoc()));
      await tester.pumpAndSettle();

      expect(find.text('TODOを追加'), findsOneWidget);
      expect(find.text('必要な情報を入力してください'), findsOneWidget);
      expect(find.text('TODO一覧'), findsOneWidget);
      expect(tester.takeException(), isNull);
    });
  });

  group('grid layout表示', () {
    testWidgets('layout: "grid"の場合、GridViewで描画される', (tester) async {
      await tester.pumpWidget(_wrap(_todoDoc()));
      await tester.pumpAndSettle();

      // 追加前は空状態のテキストが出る。
      expect(find.text('まだTODOがありません'), findsOneWidget);

      await _addTodo(tester, '牛乳を買う');

      expect(find.text('まだTODOがありません'), findsNothing);
      expect(find.byType(GridView), findsOneWidget);
      // Card内のテキストだけを見る(作成欄はreset_stateにより既に
      // 空へ戻っているはずだが、それに依存せず二重に安全策を取る)。
      expect(_findInCards('牛乳を買う'), findsOneWidget);
      // 作成欄(TextField)がsubmit後に空へ戻っていることも直接確認する。
      final inputField = tester.widget<TextField>(find.byType(TextField));
      expect(inputField.controller?.text, '', reason: 'submit後、作成欄はreset_stateで空へ戻る');
      expect(tester.takeException(), isNull);
    });

    testWidgets('複数件追加してもGridViewがクラッシュしない', (tester) async {
      await tester.pumpWidget(_wrap(_todoDoc()));
      await tester.pumpAndSettle();

      for (final title in ['牛乳を買う', '掃除をする', '本を返す']) {
        await _addTodo(tester, title);
      }

      expect(find.byType(Card), findsNWidgets(3));
      for (final title in ['牛乳を買う', '掃除をする', '本を返す']) {
        expect(_findInCards(title), findsOneWidget, reason: '$title がCardとして表示されていること');
      }
      expect(tester.takeException(), isNull);
    });
  });

  group('design_tokensがネイティブテーマへ影響しないことの確認', () {
    testWidgets('design_tokens付きのForgeDocumentViewを描画しても、'
        '外側のMaterialApp自体のThemeDataは変更されない(ローカルTheme上書きの確認)', (tester) async {
      await tester.pumpWidget(_wrap(_todoDoc()));
      await tester.pumpAndSettle();

      final materialApp = tester.widget<MaterialApp>(find.byType(MaterialApp));
      // ForgeTheme.themeそのもの(ネイティブの既定テーマ)が変更されずに
      // 外側へ渡され続けていることを確認する(design_tokensによる
      // 上書きは、ForgeDocumentView内部のTheme Widgetというサブツリー
      // に閉じており、MaterialApp自体のthemeプロパティを書き換えては
      // いない)。
      expect(materialApp.theme, ForgeTheme.theme);
    });
  });

  group('Integration: 視覚的階層を持つ単一画面', () {
    testWidgets(
      '起動 -> section_headerでセクション分割 -> 追加 -> grid表示 -> design_tokensの色が適用される、まで一連で確認する',
      (tester) async {
        await tester.pumpWidget(_wrap(_todoDoc()));
        await tester.pumpAndSettle();

        // 1. 視覚的階層(3セクション)の確認。
        expect(find.text('TODOを追加'), findsOneWidget);
        expect(find.text('TODO一覧'), findsOneWidget);

        // 2. 追加。
        await _addTodo(tester, '牛乳を買う');

        // 3. Grid表示の確認(Card内のテキストのみを対象にする)。
        expect(find.byType(GridView), findsOneWidget);
        expect(_findInCards('牛乳を買う'), findsOneWidget);

        // 4. design_tokensのボタン色が適用されていることの確認。
        //
        // **調査の記録(この行は以前`button.style?.backgroundColor`を
        // 直接検査しており、常にnullで失敗していた)**: `_buildButton`
        // /`buildForm`が生成する`ElevatedButton`は、いずれも`style:`を
        // 明示的に指定していない(`ElevatedButton(onPressed: ...,
        // child: ...)`のみ、`widget_registry.dart`・
        // `widget_registry_v1_1.dart`で確認済み)。これは意図的な設計
        // (色をWidget単位ではなく、`ForgeDocumentView`が`Theme`で
        // 一括して与える、指示書「Theme.of(context)ではなく固定色を
        // 使用していないか」の確認観点に合致する実装)であり、
        // `ElevatedButton`インスタンス自身の`style`フィールドは常に
        // `null`のままになる。色は`Theme.of(context).
        // elevatedButtonTheme`経由でのみ供給される。よって、正しい
        // 検証方法は「Widgetインスタンス自身のstyle」ではなく
        // 「そのWidgetの位置から見えるTheme」を調べることである。
        final buttonFinder = find.widgetWithText(ElevatedButton, '保存');
        final buttonContext = tester.element(buttonFinder);
        final elevatedButtonStyle = Theme.of(buttonContext).elevatedButtonTheme.style;
        final backgroundColor = elevatedButtonStyle?.backgroundColor?.resolve(<WidgetState>{});
        expect(backgroundColor, const Color(0xFF6366F1), reason: 'design_tokens.color_scheme.primaryがelevatedButtonThemeへ反映されていること');

        // 5. design_tokensがボタン以外にもRuntime全体へ反映されている
        // ことを確認する(指示書「このテストだけを修正するのではなく、
        // 実際にdesign_tokensがRuntime全体へ反映されることを確認して
        // ください」への対応)。
        //
        // 5a. ColorScheme.primary自体が上書きされていること
        // (`elevatedButtonTheme`という個別のThemeだけに閉じた変更では
        // ないことを裏付ける)。
        expect(Theme.of(buttonContext).colorScheme.primary, const Color(0xFF6366F1));

        // 5b. section_headerの強調バー(Container)がdesign_tokensの
        // primary色を反映していること。Sprint1 Patch2で
        // `buildSectionHeader`を単純化し、`_RecordCard`と同じく
        // `Theme.of(context).colorScheme.primary`だけを見る設計へ
        // 揃えた(以前は`state.designTokens`という別経路も持っていた)。
        final accentBarFinder = find.byWidgetPredicate(
          (w) => w is Container && w.decoration is BoxDecoration && (w.decoration as BoxDecoration).color != null,
        );
        expect(accentBarFinder, findsWidgets, reason: 'section_headerの強調バーが見つかること');
        final accentColors = accentBarFinder
            .evaluate()
            .map((e) => ((e.widget as Container).decoration as BoxDecoration).color)
            .toSet();
        expect(accentColors, contains(const Color(0xFF6366F1)), reason: 'section_headerの強調バーがprimary色を使っていること');

        expect(tester.takeException(), isNull);
      },
    );

    testWidgets('design_tokensのcorner_radiusがElevatedButton/TextFieldへ反映される', (tester) async {
      await tester.pumpWidget(_wrap(_todoDoc()));
      await tester.pumpAndSettle();

      final buttonContext = tester.element(find.widgetWithText(ElevatedButton, '保存'));
      final theme = Theme.of(buttonContext);
      final buttonShape = theme.elevatedButtonTheme.style?.shape?.resolve(<WidgetState>{});
      expect(buttonShape, isA<RoundedRectangleBorder>());
      expect(
        (buttonShape as RoundedRectangleBorder).borderRadius,
        BorderRadius.circular(18), // design_tokens.corner_radius.medium
      );
    });

    testWidgets(
      'primaryContainer等の派生ロールがdesign_tokensのprimaryから再計算される'
      '(Sprint1 Patch2で修正した実バグの回帰: 以前はcopyWithで.primaryだけを'
      '上書きしており、primaryContainerがネイティブ既定値のままだった)',
      (tester) async {
        await tester.pumpWidget(_wrap(_todoDoc()));
        await tester.pumpAndSettle();

        final buttonContext = tester.element(find.widgetWithText(ElevatedButton, '保存'));
        final tokenScheme = Theme.of(buttonContext).colorScheme;

        // .primaryはdesign_tokensの値そのもの(調和目的の派生色とは区別する)。
        expect(tokenScheme.primary, const Color(0xFF6366F1));
        // primaryContainerはネイティブ既定テーマの値とは異なる値へ
        // 再計算されていること(seedColorから改めて導出された証拠)。
        expect(tokenScheme.primaryContainer, isNot(ForgeTheme.theme.colorScheme.primaryContainer));
      },
    );
  });
}
