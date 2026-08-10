// record_list_view Widget Test + Integration Test(FORGE v0.7 Record
// Runtime Phase1)。
//
// 指示書「Widget Test」節(record_list_view(card)表示・追加後即時反映)と
// 「Integration」節(Flutter → Runtime → State更新 → Widget更新)の両方を
// このファイルでカバーする。実際のJSON文字列(rawJson)から
// `ForgeDocumentView`経由で描画する、v1_1_widgets_test.dartと同じ
// 実物に近い検証方式を踏襲する。
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

/// `ForgeLanguageCompiler`(Backend/forge_ai側)が実際に生成する構成
/// (form + divider + record_list_view、単一画面)を模した文書。
/// Backend/forge_ai側のテストは既にPython側で実施済みのため、ここでは
/// 同じ形をFlutter Runtime側で独立に検証する。
Map<String, dynamic> _fishRecordDoc() {
  return _screenDoc(
    {
      'type': 'column', 'id': 'root',
      'children': [
        {
          'type': 'form', 'id': 'record_form', 'submit_label': '保存',
          'submit_action': {
            // FORGE Product Quality Sprint1 Patch1で修正: 実際のCompiler
            // は`add_record`単体ではなく`composite([add_record,
            // reset_state, reset_state])`を生成する
            // (v1_3_record_crud_test.dart参照、同じ理由)。
            'type': 'composite',
            'actions': [
              {
                'type': 'add_record',
                'target_state_ref': 'records',
                'field_bindings': {'species': 'field_species', 'size': 'field_size'},
              },
              {'type': 'reset_state', 'state_ref': 'field_species'},
              {'type': 'reset_state', 'state_ref': 'field_size'},
            ],
          },
          'children': [
            {
              'type': 'text_field', 'id': 'field_species_input', 'state_ref': 'field_species',
              'placeholder': '魚種',
              'validation': {
                'rules': [
                  {'type': 'required', 'message': '魚種を入力してください'},
                ],
              },
            },
            {'type': 'text_field', 'id': 'field_size_input', 'state_ref': 'field_size', 'placeholder': 'サイズ(cm)'},
          ],
        },
        {'type': 'divider', 'id': 'form_list_divider'},
        {
          'type': 'record_list_view', 'id': 'records_list_view', 'state_ref': 'records',
          'layout': 'card', 'display_fields': ['species', 'size'],
          'empty_state_text': 'まだ釣果記録がありません',
        },
      ],
    },
    state: {
      'records': {'type': 'record_list', 'value': []},
      'field_species': {'type': 'string', 'value': ''},
      'field_size': {'type': 'string', 'value': ''},
    },
  );
}

void main() {
  group('record_list_view(card)表示', () {
    testWidgets('空のrecord_listではempty_state_textが表示される', (tester) async {
      final doc = _screenDoc(
        {'type': 'record_list_view', 'id': 'rlv1', 'state_ref': 'records', 'empty_state_text': 'まだ記録がないよ'},
        state: {'records': {'type': 'record_list', 'value': []}},
      );
      await tester.pumpWidget(_wrap(doc));
      await tester.pumpAndSettle();
      expect(find.text('まだ記録がないよ'), findsOneWidget);
      expect(tester.takeException(), isNull);
    });

    testWidgets('初期値に含まれるRecordがCardとして表示される(複数Field)', (tester) async {
      final doc = _screenDoc(
        {
          'type': 'record_list_view', 'id': 'rlv1', 'state_ref': 'records',
          'display_fields': ['species', 'size'],
        },
        state: {
          'records': {
            'type': 'record_list',
            'value': [
              {'id': 'rec_1', 'fields': {'species': 'アジ', 'size': '30'}},
            ],
          },
        },
      );
      await tester.pumpWidget(_wrap(doc));
      await tester.pumpAndSettle();
      // Stage1(checklist方式)ではprimary Fieldしか出せなかったが、
      // v1.3では両方のFieldが同じCardに表示される(FORGE v0.7の核心)。
      expect(find.textContaining('アジ'), findsOneWidget);
      expect(find.textContaining('30'), findsOneWidget);
      expect(find.byType(Card), findsOneWidget);
      expect(tester.takeException(), isNull);
    });

    testWidgets('複数件のRecordがそれぞれ別のCardとして表示される', (tester) async {
      final doc = _screenDoc(
        {'type': 'record_list_view', 'id': 'rlv1', 'state_ref': 'records', 'display_fields': ['species']},
        state: {
          'records': {
            'type': 'record_list',
            'value': [
              {'id': 'rec_1', 'fields': {'species': 'アジ'}},
              {'id': 'rec_2', 'fields': {'species': 'サバ'}},
            ],
          },
        },
      );
      await tester.pumpWidget(_wrap(doc));
      await tester.pumpAndSettle();
      expect(find.byType(Card), findsNWidgets(2));
      expect(find.textContaining('アジ'), findsOneWidget);
      expect(find.textContaining('サバ'), findsOneWidget);
    });
  });

  group('追加後即時反映', () {
    testWidgets('フォーム送信後、record_list_viewが即座に更新される(AnimatedBuilder経由)', (tester) async {
      await tester.pumpWidget(_wrap(_fishRecordDoc()));
      await tester.pumpAndSettle();

      // 追加前: 空状態のテキストが出ている。
      expect(find.text('まだ釣果記録がありません'), findsOneWidget);

      await tester.enterText(find.byWidgetPredicate((w) => w is TextField).first, 'アジ');
      await tester.enterText(find.byWidgetPredicate((w) => w is TextField).at(1), '30');
      await tester.tap(find.widgetWithText(ElevatedButton, '保存'));
      await tester.pump();

      // 追加後: 空状態のテキストは消え、新しいRecordが即座にCardとして
      // 表示される(setState/notifyListeners経由の即時反映)。
      expect(find.text('まだ釣果記録がありません'), findsNothing);
      expect(find.textContaining('アジ'), findsOneWidget);
      expect(find.textContaining('30'), findsOneWidget);
      expect(tester.takeException(), isNull);
    });

    testWidgets('必須Field未入力では、Validationにより追加が阻止される', (tester) async {
      await tester.pumpWidget(_wrap(_fishRecordDoc()));
      await tester.pumpAndSettle();

      // 魚種(必須)を空のまま送信する。
      await tester.tap(find.widgetWithText(ElevatedButton, '保存'));
      await tester.pump();

      // Validation失敗のため、record_listへは反映されない
      // (空状態のテキストが残ったまま)。
      expect(find.text('まだ釣果記録がありません'), findsOneWidget);
      expect(tester.takeException(), isNull);
    });
  });

  group('Integration: Flutter -> Runtime -> State更新 -> Widget更新', () {
    testWidgets(
      'JSON解析 -> Form入力 -> add_record実行 -> State更新 -> record_list_view再描画 まで一気通貫で確認する',
      (tester) async {
        // 1. 生JSON文字列相当のMapから、ForgeDocumentView経由で実際にパース・
        //    描画する(Backendが実際に返すレスポンスの形を模す)。
        await tester.pumpWidget(_wrap(_fishRecordDoc()));
        await tester.pumpAndSettle();
        expect(find.widgetWithText(ElevatedButton, '保存'), findsOneWidget);

        // 2. ユーザー入力(2つのtext_field、複数Field)。
        final textFields = find.byWidgetPredicate((w) => w is TextField);
        expect(textFields, findsNWidgets(2));
        await tester.enterText(textFields.first, 'カレイ');
        await tester.enterText(textFields.at(1), '45');
        await tester.pump();

        // 3. 送信(SubmitFormAction -> Validation -> add_record -> reset_state x2)。
        await tester.tap(find.widgetWithText(ElevatedButton, '保存'));
        await tester.pump();

        // 4. State更新の確認(record_list_viewが新しいRecordを表示)。
        expect(find.textContaining('カレイ'), findsOneWidget);
        expect(find.textContaining('45'), findsOneWidget);

        // 5. reset_stateにより、フォームの入力欄が空へ戻っていること。
        final speciesField = tester.widget<TextField>(textFields.first);
        expect(speciesField.controller?.text, '', reason: 'add_record後、reset_stateでフォームが空に戻る');

        // 6. さらにもう1件追加し、1件目が消えずに残ること(累積の確認)。
        await tester.enterText(textFields.first, 'ヒラメ');
        await tester.enterText(textFields.at(1), '50');
        await tester.tap(find.widgetWithText(ElevatedButton, '保存'));
        await tester.pump();

        expect(find.textContaining('カレイ'), findsOneWidget, reason: '1件目が消えていないこと');
        expect(find.textContaining('ヒラメ'), findsOneWidget, reason: '2件目が追加されていること');
        expect(find.byType(Card), findsNWidgets(2));
        expect(tester.takeException(), isNull);
      },
    );
  });
}
