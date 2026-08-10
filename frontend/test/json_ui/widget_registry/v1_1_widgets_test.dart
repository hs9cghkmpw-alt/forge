// v1.1新規Widget(heading/checkbox/card/list/divider/form)のWidget Test
// (FORGE-MILESTONE-002 PHASE9)。
//
// 注記: Claudeのサンドボックスに Dart SDK が無いため、このファイルは
// 一度も `flutter test` で実行されていない。CEO環境での実行が必須。

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:forge_app/core/theme/forge_theme.dart';
import 'package:forge_app/json_ui/renderer/forge_renderer.dart';

Map<String, dynamic> _screenDoc(Map<String, dynamic> body, {Map<String, dynamic>? state}) {
  return {
    'version': '1.1',
    'initial_screen_id': 's1',
    'screens': [
      {'id': 's1', 'title': 'テスト画面', 'state': state ?? <String, dynamic>{}, 'body': body},
    ],
  };
}

Widget _wrap(Map<String, dynamic> doc) {
  return MaterialApp(theme: ForgeTheme.theme, home: ForgeDocumentView(rawJson: doc));
}

void main() {
  testWidgets('heading: value が表示される', (tester) async {
    final doc = _screenDoc({'type': 'heading', 'id': 'h1', 'value': '見出しテスト', 'level': 1});
    await tester.pumpWidget(_wrap(doc));
    await tester.pumpAndSettle();
    expect(find.text('見出しテスト'), findsOneWidget);
    expect(tester.takeException(), isNull);
  });

  testWidgets('divider: 例外なく描画される', (tester) async {
    final doc = _screenDoc({
      'type': 'column', 'id': 'col1',
      'children': [
        {'type': 'text', 'id': 't1', 'value': '上'},
        {'type': 'divider', 'id': 'd1'},
        {'type': 'text', 'id': 't2', 'value': '下'},
      ],
    });
    await tester.pumpWidget(_wrap(doc));
    await tester.pumpAndSettle();
    expect(find.byType(Divider), findsOneWidget);
    expect(tester.takeException(), isNull);
  });

  testWidgets('checkbox: タップで状態が変わりCheckboxListTileが反映する', (tester) async {
    final doc = _screenDoc(
      {'type': 'checkbox', 'id': 'c1', 'label': '同意する', 'state_ref': 'agreed'},
      state: {
        'agreed': {'type': 'boolean', 'value': false},
      },
    );
    await tester.pumpWidget(_wrap(doc));
    await tester.pumpAndSettle();

    expect(find.text('同意する'), findsOneWidget);
    final tileBefore = tester.widget<CheckboxListTile>(find.byType(CheckboxListTile));
    expect(tileBefore.value, isFalse);

    await tester.tap(find.byType(CheckboxListTile));
    await tester.pump();

    final tileAfter = tester.widget<CheckboxListTile>(find.byType(CheckboxListTile));
    expect(tileAfter.value, isTrue);
    expect(tester.takeException(), isNull);
  });

  testWidgets('list: string_list stateの内容が表示される', (tester) async {
    final doc = _screenDoc(
      {'type': 'list', 'id': 'l1', 'state_ref': 'tags'},
      state: {
        'tags': {
          'type': 'string_list',
          'value': ['緊急', '重要', '後で'],
        },
      },
    );
    await tester.pumpWidget(_wrap(doc));
    await tester.pumpAndSettle();
    expect(find.textContaining('緊急'), findsOneWidget);
    expect(find.textContaining('重要'), findsOneWidget);
    expect(find.textContaining('後で'), findsOneWidget);
    expect(tester.takeException(), isNull);
  });

  testWidgets('list: 空の場合はempty_state_textが表示される', (tester) async {
    final doc = _screenDoc(
      {'type': 'list', 'id': 'l1', 'state_ref': 'tags', 'empty_state_text': '何もありません'},
      state: {
        'tags': {'type': 'string_list', 'value': <String>[]},
      },
    );
    await tester.pumpWidget(_wrap(doc));
    await tester.pumpAndSettle();
    expect(find.text('何もありません'), findsOneWidget);
    expect(tester.takeException(), isNull);
  });

  testWidgets('card: 内部のWidgetを描画し、Card Widgetで囲む', (tester) async {
    final doc = _screenDoc({
      'type': 'card', 'id': 'card1',
      'children': [
        {'type': 'heading', 'id': 'h1', 'value': 'カード見出し', 'level': 2},
        {'type': 'text', 'id': 't1', 'value': 'カード本文'},
      ],
    });
    await tester.pumpWidget(_wrap(doc));
    await tester.pumpAndSettle();
    expect(find.byType(Card), findsOneWidget);
    expect(find.text('カード見出し'), findsOneWidget);
    expect(find.text('カード本文'), findsOneWidget);
    expect(tester.takeException(), isNull);
  });

  testWidgets('form: children + submit buttonが描画され、submitで例外が出ない', (tester) async {
    final doc = _screenDoc(
      {
        'type': 'form', 'id': 'form1', 'submit_label': '送信する',
        'children': [
          {'type': 'text_field', 'id': 'tf1', 'state_ref': 'note'},
        ],
        'submit_action': {'type': 'go_back'},
      },
      state: {
        'note': {'type': 'string', 'value': ''},
      },
    );
    await tester.pumpWidget(_wrap(doc));
    await tester.pumpAndSettle();
    expect(find.widgetWithText(ElevatedButton, '送信する'), findsOneWidget);
    // go_backは戻る画面が無い(このテストではpushしていない)ため、
    // Navigator.maybePop()が「何もしない」を選ぶだけで例外にはならないはず。
    await tester.tap(find.widgetWithText(ElevatedButton, '送信する'));
    await tester.pump();
    expect(tester.takeException(), isNull);
  });

  testWidgets('12種類のWidgetを1画面に混在させても例外なく描画される', (tester) async {
    final doc = _screenDoc(
      {
        'type': 'column', 'id': 'root',
        'children': [
          {'type': 'heading', 'id': 'h1', 'value': 'タイトル', 'level': 1},
          {'type': 'text', 'id': 't1', 'value': '本文'},
          {'type': 'divider', 'id': 'd1'},
          {
            'type': 'card', 'id': 'card1',
            'children': [
              {'type': 'list', 'id': 'l1', 'state_ref': 'tags'},
            ],
          },
          {'type': 'checklist', 'id': 'cl1', 'state_ref': 'items'},
          {'type': 'checkbox', 'id': 'cb1', 'label': '同意', 'state_ref': 'agreed'},
          {
            'type': 'row', 'id': 'r1',
            'children': [
              {'type': 'text_field', 'id': 'tf1', 'state_ref': 'note'},
              {
                'type': 'button', 'id': 'b1', 'label': 'OK',
                'action': {'type': 'go_back'},
              },
            ],
          },
        ],
      },
      state: {
        'tags': {
          'type': 'string_list',
          'value': ['a'],
        },
        'items': {
          'type': 'checklist',
          'value': [
            {'id': 'i1', 'text': 'x', 'done': false},
          ],
        },
        'agreed': {'type': 'boolean', 'value': false},
        'note': {'type': 'string', 'value': ''},
      },
    );
    await tester.pumpWidget(_wrap(doc));
    await tester.pumpAndSettle();
    expect(tester.takeException(), isNull);
  });
}
