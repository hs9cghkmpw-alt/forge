// record_list_view Widget Test(選択・編集・削除) + Integration Test
// (FORGE v0.8 Record Runtime Phase2)。
//
// 指示書「Widget Test」節(Card選択・編集反映・削除反映)と「Integration」
// 節(Flutter → Record追加 → Record選択 → 編集 → 削除)の両方をこの
// ファイルでカバーする。v1_3_record_list_view_test.dart(Phase1)と同じ、
// 実際のJSONからForgeDocumentView経由で描画する検証方式を踏襲する。
//
// 注記: Claudeのサンドボックスに Dart SDK が無いため、このファイルは
// 一度も `flutter test` で実行されていない。CEO環境での実行が必須。

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:forge_app/core/theme/forge_theme.dart';
import 'package:forge_app/json_ui/renderer/forge_renderer.dart';

Map<String, dynamic> _screenDoc(Map<String, dynamic> body, {Map<String, dynamic>? state}) {
  return {
    'version': '1.3',
    'initial_screen_id': 's1',
    'screens': [
      {'id': 's1', 'title': 'テスト画面', 'state': state ?? <String, dynamic>{}, 'body': body},
    ],
  };
}

Widget _wrap(Map<String, dynamic> doc) {
  return MaterialApp(theme: ForgeTheme.theme, home: ForgeDocumentView(rawJson: doc));
}

/// `ForgeLanguageCompiler`(forge_ai側)が実際に生成する、CRUD対応済みの
/// 構成(create form + selectable record_list_view + edit form +
/// delete button、単一画面)を模した文書。
Map<String, dynamic> _fishRecordCrudDoc() {
  return _screenDoc(
    {
      'type': 'column', 'id': 'root',
      'children': [
        {
          'type': 'form', 'id': 'record_form', 'submit_label': '保存',
          'submit_action': {
            // FORGE Product Quality Sprint1 Patch1で修正: 実際のCompiler
            // (`forge_language_compiler.py`)は、`add_record`単体ではなく
            // 必ず`composite([add_record, reset_state(...)])`を生成する
            // (作成フォームは送信後に空へ戻る)。以前このテスト用の
            // 文書は`add_record`単体のままになっており、実際のCompiler
            // 出力と乖離していた。この乖離が、送信後も作成欄に前回入力
            // した文字列が残ったままになり、`find.textContaining`が
            // 「一覧のCard」と「作成欄のEditableText」の両方へヒットして
            // `findsOneWidget`が2件検出で失敗する、という具体的な不具合の
            // 原因になっていた(Runtime自体のバグではなく、テスト文書が
            // 実際のCompiler出力の形を正しく再現できていなかったことに
            // 起因する)。
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
            {'type': 'text_field', 'id': 'field_species_input', 'state_ref': 'field_species', 'placeholder': '魚種'},
          ],
        },
        {'type': 'divider', 'id': 'd1'},
        {
          'type': 'record_list_view', 'id': 'records_list_view', 'state_ref': 'records',
          'layout': 'card', 'display_fields': ['species'],
          'selectable': true, 'selected_state_ref': 'selected',
          'select_field_bindings': {'species': 'edit_field_species'},
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
                'field_bindings': {'species': 'edit_field_species'},
              },
              {'type': 'reset_state', 'state_ref': 'edit_field_species'},
              {'type': 'reset_state', 'state_ref': 'selected'},
            ],
          },
          'children': [
            {'type': 'text_field', 'id': 'edit_field_species_input', 'state_ref': 'edit_field_species', 'placeholder': '魚種'},
          ],
        },
        {
          'type': 'button', 'id': 'record_delete_button', 'label': '削除',
          'action': {
            'type': 'composite',
            'actions': [
              {'type': 'delete_record', 'target_state_ref': 'records', 'record_id_ref': 'selected'},
              {'type': 'reset_state', 'state_ref': 'edit_field_species'},
              {'type': 'reset_state', 'state_ref': 'selected'},
            ],
          },
        },
      ],
    },
    state: {
      'records': {'type': 'record_list', 'value': []},
      'selected': {'type': 'selected_record', 'value': null},
      'field_species': {'type': 'string', 'value': ''},
      'edit_field_species': {'type': 'string', 'value': ''},
    },
  );
}

Future<void> _addRecord(WidgetTester tester, String species) async {
  final createField = find.byWidgetPredicate((w) => w is TextField).first;
  await tester.enterText(createField, species);
  await tester.tap(find.widgetWithText(ElevatedButton, '保存'));
  await tester.pump();
}

/// Sprint1 Patch1新規。「更新」「削除」ボタンは、複数件のRecordを
/// 追加した後の単一画面レイアウトでは、画面外(テスト用ビューポート外)
/// に位置することがある。必ず`tester.ensureVisible()`でスクロールして
/// からタップする(v1_0_typed_schema_widget_test.dartと同じ理由)。
Future<void> _tapButton(WidgetTester tester, Finder finder) async {
  await tester.ensureVisible(finder);
  await tester.pumpAndSettle();
  await tester.tap(finder);
  await tester.pumpAndSettle();
}

void main() {
  group('Card選択', () {
    testWidgets('「編集」ボタンをタップすると、そのCardが選択状態(「選択中」表示)になる', (tester) async {
      await tester.pumpWidget(_wrap(_fishRecordCrudDoc()));
      await tester.pumpAndSettle();

      await _addRecord(tester, 'アジ');
      expect(find.text('編集'), findsOneWidget);
      expect(find.text('選択中'), findsNothing);

      await _tapButton(tester, find.widgetWithText(TextButton, '編集'));

      expect(find.text('選択中'), findsOneWidget);
      expect(tester.takeException(), isNull);
    });

    testWidgets('選択すると、編集フォームへFieldの値が反映される(select_field_bindings)', (tester) async {
      await tester.pumpWidget(_wrap(_fishRecordCrudDoc()));
      await tester.pumpAndSettle();

      await _addRecord(tester, 'アジ');
      await _tapButton(tester, find.widgetWithText(TextButton, '編集'));

      final textFields = find.byWidgetPredicate((w) => w is TextField);
      // 1つ目=作成フォーム(空のまま)、2つ目=編集フォーム(「アジ」が反映される)。
      final editField = tester.widget<TextField>(textFields.at(1));
      expect(editField.controller?.text, 'アジ');
    });
  });

  group('編集反映', () {
    testWidgets('編集フォームで値を変えて「更新」すると、一覧のCardへ即座に反映される', (tester) async {
      await tester.pumpWidget(_wrap(_fishRecordCrudDoc()));
      await tester.pumpAndSettle();

      await _addRecord(tester, 'アジ');
      await _tapButton(tester, find.widgetWithText(TextButton, '編集'));

      final textFields = find.byWidgetPredicate((w) => w is TextField);
      await tester.enterText(textFields.at(1), 'サバ');
      await _tapButton(tester, find.widgetWithText(ElevatedButton, '更新'));

      expect(find.textContaining('アジ'), findsNothing, reason: '更新後は古い値が残っていないこと');
      expect(find.textContaining('サバ'), findsOneWidget);
      expect(tester.takeException(), isNull);
    });

    testWidgets('更新後、選択状態が解除される(「選択中」表示が消える)', (tester) async {
      await tester.pumpWidget(_wrap(_fishRecordCrudDoc()));
      await tester.pumpAndSettle();

      await _addRecord(tester, 'アジ');
      await _tapButton(tester, find.widgetWithText(TextButton, '編集'));
      await _tapButton(tester, find.widgetWithText(ElevatedButton, '更新'));

      expect(find.text('選択中'), findsNothing);
      expect(find.text('編集'), findsOneWidget);
    });
  });

  group('削除反映', () {
    testWidgets('選択して「削除」すると、一覧から即座に消える', (tester) async {
      await tester.pumpWidget(_wrap(_fishRecordCrudDoc()));
      await tester.pumpAndSettle();

      await _addRecord(tester, 'アジ');
      expect(find.textContaining('アジ'), findsOneWidget);

      await _tapButton(tester, find.widgetWithText(TextButton, '編集'));
      await _tapButton(tester, find.widgetWithText(ElevatedButton, '削除'));

      expect(find.textContaining('アジ'), findsNothing);
      expect(find.text('まだ釣果記録がありません'), findsOneWidget);
      expect(tester.takeException(), isNull);
    });

    testWidgets('2件のうち選択した1件だけが削除され、もう1件は残る', (tester) async {
      await tester.pumpWidget(_wrap(_fishRecordCrudDoc()));
      await tester.pumpAndSettle();

      await _addRecord(tester, 'アジ');
      await _addRecord(tester, 'サバ');
      expect(find.byType(Card), findsNWidgets(2));

      // 1件目(アジ)を選択して削除する。
      final editButtons = find.widgetWithText(TextButton, '編集');
      await _tapButton(tester, editButtons.first);
      await _tapButton(tester, find.widgetWithText(ElevatedButton, '削除'));

      expect(find.byType(Card), findsNWidgets(1));
      expect(find.textContaining('サバ'), findsOneWidget, reason: '削除していない方は残る');
      expect(find.textContaining('アジ'), findsNothing);
    });

    testWidgets('無選択のまま「削除」を押しても例外にならない(noOpとして安全に失敗する)', (tester) async {
      await tester.pumpWidget(_wrap(_fishRecordCrudDoc()));
      await tester.pumpAndSettle();

      await _addRecord(tester, 'アジ');
      // 編集(選択)せずにいきなり削除を押す。
      await _tapButton(tester, find.widgetWithText(ElevatedButton, '削除'));

      expect(find.textContaining('アジ'), findsOneWidget, reason: '無選択の削除は何も起きない');
      expect(tester.takeException(), isNull);
    });
  });

  group('Integration: Record追加 -> Record選択 -> 編集 -> 削除', () {
    testWidgets('一連の操作を最初から最後まで通しで確認する', (tester) async {
      // 1. 起動。
      await tester.pumpWidget(_wrap(_fishRecordCrudDoc()));
      await tester.pumpAndSettle();
      expect(find.text('まだ釣果記録がありません'), findsOneWidget);

      // 2. Record追加。
      await _addRecord(tester, 'アジ');
      expect(find.text('まだ釣果記録がありません'), findsNothing);
      expect(find.textContaining('アジ'), findsOneWidget);
      expect(find.byType(Card), findsNWidgets(1));

      // 3. Record選択。
      await _tapButton(tester, find.widgetWithText(TextButton, '編集'));
      expect(find.text('選択中'), findsOneWidget);
      final textFieldsAfterSelect = find.byWidgetPredicate((w) => w is TextField);
      final editFieldAfterSelect = tester.widget<TextField>(textFieldsAfterSelect.at(1));
      expect(editFieldAfterSelect.controller?.text, 'アジ', reason: '選択時に編集フォームへ反映される');

      // 4. 編集。
      await tester.enterText(textFieldsAfterSelect.at(1), 'カレイ');
      await _tapButton(tester, find.widgetWithText(ElevatedButton, '更新'));
      expect(find.textContaining('アジ'), findsNothing);
      expect(find.textContaining('カレイ'), findsOneWidget);
      expect(find.text('選択中'), findsNothing, reason: '更新後は選択が解除される');

      // 5. 削除(まず選択してから)。
      await _tapButton(tester, find.widgetWithText(TextButton, '編集'));
      await _tapButton(tester, find.widgetWithText(ElevatedButton, '削除'));
      expect(find.textContaining('カレイ'), findsNothing);
      expect(find.text('まだ釣果記録がありません'), findsOneWidget);
      expect(find.byType(Card), findsNothing);

      expect(tester.takeException(), isNull);
    });
  });
}
