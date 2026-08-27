// Quality Gate v2 Round 5（020A2 §7）で**実際に見えた**もの。
//
// `bar_chart` は記録が無いとき `SizedBox.shrink()` を返していた。
// ところが `style_role: card.summary` の見た目は `applyForgeRole()` が
// **外側から**被せるので、中身が空でも card の padding だけが残り、
// 一覧の空表示のすぐ下に**文字の無い灰色の箱**が描かれていた。
//
// 「撮って、開いて、見る」で見つけた——静的なテストは全部通っていた。
// 見つけた以上、次に戻ったら落ちる形にする。

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:forge_app/core/theme/forge_theme.dart';
import 'package:forge_app/json_ui/renderer/forge_renderer.dart';

Map<String, dynamic> _docWithEmptyChart() => {
      'version': '1.7',
      'initial_screen_id': 's1',
      'record_schemas': {
        'sale': {
          'fields': [
            {'name': 'department', 'type': 'text', 'label': '部署', 'required': true},
            {'name': 'amount', 'type': 'number', 'label': '金額', 'required': true},
          ],
        },
      },
      'screens': [
        {
          'id': 's1',
          'title': '売上記録',
          'state': {
            'records': {'type': 'record_list', 'value': <dynamic>[], 'schema_ref': 'sale'},
          },
          'body': {
            'type': 'column',
            'id': 'c1',
            'children': [
              {
                'type': 'bar_chart',
                'id': 'bc1',
                'style_role': 'card.summary',
                'state_ref': 'records',
                'value_field': 'amount',
                'label_field': 'department',
                'title': '売上記録の金額',
              },
            ],
          },
        },
      ],
    };

void main() {
  testWidgets('記録が無いグラフは、無言の箱ではなく理由を出す', (tester) async {
    await tester.pumpWidget(
      MaterialApp(theme: ForgeTheme.theme, home: ForgeDocumentView(rawJson: _docWithEmptyChart())),
    );
    await tester.pumpAndSettle();

    // **見出しが残る。** どの箱なのか分からないまま置かれるのが問題だった。
    expect(find.text('売上記録の金額'), findsOneWidget);
    // **なぜ空なのかを言う。**
    expect(find.text('グラフに出せる記録がまだありません'), findsOneWidget);
  });

  testWidgets('記録があるときは、その説明を出さない', (tester) async {
    final doc = _docWithEmptyChart();
    final screen = (doc['screens'] as List).first as Map<String, dynamic>;
    ((screen['state'] as Map)['records'] as Map)['value'] = <dynamic>[
      {'id': 'r1', 'fields': {'department': '営業', 'amount': 120}},
    ];

    await tester.pumpWidget(
      MaterialApp(theme: ForgeTheme.theme, home: ForgeDocumentView(rawJson: doc)),
    );
    await tester.pumpAndSettle();

    expect(find.text('売上記録の金額'), findsOneWidget);
    expect(find.text('グラフに出せる記録がまだありません'), findsNothing);
    expect(find.text('営業'), findsOneWidget);
  });
}
