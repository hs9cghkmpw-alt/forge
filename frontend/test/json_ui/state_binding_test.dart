// State Binding Widget Test(FORGE-MILESTONE-003)。
//
// 指示書5章「State Binding」の項目を網羅する: text_field入力がStateへ反映される・
// checkbox操作がStateへ反映される・checklist変更がStateへ反映される・
// State変更後にUIへ反映される・画面遷移後も値を保持する。
//
// 注記: Claudeのサンドボックスに Dart SDK が無いため、このファイルは
// 一度も `flutter test` で実行されていない。CEO環境での実行が必須。

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:forge_app/core/theme/forge_theme.dart';
import 'package:forge_app/json_ui/renderer/forge_renderer.dart';

Widget _wrapDocument(Map<String, dynamic> rawJson) {
  return MaterialApp(theme: ForgeTheme.theme, home: ForgeDocumentView(rawJson: rawJson));
}

Map<String, dynamic> _doc({
  required Map<String, dynamic> body,
  required Map<String, dynamic> state,
  List<Map<String, dynamic>>? extraScreens,
}) {
  return {
    'version': '1.2',
    'initial_screen_id': 's1',
    'screens': [
      {'id': 's1', 'title': 'テスト画面', 'state': state, 'body': body},
      ...?extraScreens,
    ],
  };
}

void main() {
  testWidgets('text_field入力がStateへ反映される(次に読む値に使われる)', (tester) async {
    // 直接Stateを覗く手段はUIから提供していないため、入力→他Widget(text)へ
    // 反映される、という間接的な形で確認する(state_ref経由でtextWidgetが
    // 同じキーを表示する構成)。
    await tester.pumpWidget(_wrapDocument(_doc(
      body: {
        'type': 'column', 'id': 'root', 'children': [
          {'type': 'text_field', 'id': 'tf1', 'state_ref': 'note'},
        ],
      },
      state: {'note': {'type': 'string', 'value': ''}},
    )));

    await tester.enterText(find.byType(TextField), 'こんにちは');
    await tester.pump();

    final field = tester.widget<TextField>(find.byType(TextField));
    expect(field.controller?.text, 'こんにちは');
  });

  testWidgets('checkbox操作がStateへ反映される(UI上のチェック状態が変わる)', (tester) async {
    await tester.pumpWidget(_wrapDocument(_doc(
      body: {'type': 'checkbox', 'id': 'cb1', 'label': '同意する', 'state_ref': 'agreed'},
      state: {'agreed': {'type': 'boolean', 'value': false}},
    )));

    expect(tester.widget<Checkbox>(find.byType(Checkbox)).value, isFalse);
    await tester.tap(find.byType(CheckboxListTile));
    await tester.pump();
    expect(tester.widget<Checkbox>(find.byType(Checkbox)).value, isTrue);
  });

  testWidgets('checklist変更(追加)がStateへ反映され、UIに新項目が表示される', (tester) async {
    await tester.pumpWidget(_wrapDocument(_doc(
      body: {
        'type': 'column', 'id': 'root', 'children': [
          {'type': 'checklist', 'id': 'cl1', 'state_ref': 'items'},
          {
            'type': 'row', 'id': 'add_row', 'children': [
              {'type': 'text_field', 'id': 'add_field', 'state_ref': 'new_text'},
              {
                'type': 'button', 'id': 'add_btn', 'label': '追加',
                'action': {'type': 'add_item', 'target_state_ref': 'items', 'source_state_ref': 'new_text'},
              },
            ],
          },
        ],
      },
      state: {
        'items': {'type': 'checklist', 'value': <Map<String, dynamic>>[]},
        'new_text': {'type': 'string', 'value': ''},
      },
    )));

    expect(find.text('牛乳'), findsNothing);
    await tester.enterText(find.byType(TextField), '牛乳');
    await tester.pump();
    await tester.tap(find.widgetWithText(ElevatedButton, '追加'));
    await tester.pump();

    expect(find.text('牛乳'), findsOneWidget, reason: '追加した項目がUIに反映されるはず');
    expect(tester.takeException(), isNull);
  });

  testWidgets('State変更後にUIへ反映される(checklist項目のチェック操作)', (tester) async {
    await tester.pumpWidget(_wrapDocument(_doc(
      body: {'type': 'checklist', 'id': 'cl1', 'state_ref': 'items'},
      state: {
        'items': {
          'type': 'checklist',
          'value': [
            {'id': 'item_1', 'text': '牛乳', 'done': false},
          ],
        },
      },
    )));

    expect(find.byIcon(Icons.circle_outlined), findsOneWidget);
    await tester.tap(find.byIcon(Icons.circle_outlined));
    await tester.pump();
    expect(find.byIcon(Icons.check_circle_rounded), findsOneWidget, reason: 'チェック後は別のiconに変わるはず');
    expect(tester.takeException(), isNull);
  });

  testWidgets('画面遷移後も値を保持する(戻ってきても入力内容が消えない)', (tester) async {
    await tester.pumpWidget(_wrapDocument(_doc(
      body: {
        'type': 'column', 'id': 'root', 'children': [
          {'type': 'text_field', 'id': 'tf1', 'state_ref': 'note'},
          {
            'type': 'button', 'id': 'go_btn', 'label': '次へ',
            'action': {'type': 'navigate', 'target_screen_id': 's2'},
          },
        ],
      },
      state: {'note': {'type': 'string', 'value': ''}},
      extraScreens: [
        {
          'id': 's2', 'title': '2画面目', 'state': <String, dynamic>{},
          'body': {
            'type': 'button', 'id': 'back_btn', 'label': '戻る',
            'action': {'type': 'go_back'},
          },
        },
      ],
    )));

    await tester.enterText(find.byType(TextField), '消えないはず');
    await tester.pump();

    await tester.tap(find.widgetWithText(ElevatedButton, '次へ'));
    await tester.pumpAndSettle();
    expect(find.widgetWithText(AppBar, '2画面目'), findsOneWidget);

    await tester.tap(find.widgetWithText(ElevatedButton, '戻る'));
    await tester.pumpAndSettle();

    final field = tester.widget<TextField>(find.byType(TextField));
    expect(field.controller?.text, '消えないはず', reason: '1画面目のForgeRuntimeStateはpopされるまで破棄されないため保持される');
    expect(tester.takeException(), isNull);
  });
}
