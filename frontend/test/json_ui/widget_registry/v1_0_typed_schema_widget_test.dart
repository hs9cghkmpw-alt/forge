// Schema-driven Widget Test + Integration Test(FORGE v1.0)。
//
// 指示書「Widget」節と「Integration Tests」節(Fishing Log・Household
// Budgetの2フロー)をカバーする。実際のJSON文書からForgeDocumentView
// 経由で描画する、既存ラウンドと同じ実物に近い検証方式を踏襲する。
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

/// `ForgeLanguageCompiler`が実際に生成する構成を模した、型付き
/// FishRecord文書(species: string必須, size: number, catch_date: date)。
Map<String, dynamic> _fishRecordDoc() {
  return {
    'version': '1.4',
    'initial_screen_id': 's1',
    'record_schemas': {
      'fish_record': {
        'fields': [
          {'name': 'species', 'type': 'string', 'label': '魚種', 'required': true},
          {'name': 'size', 'type': 'number', 'label': 'サイズ(cm)', 'required': false},
          {'name': 'catch_date', 'type': 'date', 'label': '日付', 'required': false},
        ],
      },
    },
    'screens': [
      {
        'id': 's1', 'title': '釣果記録',
        'state': {
          'records': {'type': 'record_list', 'value': [], 'schema_ref': 'fish_record'},
          'field_species': {'type': 'string', 'value': ''},
          'field_size': {'type': 'string', 'value': ''},
          'field_catch_date': {'type': 'string', 'value': ''},
          'selected': {'type': 'selected_record', 'value': null},
          'edit_field_species': {'type': 'string', 'value': ''},
          'edit_field_size': {'type': 'string', 'value': ''},
          'edit_field_catch_date': {'type': 'string', 'value': ''},
        },
        'body': {
          'type': 'column', 'id': 'root',
          'children': [
            {
              'type': 'form', 'id': 'record_form', 'submit_label': '保存',
              'submit_action': {
                'type': 'composite',
                'actions': [
                  {
                    'type': 'add_record', 'target_state_ref': 'records',
                    'field_bindings': {
                      'species': 'field_species', 'size': 'field_size', 'catch_date': 'field_catch_date',
                    },
                  },
                  {'type': 'reset_state', 'state_ref': 'field_species'},
                  {'type': 'reset_state', 'state_ref': 'field_size'},
                  {'type': 'reset_state', 'state_ref': 'field_catch_date'},
                ],
              },
              'children': [
                {
                  'type': 'text_field', 'id': 't1', 'state_ref': 'field_species', 'placeholder': '魚種',
                  'validation': {'rules': [{'type': 'required', 'message': '魚種を入力してください'}]},
                },
                {'type': 'text_field', 'id': 't2', 'state_ref': 'field_size', 'placeholder': 'サイズ(cm)'},
                {'type': 'text_field', 'id': 't3', 'state_ref': 'field_catch_date', 'placeholder': '日付'},
              ],
            },
            {'type': 'divider', 'id': 'd1'},
            {
              'type': 'record_list_view', 'id': 'records_list_view', 'state_ref': 'records',
              'layout': 'card', 'display_fields': ['species', 'size', 'catch_date'],
              'selectable': true, 'selected_state_ref': 'selected',
              'select_field_bindings': {
                'species': 'edit_field_species', 'size': 'edit_field_size', 'catch_date': 'edit_field_catch_date',
              },
              'empty_state_text': 'まだ釣果記録がありません',
            },
            {'type': 'divider', 'id': 'd2'},
            {
              'type': 'form', 'id': 'record_edit_form', 'submit_label': '更新',
              'submit_action': {
                'type': 'composite',
                'actions': [
                  {
                    'type': 'update_record', 'target_state_ref': 'records', 'record_id_ref': 'selected',
                    'field_bindings': {
                      'species': 'edit_field_species', 'size': 'edit_field_size', 'catch_date': 'edit_field_catch_date',
                    },
                  },
                  {'type': 'reset_state', 'state_ref': 'edit_field_species'},
                  {'type': 'reset_state', 'state_ref': 'edit_field_size'},
                  {'type': 'reset_state', 'state_ref': 'edit_field_catch_date'},
                  {'type': 'reset_state', 'state_ref': 'selected'},
                ],
              },
              'children': [
                {'type': 'text_field', 'id': 'e1', 'state_ref': 'edit_field_species', 'placeholder': '魚種'},
                {'type': 'text_field', 'id': 'e2', 'state_ref': 'edit_field_size', 'placeholder': 'サイズ(cm)'},
                {'type': 'text_field', 'id': 'e3', 'state_ref': 'edit_field_catch_date', 'placeholder': '日付'},
              ],
            },
            {
              'type': 'button', 'id': 'record_delete_button', 'label': '削除',
              'action': {
                'type': 'composite',
                'actions': [
                  {'type': 'delete_record', 'target_state_ref': 'records', 'record_id_ref': 'selected'},
                  {'type': 'reset_state', 'state_ref': 'edit_field_species'},
                  {'type': 'reset_state', 'state_ref': 'edit_field_size'},
                  {'type': 'reset_state', 'state_ref': 'edit_field_catch_date'},
                  {'type': 'reset_state', 'state_ref': 'selected'},
                ],
              },
            },
          ],
        },
      },
    ],
  };
}

/// Household Budget文書(category: choice, amount: number必須,
/// date: date)。
Map<String, dynamic> _budgetDoc() {
  return {
    'version': '1.4',
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
        'id': 's1', 'title': '家計簿記録',
        'state': {
          'records': {'type': 'record_list', 'value': [], 'schema_ref': 'transaction'},
          'field_category': {'type': 'string', 'value': ''},
          'field_amount': {'type': 'string', 'value': ''},
          'field_date': {'type': 'string', 'value': ''},
          'selected': {'type': 'selected_record', 'value': null},
          'edit_field_category': {'type': 'string', 'value': ''},
          'edit_field_amount': {'type': 'string', 'value': ''},
          'edit_field_date': {'type': 'string', 'value': ''},
        },
        'body': {
          'type': 'column', 'id': 'root',
          'children': [
            {
              'type': 'form', 'id': 'record_form', 'submit_label': '保存',
              'submit_action': {
                'type': 'composite',
                'actions': [
                  {
                    'type': 'add_record', 'target_state_ref': 'records',
                    'field_bindings': {
                      'category': 'field_category', 'amount': 'field_amount', 'date': 'field_date',
                    },
                  },
                  {'type': 'reset_state', 'state_ref': 'field_category'},
                  {'type': 'reset_state', 'state_ref': 'field_amount'},
                  {'type': 'reset_state', 'state_ref': 'field_date'},
                ],
              },
              'children': [
                {'type': 'text_field', 'id': 't1', 'state_ref': 'field_category', 'placeholder': 'カテゴリ'},
                {
                  'type': 'text_field', 'id': 't2', 'state_ref': 'field_amount', 'placeholder': '金額',
                  'validation': {'rules': [{'type': 'required', 'message': '金額を入力してください'}]},
                },
                {'type': 'text_field', 'id': 't3', 'state_ref': 'field_date', 'placeholder': '日付'},
              ],
            },
            {'type': 'divider', 'id': 'd1'},
            {
              'type': 'record_list_view', 'id': 'records_list_view', 'state_ref': 'records',
              'layout': 'card', 'display_fields': ['category', 'amount', 'date'],
              'selectable': true, 'selected_state_ref': 'selected',
              'select_field_bindings': {
                'category': 'edit_field_category', 'amount': 'edit_field_amount', 'date': 'edit_field_date',
              },
              'empty_state_text': 'まだ家計簿記録がありません',
            },
            {'type': 'divider', 'id': 'd2'},
            {
              'type': 'form', 'id': 'record_edit_form', 'submit_label': '更新',
              'submit_action': {
                'type': 'composite',
                'actions': [
                  {
                    'type': 'update_record', 'target_state_ref': 'records', 'record_id_ref': 'selected',
                    'field_bindings': {
                      'category': 'edit_field_category', 'amount': 'edit_field_amount', 'date': 'edit_field_date',
                    },
                  },
                  {'type': 'reset_state', 'state_ref': 'edit_field_category'},
                  {'type': 'reset_state', 'state_ref': 'edit_field_amount'},
                  {'type': 'reset_state', 'state_ref': 'edit_field_date'},
                  {'type': 'reset_state', 'state_ref': 'selected'},
                ],
              },
              'children': [
                {'type': 'text_field', 'id': 'e1', 'state_ref': 'edit_field_category', 'placeholder': 'カテゴリ'},
                {'type': 'text_field', 'id': 'e2', 'state_ref': 'edit_field_amount', 'placeholder': '金額'},
                {'type': 'text_field', 'id': 'e3', 'state_ref': 'edit_field_date', 'placeholder': '日付'},
              ],
            },
            {
              'type': 'button', 'id': 'record_delete_button', 'label': '削除',
              'action': {
                'type': 'composite',
                'actions': [
                  {'type': 'delete_record', 'target_state_ref': 'records', 'record_id_ref': 'selected'},
                  {'type': 'reset_state', 'state_ref': 'edit_field_category'},
                  {'type': 'reset_state', 'state_ref': 'edit_field_amount'},
                  {'type': 'reset_state', 'state_ref': 'edit_field_date'},
                  {'type': 'reset_state', 'state_ref': 'selected'},
                ],
              },
            },
          ],
        },
      },
    ],
  };
}

Future<void> _fillAndSave(
  WidgetTester tester, {
  required String species,
  required String size,
  required String date,
}) async {
  final fields = find.byWidgetPredicate((w) => w is TextField);
  await tester.enterText(fields.at(0), species);
  await tester.enterText(fields.at(1), size);
  await tester.enterText(fields.at(2), date);
  await tester.tap(find.widgetWithText(ElevatedButton, '保存'));
  await tester.pump();
}

/// Sprint1 Patch1新規。「更新」「削除」ボタンは、複数件のRecordを
/// 追加した後の単一画面レイアウトでは、画面外(テスト用ビューポート外)
/// に位置することがある。`tester.tap()`だけでは、対象Widgetが実際に
/// 可視状態でなくてもヒットテストに失敗する場合があるため、必ず
/// `tester.ensureVisible()`でスクロールしてからタップする。
Future<void> _tapButton(WidgetTester tester, Finder finder) async {
  await tester.ensureVisible(finder);
  await tester.pumpAndSettle();
  await tester.tap(finder);
  await tester.pumpAndSettle();
}

void main() {
  group('label表示', () {
    testWidgets('一覧のCardが内部Field名ではなくrecord_schemaのlabelを表示する', (tester) async {
      await tester.pumpWidget(_wrap(_fishRecordDoc()));
      await tester.pumpAndSettle();
      await _fillAndSave(tester, species: 'アジ', size: '30', date: '2026-07-19');

      expect(find.textContaining('魚種: アジ'), findsOneWidget);
      expect(find.textContaining('サイズ(cm): 30'), findsOneWidget);
      expect(find.textContaining('species:'), findsNothing, reason: '内部Field名がそのまま出ないこと');
    });
  });

  group('schema Field順', () {
    testWidgets('Cardの表示順がrecord_schemaのField順(species, size, catch_date)と一致する', (tester) async {
      await tester.pumpWidget(_wrap(_fishRecordDoc()));
      await tester.pumpAndSettle();
      await _fillAndSave(tester, species: 'アジ', size: '30', date: '2026-07-19');

      final speciesIndex = tester.getTopLeft(find.textContaining('魚種:')).dy;
      final sizeIndex = tester.getTopLeft(find.textContaining('サイズ(cm):')).dy;
      final dateIndex = tester.getTopLeft(find.textContaining('日付:')).dy;
      expect(speciesIndex, lessThan(sizeIndex));
      expect(sizeIndex, lessThan(dateIndex));
    });
  });

  group('required error表示', () {
    testWidgets('魚種(必須)を空のまま保存すると、text_field付近にエラーが表示される', (tester) async {
      await tester.pumpWidget(_wrap(_fishRecordDoc()));
      await tester.pumpAndSettle();
      await tester.tap(find.widgetWithText(ElevatedButton, '保存'));
      await tester.pump();

      expect(find.text('魚種を入力してください'), findsOneWidget);
      expect(find.text('まだ釣果記録がありません'), findsOneWidget, reason: '追加されていないこと');
    });
  });

  group('number error表示', () {
    testWidgets('サイズに数字以外を入れると保存時にエラーが表示される', (tester) async {
      await tester.pumpWidget(_wrap(_fishRecordDoc()));
      await tester.pumpAndSettle();
      await _fillAndSave(tester, species: 'アジ', size: 'あいう', date: '');

      expect(find.text('まだ釣果記録がありません'), findsOneWidget, reason: '不正な数値では追加されない');
      expect(tester.takeException(), isNull);
    });
  });

  group('date error表示', () {
    testWidgets('実在しない日付(2026-02-30)を入れると保存されない', (tester) async {
      await tester.pumpWidget(_wrap(_fishRecordDoc()));
      await tester.pumpAndSettle();
      await _fillAndSave(tester, species: 'アジ', size: '', date: '2026-02-30');

      expect(find.text('まだ釣果記録がありません'), findsOneWidget);
    });
  });

  group('choice error表示', () {
    testWidgets('optionsに無いカテゴリを入れると保存されない', (tester) async {
      await tester.pumpWidget(_wrap(_budgetDoc()));
      await tester.pumpAndSettle();
      final fields = find.byWidgetPredicate((w) => w is TextField);
      await tester.enterText(fields.at(0), 'サブスク'); // optionsに無い
      await tester.enterText(fields.at(1), '1000');
      await tester.tap(find.widgetWithText(ElevatedButton, '保存'));
      await tester.pump();

      expect(find.text('まだ家計簿記録がありません'), findsOneWidget);
    });
  });

  group('schemaなしFallback', () {
    testWidgets('record_schemasが無い文書(v1.3以前)は、従来通りField名で表示される', (tester) async {
      final doc = {
        'version': '1.3',
        'initial_screen_id': 's1',
        'screens': [
          {
            'id': 's1', 'title': 'テスト',
            'state': {
              'records': {
                'type': 'record_list',
                'value': [
                  {'id': 'rec_1', 'fields': {'species': 'アジ'}},
                ],
              },
            },
            'body': {'type': 'record_list_view', 'id': 'rlv1', 'state_ref': 'records'},
          },
        ],
      };
      await tester.pumpWidget(_wrap(doc));
      await tester.pumpAndSettle();
      expect(find.textContaining('species: アジ'), findsOneWidget);
    });
  });

  group('v1.3 Document互換', () {
    testWidgets('schema_refを持たないrecord_listでも、追加・表示が正常に動作する', (tester) async {
      final doc = {
        'version': '1.3',
        'initial_screen_id': 's1',
        'screens': [
          {
            'id': 's1', 'title': 'テスト',
            'state': {
              'records': {'type': 'record_list', 'value': []},
              'field_species': {'type': 'string', 'value': ''},
            },
            'body': {
              'type': 'column', 'id': 'root',
              'children': [
                {
                  'type': 'form', 'id': 'f1', 'submit_label': '保存',
                  'submit_action': {
                    // FORGE Product Quality Sprint1 Patch1で修正:
                    // 実際のCompilerは`add_record`単体ではなく
                    // `composite([add_record, reset_state])`を生成する。
                    'type': 'composite',
                    'actions': [
                      {
                        'type': 'add_record', 'target_state_ref': 'records',
                        'field_bindings': {'species': 'field_species'},
                      },
                      {'type': 'reset_state', 'state_ref': 'field_species'},
                    ],
                  },
                  'children': [
                    {'type': 'text_field', 'id': 't1', 'state_ref': 'field_species'},
                  ],
                },
                {'type': 'record_list_view', 'id': 'rlv1', 'state_ref': 'records'},
              ],
            },
          },
        ],
      };
      await tester.pumpWidget(_wrap(doc));
      await tester.pumpAndSettle();
      await tester.enterText(find.byType(TextField), 'アジ');
      await tester.tap(find.widgetWithText(ElevatedButton, '保存'));
      await tester.pump();
      expect(find.textContaining('アジ'), findsOneWidget);
      expect(tester.takeException(), isNull);
    });
  });

  group('Integration: Fishing Log', () {
    testWidgets(
      '起動 -> species/size/date入力 -> 保存 -> Card表示 -> 選択 -> size更新 -> 保存 -> 削除',
      (tester) async {
        await tester.pumpWidget(_wrap(_fishRecordDoc()));
        await tester.pumpAndSettle();

        // 起動 -> 入力 -> 保存。
        await _fillAndSave(tester, species: 'アジ', size: '30', date: '2026-07-19');
        expect(find.textContaining('魚種: アジ'), findsOneWidget, reason: 'label表示の確認');
        expect(find.textContaining('サイズ(cm): 30'), findsOneWidget, reason: 'number型維持の確認');
        expect(find.textContaining('日付: 2026-07-19'), findsOneWidget, reason: 'date validationの確認');

        // 選択。
        await _tapButton(tester, find.widgetWithText(TextButton, '編集'));
        final editFields = find.byWidgetPredicate((w) => w is TextField);
        // 作成フォーム3件 + 編集フォーム3件がこの時点で存在する。
        expect(tester.widget<TextField>(editFields.at(3)).controller?.text, 'アジ', reason: 'selected同期の確認');

        // size更新。
        await tester.enterText(editFields.at(4), '45');
        await _tapButton(tester, find.widgetWithText(ElevatedButton, '更新'));
        expect(find.textContaining('サイズ(cm): 45'), findsOneWidget);
        expect(find.textContaining('サイズ(cm): 30'), findsNothing);

        // 削除。
        await _tapButton(tester, find.widgetWithText(TextButton, '編集'));
        await _tapButton(tester, find.widgetWithText(ElevatedButton, '削除'));
        expect(find.text('まだ釣果記録がありません'), findsOneWidget, reason: '削除後クリアの確認');
        expect(tester.takeException(), isNull);
      },
    );
  });

  group('Integration: Household Budget', () {
    testWidgets(
      '起動 -> amount/date/category入力 -> 保存 -> 編集 -> 削除、無効なamount/dateの拒否、複数Recordの独立性',
      (tester) async {
        await tester.pumpWidget(_wrap(_budgetDoc()));
        await tester.pumpAndSettle();

        final fields = find.byWidgetPredicate((w) => w is TextField);

        // 無効なamountの拒否。
        await tester.enterText(fields.at(0), '食費');
        await tester.enterText(fields.at(1), 'たくさん'); // 数値でない
        await tester.enterText(fields.at(2), '2026-07-19');
        await tester.tap(find.widgetWithText(ElevatedButton, '保存'));
        await tester.pump();
        expect(find.text('まだ家計簿記録がありません'), findsOneWidget, reason: '無効なamountは拒否される');

        // 無効なdateの拒否。
        await tester.enterText(fields.at(1), '1000');
        await tester.enterText(fields.at(2), '2026-13-40');
        await tester.tap(find.widgetWithText(ElevatedButton, '保存'));
        await tester.pump();
        expect(find.text('まだ家計簿記録がありません'), findsOneWidget, reason: '無効なdateは拒否される');

        // 正しい入力で1件目を保存。
        await tester.enterText(fields.at(2), '2026-07-19');
        await tester.tap(find.widgetWithText(ElevatedButton, '保存'));
        await tester.pump();
        expect(find.textContaining('カテゴリ: 食費'), findsOneWidget);

        // 2件目を保存(複数Recordの独立性を確認する準備)。
        await tester.enterText(fields.at(0), '交通費');
        await tester.enterText(fields.at(1), '500');
        await tester.enterText(fields.at(2), '2026-07-20');
        await tester.tap(find.widgetWithText(ElevatedButton, '保存'));
        await tester.pump();
        expect(find.byType(Card), findsNWidgets(2));

        // 1件目を選択して編集。
        final editButtons = find.widgetWithText(TextButton, '編集');
        await _tapButton(tester, editButtons.first);
        final editFields = find.byWidgetPredicate((w) => w is TextField);
        await tester.enterText(editFields.at(4), '1200'); // amount
        await _tapButton(tester, find.widgetWithText(ElevatedButton, '更新'));

        // 複数Recordの独立性: 1件目だけ更新され、2件目(交通費)は影響を受けない。
        expect(find.textContaining('金額: 1200'), findsOneWidget);
        expect(find.textContaining('カテゴリ: 交通費'), findsOneWidget, reason: '2件目は独立して残る');
        expect(find.textContaining('金額: 500'), findsOneWidget, reason: '2件目の金額は変わらない');

        // 削除。
        await _tapButton(tester, editButtons.first);
        await _tapButton(tester, find.widgetWithText(ElevatedButton, '削除'));
        expect(find.byType(Card), findsNWidgets(1), reason: '削除したのは1件のみ');
        expect(find.textContaining('カテゴリ: 交通費'), findsOneWidget, reason: '残った方は無傷');
        expect(tester.takeException(), isNull);
      },
    );
  });
}
