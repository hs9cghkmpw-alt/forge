// Widget Vocabulary Expansion(v1.6・v1.7、2026-08-11)のWidget Test。
//
// FORGE-AI-QUALITY-001。CEO「全て実装してくれ。確認もしなくて良い、
// ゴールは示している。つくってくれ。」の後、さらに「出し惜しみせず、
// 完璧を求めてくれ」という指示を受け、このセッションで初めて実際に
// Flutter SDKを取得して`flutter analyze`・`flutter test`を実行できる
// ようになった(従来は一度も実行できていなかった)。
//
// choice_field(v1.6)・bar_chart(v1.6)・date_field(v1.7)・
// tab_view(v1.7)は、いずれも実際に`flutter analyze`/`flutter test`で
// 検証したことが一度も無いまま実装されていた。実際に検証した結果、
// `widget_registry_core.dart`の`typeNameOf()`(sealed classの網羅的
// switch式)にこの4種のケースが1つも追加されておらず、**4種類とも
// 一度もRuntime上で描画できない状態だった**という重大な実バグを発見・
// 修正した(詳細はTECH_DEBT.md TD37参照)。このテストファイルは、
// その修正が正しいことも含めて検証する。

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:forge_app/core/theme/forge_theme.dart';
import 'package:forge_app/json_ui/renderer/forge_renderer.dart';

Widget _wrap(Map<String, dynamic> doc) {
  return MaterialApp(theme: ForgeTheme.theme, home: ForgeDocumentView(rawJson: doc));
}

/// `find.text('日付')`を直接tap()すると、`InputDecoration.labelText`の
/// フローティングラベル用に存在する(不可視の)複製Textをヒットテスト
/// してしまうことがあり、`tap()`が実害の無い警告を出す(実際の
/// タップ自体はInkWell経由で成立するが、テストの意図をより正確に
/// 表すため、実際にジェスチャーを検知する`InkWell`を明示的に狙う)。
Finder _dateFieldTapTarget() =>
    find.ancestor(of: find.text('日付'), matching: find.byType(InkWell)).first;

/// `ForgeLanguageCompiler`(v1.7)が実際に生成する household_budget 相当の
/// 文書を模した、tab_view + choice_field + date_field + bar_chart を
/// すべて含む文書。
Map<String, dynamic> _budgetDoc() {
  return {
    'version': '1.7',
    'initial_screen_id': 's1',
    'record_schemas': {
      'transaction': {
        'fields': [
          {'name': 'category', 'type': 'choice', 'label': 'カテゴリ', 'required': true, 'options': ['食費', '交通費', '娯楽']},
          {'name': 'amount', 'type': 'number', 'label': '金額', 'required': true},
          {'name': 'date', 'type': 'date', 'label': '日付', 'required': false},
        ],
      },
    },
    'screens': [
      {
        'id': 's1', 'title': '家計簿',
        'state': {
          'records': {'type': 'record_list', 'value': [], 'schema_ref': 'transaction'},
          'field_category': {'type': 'string', 'value': ''},
          'field_amount': {'type': 'string', 'value': ''},
          'field_date': {'type': 'string', 'value': ''},
        },
        'body': {
          'type': 'tab_view', 'id': 'root_tabs',
          'tab_titles': ['家計簿記録を追加', '家計簿記録一覧'],
          'children': [
            {
              'type': 'column', 'id': 'create_tab',
              'children': [
                {
                  'type': 'form', 'id': 'record_form', 'submit_label': '保存',
                  'submit_action': {
                    'type': 'composite',
                    'actions': [
                      {
                        'type': 'add_record', 'target_state_ref': 'records',
                        'field_bindings': {'category': 'field_category', 'amount': 'field_amount', 'date': 'field_date'},
                      },
                      {'type': 'reset_state', 'state_ref': 'field_category'},
                      {'type': 'reset_state', 'state_ref': 'field_amount'},
                      {'type': 'reset_state', 'state_ref': 'field_date'},
                    ],
                  },
                  'children': [
                    {'type': 'choice_field', 'id': 'cf1', 'label': 'カテゴリ', 'state_ref': 'field_category', 'options': ['食費', '交通費', '娯楽']},
                    {'type': 'text_field', 'id': 'tf1', 'state_ref': 'field_amount', 'placeholder': '金額'},
                    {'type': 'date_field', 'id': 'df1', 'label': '日付', 'state_ref': 'field_date'},
                  ],
                },
              ],
            },
            {
              'type': 'column', 'id': 'list_tab',
              'children': [
                {
                  'type': 'record_list_view', 'id': 'rlv1', 'state_ref': 'records',
                  'display_fields': ['category', 'amount', 'date'], 'empty_state_text': 'まだ記録がありません',
                },
                {'type': 'bar_chart', 'id': 'bc1', 'state_ref': 'records', 'value_field': 'amount', 'label_field': 'category', 'title': '支出内訳'},
              ],
            },
          ],
        },
      },
    ],
  };
}

void main() {
  group('choice_field', () {
    testWidgets('ドロップダウンとしてlabelが表示される(未選択時もクラッシュしない)', (tester) async {
      await tester.pumpWidget(_wrap(_budgetDoc()));
      await tester.pumpAndSettle();

      expect(find.byType(DropdownButtonFormField<String>), findsOneWidget);
      expect(find.text('カテゴリ'), findsOneWidget);
      expect(tester.takeException(), isNull);
    });

    testWidgets('選択肢をタップすると選択状態になり、送信するとRecordへ反映される', (tester) async {
      await tester.pumpWidget(_wrap(_budgetDoc()));
      await tester.pumpAndSettle();

      // ドロップダウンを開いて「食費」を選ぶ。
      await tester.tap(find.byType(DropdownButtonFormField<String>));
      await tester.pumpAndSettle();
      // メニュー内の「食費」(フォーム内に既に見えているものとは別インスタンス)をタップ。
      await tester.tap(find.text('食費').last);
      await tester.pumpAndSettle();

      await tester.enterText(find.byType(TextField), '3200');
      await tester.tap(find.widgetWithText(ElevatedButton, '保存'));
      await tester.pumpAndSettle();

      // 一覧タブへ切り替えて、Recordに反映されていることを確認する。
      await tester.tap(find.text('家計簿記録一覧'));
      await tester.pumpAndSettle();

      expect(find.textContaining('食費'), findsWidgets);
      expect(find.textContaining('3200'), findsWidgets);
      expect(tester.takeException(), isNull);
    });
  });

  group('date_field', () {
    testWidgets('labelが表示され、タップするとshowDatePicker()のカレンダーが開く', (tester) async {
      await tester.pumpWidget(_wrap(_budgetDoc()));
      await tester.pumpAndSettle();

      expect(find.text('日付'), findsOneWidget);
      await tester.tap(_dateFieldTapTarget());
      await tester.pumpAndSettle();

      // Material標準のDatePickerDialogが開いていることを確認する
      // (OKボタンはMaterialLocalizations既定で'OK'表記)。
      expect(find.byType(DatePickerDialog), findsOneWidget);
      expect(tester.takeException(), isNull);

      // ダイアログを閉じる(何も選ばずキャンセル)。
      await tester.tap(find.text('Cancel'));
      await tester.pumpAndSettle();
      expect(find.byType(DatePickerDialog), findsNothing);
    });

    testWidgets('日付を選ぶとISO 8601形式(YYYY-MM-DD)でstateへ反映される', (tester) async {
      await tester.pumpWidget(_wrap(_budgetDoc()));
      await tester.pumpAndSettle();

      await tester.tap(_dateFieldTapTarget());
      await tester.pumpAndSettle();

      // カレンダーグリッド内の「15日」をタップして選択する(その月の
      // 15日は、初期表示される月ならほぼ確実に表示されているはず)。
      await tester.tap(find.text('15').first);
      await tester.pumpAndSettle();
      await tester.tap(find.text('OK'));
      await tester.pumpAndSettle();

      // 選択した日付がYYYY-MM-DD形式でテキストとして表示されていること
      // (厳密な日付値ではなく、形式が壊れていないことを確認する
      // ——実際の「15日」が属する月はテスト実行時のカレンダーの
      // 初期状態に依存するため)。
      final dateTexts = find
          .byWidgetPredicate((w) => w is Text && RegExp(r'^\d{4}-\d{2}-15$').hasMatch(w.data ?? ''))
          .evaluate();
      expect(dateTexts, isNotEmpty, reason: 'YYYY-MM-15形式の日付テキストが見つかること');
      expect(tester.takeException(), isNull);
    });
  });

  group('tab_view', () {
    testWidgets('タブタイトルが表示され、既定では最初のタブの中身だけが描画される', (tester) async {
      await tester.pumpWidget(_wrap(_budgetDoc()));
      await tester.pumpAndSettle();

      expect(find.text('家計簿記録を追加'), findsOneWidget);
      expect(find.text('家計簿記録一覧'), findsOneWidget);
      // 最初のタブ(追加)の中身は見えているはず。
      expect(find.byType(DropdownButtonFormField<String>), findsOneWidget);
      // 2番目のタブ(一覧)の中身はまだ描画されていないはず
      // (TabBarViewのような「全タブ保持」ではなく、選択中のタブだけを
      // 描画する設計のため)。
      expect(find.text('まだ記録がありません'), findsNothing);
      expect(tester.takeException(), isNull);
    });

    testWidgets('タブをタップすると中身が切り替わる', (tester) async {
      await tester.pumpWidget(_wrap(_budgetDoc()));
      await tester.pumpAndSettle();

      await tester.tap(find.text('家計簿記録一覧'));
      await tester.pumpAndSettle();

      expect(find.text('まだ記録がありません'), findsOneWidget, reason: '一覧タブへ切り替わったこと');
      expect(find.byType(DropdownButtonFormField<String>), findsNothing, reason: '追加タブの中身はもう描画されていないこと');
      expect(tester.takeException(), isNull);
    });
  });

  group('bar_chart', () {
    testWidgets('titleが表示され、Recordが無い間はクラッシュしない', (tester) async {
      await tester.pumpWidget(_wrap(_budgetDoc()));
      await tester.pumpAndSettle();

      await tester.tap(find.text('家計簿記録一覧'));
      await tester.pumpAndSettle();

      // Recordが0件の間、bar_chartは何も描画しない(SizedBox.shrink)
      // 設計のため、タイトルは出ない。
      expect(find.text('支出内訳'), findsNothing);
      expect(tester.takeException(), isNull);
    });

    testWidgets('Recordを追加すると、bar_chartのtitleとバーが表示される', (tester) async {
      await tester.pumpWidget(_wrap(_budgetDoc()));
      await tester.pumpAndSettle();

      await tester.tap(find.byType(DropdownButtonFormField<String>));
      await tester.pumpAndSettle();
      await tester.tap(find.text('娯楽').last);
      await tester.pumpAndSettle();
      await tester.enterText(find.byType(TextField), '4500');
      await tester.tap(find.widgetWithText(ElevatedButton, '保存'));
      await tester.pumpAndSettle();

      await tester.tap(find.text('家計簿記録一覧'));
      await tester.pumpAndSettle();

      expect(find.text('支出内訳'), findsOneWidget);
      // 棒グラフのラベル(カテゴリ名)・値(金額)がそれぞれ表示されること。
      expect(find.textContaining('娯楽'), findsWidgets);
      expect(find.textContaining('4500'), findsWidgets);
      expect(tester.takeException(), isNull);
    });
  });

  group('Integration: household_budgetの一連の流れ', () {
    testWidgets(
      '追加タブでカテゴリ・金額・日付を入力 -> 保存 -> 一覧タブでRecordとbar_chartを確認',
      (tester) async {
        await tester.pumpWidget(_wrap(_budgetDoc()));
        await tester.pumpAndSettle();

        await tester.tap(find.byType(DropdownButtonFormField<String>));
        await tester.pumpAndSettle();
        await tester.tap(find.text('交通費').last);
        await tester.pumpAndSettle();

        await tester.enterText(find.byType(TextField), '580');

        await tester.tap(_dateFieldTapTarget());
        await tester.pumpAndSettle();
        await tester.tap(find.text('20').first);
        await tester.pumpAndSettle();
        await tester.tap(find.text('OK'));
        await tester.pumpAndSettle();

        await tester.tap(find.widgetWithText(ElevatedButton, '保存'));
        await tester.pumpAndSettle();

        await tester.tap(find.text('家計簿記録一覧'));
        await tester.pumpAndSettle();

        expect(find.text('まだ記録がありません'), findsNothing);
        expect(find.textContaining('交通費'), findsWidgets);
        expect(find.textContaining('580'), findsWidgets);
        expect(find.text('支出内訳'), findsOneWidget);
        expect(tester.takeException(), isNull);
      },
    );
  });
}
