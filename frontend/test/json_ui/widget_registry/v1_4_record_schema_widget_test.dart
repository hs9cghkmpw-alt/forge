// record_schema付きJSONが読める(FORGE v0.9 Typed Record Runtime
// Phase1、指示書「Flutter」節)。
//
// record_schemasを含むJSON文書が、ForgeDocumentView経由で例外無く
// 解析・描画でき、かつ既存(record_schema無し)と全く同じ見た目に
// なることを確認する(指示書「まだUIを変えないでください」の裏付け)。
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

Map<String, dynamic> _fishRecordSchema() {
  return {
    'fields': [
      {'name': 'species', 'type': 'string', 'label': '魚種', 'required': true},
      {'name': 'size', 'type': 'number', 'label': 'サイズ(cm)', 'required': false},
      {'name': 'date', 'type': 'date', 'label': '日付', 'required': false},
      {'name': 'memo', 'type': 'string', 'label': 'メモ', 'required': false},
    ],
  };
}

/// `body`・`state`はFORGE v0.8のCRUDドキュメント(v1_3_record_crud_test.dart
/// の`_fishRecordCrudDoc()`)と意図的に同一の形にしている。違いは
/// `version`と`record_schemas`・`schema_ref`の有無のみ(FORGE v0.9が
/// 型情報の追加のみで、Widget構成には一切影響しないことを確認するため)。
Map<String, dynamic> _bodyAndState() {
  return {
    'body': {
      'type': 'column', 'id': 'root',
      'children': [
        {
          'type': 'form', 'id': 'record_form', 'submit_label': '保存',
          'submit_action': {
            // FORGE Product Quality Sprint1 Patch1で修正: 実際のCompiler
            // は`add_record`単体ではなく`composite([add_record,
            // reset_state])`を生成する。v1_3_record_crud_test.dartと
            // 同じ理由で修正した。
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
          'empty_state_text': 'まだ釣果記録がありません',
        },
      ],
    },
    'state': {
      'records': {'type': 'record_list', 'value': <dynamic>[]},
      'field_species': {'type': 'string', 'value': ''},
    },
  };
}

Map<String, dynamic> _docWithoutSchema() {
  final parts = _bodyAndState();
  return {
    'version': '1.3',
    'initial_screen_id': 's1',
    'screens': [
      {'id': 's1', 'title': 'テスト画面', 'state': parts['state'], 'body': parts['body']},
    ],
  };
}

Map<String, dynamic> _docWithSchema() {
  final parts = _bodyAndState();
  final state = Map<String, dynamic>.from(parts['state'] as Map<String, dynamic>);
  state['records'] = {'type': 'record_list', 'value': <dynamic>[], 'schema_ref': 'fish_record'};
  return {
    'version': '1.4',
    'initial_screen_id': 's1',
    'record_schemas': {'fish_record': _fishRecordSchema()},
    'screens': [
      {'id': 's1', 'title': 'テスト画面', 'state': state, 'body': parts['body']},
    ],
  };
}

void main() {
  group('record_schema付きJSONが読める', () {
    testWidgets('record_schemasを含む文書が例外無く解析・描画できる', (tester) async {
      await tester.pumpWidget(_wrap(_docWithSchema()));
      await tester.pumpAndSettle();

      expect(find.text('まだ釣果記録がありません'), findsOneWidget);
      expect(find.byType(TextField), findsOneWidget);
      expect(tester.takeException(), isNull);
    });

    testWidgets('record_schema付きでも、通常通りRecordの追加が動作する', (tester) async {
      await tester.pumpWidget(_wrap(_docWithSchema()));
      await tester.pumpAndSettle();

      await tester.enterText(find.byType(TextField).first, 'アジ');
      await tester.tap(find.widgetWithText(ElevatedButton, '保存'));
      await tester.pump();

      expect(find.textContaining('アジ'), findsOneWidget);
      expect(find.text('まだ釣果記録がありません'), findsNothing);
      expect(tester.takeException(), isNull);
    });

    testWidgets('record_schemasの有無でWidget構成(種類・個数)が変わらない(UI無変更の裏付け)', (tester) async {
      await tester.pumpWidget(_wrap(_docWithoutSchema()));
      await tester.pumpAndSettle();
      final withoutSchemaTextFieldCount = find.byType(TextField).evaluate().length;
      final withoutSchemaFormCount = find.byType(Form).evaluate().length;

      await tester.pumpWidget(_wrap(_docWithSchema()));
      await tester.pumpAndSettle();
      final withSchemaTextFieldCount = find.byType(TextField).evaluate().length;
      final withSchemaFormCount = find.byType(Form).evaluate().length;

      expect(withSchemaTextFieldCount, withoutSchemaTextFieldCount);
      expect(withSchemaFormCount, withoutSchemaFormCount);
      expect(find.text('まだ釣果記録がありません'), findsOneWidget);
    });

    testWidgets('record_schemasが無い(v1.3以前相当の)文書も引き続き読める(後方互換)', (tester) async {
      await tester.pumpWidget(_wrap(_docWithoutSchema()));
      await tester.pumpAndSettle();

      expect(find.text('まだ釣果記録がありません'), findsOneWidget);
      expect(tester.takeException(), isNull);
    });
  });
}
