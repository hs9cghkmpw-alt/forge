// Widget Vocabulary Expansion(v1.8、2026-08-11)のWidget Test。
//
// FORGE-AI-QUALITY-001。CEO「要は、一気に検証を進めたい。なので、
// 壊れてる?って機能でもどんどん追加してくれ。あとでなおす。」への
// 対応。`slider`(範囲指定の数値入力)を実際に`ForgeDocumentView`経由で
// 描画し、ドラッグ操作・Recordへの反映まで検証する
// (`v1_6_v1_7_widget_vocabulary_expansion_test.dart`と同じ方針、
// TD37の教訓——`typeNameOf()`への追加を忘れると非網羅switchの
// コンパイルエラーになる——を踏まえ、このテスト自体がそれを検出できる)。

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:forge_app/core/theme/forge_theme.dart';
import 'package:forge_app/json_ui/renderer/forge_renderer.dart';

Widget _wrap(Map<String, dynamic> doc) {
  return MaterialApp(theme: ForgeTheme.theme, home: ForgeDocumentView(rawJson: doc));
}

/// `ForgeLanguageCompiler`(v1.8)が実際に生成する reading_log 相当の
/// 文書を模した、tab_view + text_field + slider を含む文書。
Map<String, dynamic> _readingLogDoc() {
  return {
    'version': '1.8',
    'initial_screen_id': 's1',
    'record_schemas': {
      'book': {
        'fields': [
          {'name': 'title', 'type': 'string', 'label': 'タイトル', 'required': true},
          {'name': 'rating', 'type': 'number', 'label': '評価(5段階)', 'required': false},
        ],
      },
    },
    'screens': [
      {
        'id': 's1', 'title': '読書ログ',
        'state': {
          'records': {'type': 'record_list', 'value': <dynamic>[], 'schema_ref': 'book'},
          'field_title': {'type': 'string', 'value': ''},
          'field_rating': {'type': 'number', 'value': 1},
        },
        'body': {
          'type': 'tab_view', 'id': 'root_tabs',
          'tab_titles': ['本を追加', '本の一覧'],
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
                        'field_bindings': {'title': 'field_title', 'rating': 'field_rating'},
                      },
                      {'type': 'reset_state', 'state_ref': 'field_title'},
                      {'type': 'reset_state', 'state_ref': 'field_rating'},
                    ],
                  },
                  'children': [
                    {'type': 'text_field', 'id': 'tf1', 'state_ref': 'field_title', 'placeholder': 'タイトル'},
                    {'type': 'slider', 'id': 'sl1', 'label': '評価(5段階)', 'state_ref': 'field_rating', 'min': 1, 'max': 5},
                  ],
                },
              ],
            },
            {
              'type': 'column', 'id': 'list_tab',
              'children': [
                {
                  'type': 'record_list_view', 'id': 'rlv1', 'state_ref': 'records',
                  'display_fields': ['title', 'rating'], 'empty_state_text': 'まだ記録がありません',
                },
              ],
            },
          ],
        },
      },
    ],
  };
}

void main() {
  group('slider', () {
    testWidgets('labelと初期値(min)が表示される(未操作でもクラッシュしない)', (tester) async {
      await tester.pumpWidget(_wrap(_readingLogDoc()));
      await tester.pumpAndSettle();

      expect(find.byType(Slider), findsOneWidget);
      expect(find.text('評価(5段階)'), findsOneWidget);
      expect(find.text('1'), findsOneWidget);
      expect(tester.takeException(), isNull);
    });

    testWidgets('右端までドラッグするとmaxの値が表示される', (tester) async {
      await tester.pumpWidget(_wrap(_readingLogDoc()));
      await tester.pumpAndSettle();

      // 十分大きなoffsetでドラッグし、確実に右端(max)まで動かす。
      await tester.drag(find.byType(Slider), const Offset(1000, 0));
      await tester.pumpAndSettle();

      expect(find.text('5'), findsOneWidget);
      expect(tester.takeException(), isNull);
    });

    testWidgets('左端までドラッグするとminの値が表示される(右端から戻す)', (tester) async {
      await tester.pumpWidget(_wrap(_readingLogDoc()));
      await tester.pumpAndSettle();

      await tester.drag(find.byType(Slider), const Offset(1000, 0));
      await tester.pumpAndSettle();
      expect(find.text('5'), findsOneWidget);

      await tester.drag(find.byType(Slider), const Offset(-1000, 0));
      await tester.pumpAndSettle();
      expect(find.text('1'), findsOneWidget);
      expect(tester.takeException(), isNull);
    });
  });

  group('Integration: reading_logの一連の流れ', () {
    testWidgets(
      'タイトルを入力・評価をmaxまでドラッグ -> 保存 -> 一覧タブでRecordを確認',
      (tester) async {
        await tester.pumpWidget(_wrap(_readingLogDoc()));
        await tester.pumpAndSettle();

        await tester.enterText(find.byType(TextField), '銀河ヒッチハイク・ガイド');
        await tester.drag(find.byType(Slider), const Offset(1000, 0));
        await tester.pumpAndSettle();

        await tester.tap(find.widgetWithText(ElevatedButton, '保存'));
        await tester.pumpAndSettle();

        await tester.tap(find.text('本の一覧'));
        await tester.pumpAndSettle();

        expect(find.text('まだ記録がありません'), findsNothing);
        expect(find.textContaining('銀河ヒッチハイク・ガイド'), findsWidgets);
        // ForgeRecordValidator.validate()が値を.toString()経由で
        // 一度文字列化してから再parseするため、整数値でも末尾に
        // ".0"が付いて表示される既知の見た目上の未解決課題
        // (TECH_DEBT.md TD38参照。「あとでなおす」の対象として
        // CEOから明示的に許可を得ている)。
        expect(find.textContaining('5.0'), findsWidgets);
        expect(tester.takeException(), isNull);
      },
    );
  });
}
