// v1.9 集計付きbar_chartのWidget Test
// (FORGE-USER-GUIDED-SELF-EXTENSION-006 Phase 4、2026-08-13新設)。
//
// **このファイルが証明すること**
//
// ロードマップPhase 4 / 指示書§56の基準は
// 「表現 → 検証 → コンパイル → **描画** → 使用」である。
// 単体テスト(`forge_aggregate_test.dart`)は集計の正しさを示すが、
// **実際に画面へ出ること**は示さない。ここでRuntimeを通して描画する。
//
// 併せて、TD37と同じ形の事故(Validator・Runtime・Registryの不一致で
// 一度も描画されない)が起きていないことも確認する。

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:forge_app/core/theme/forge_theme.dart';
import 'package:forge_app/json_ui/renderer/forge_renderer.dart';

Widget _wrap(Map<String, dynamic> doc) =>
    MaterialApp(theme: ForgeTheme.theme, home: ForgeDocumentView(rawJson: doc));

/// 釣果3件(堤防2・磯1)。「よく釣れる場所を知りたい」という、
/// §33の困りごとにそのまま対応する。
List<Map<String, dynamic>> _catchRecords() => [
      {'id': 'r1', 'fields': {'place': '堤防', 'size': 25}},
      {'id': 'r2', 'fields': {'place': '磯', 'size': 40}},
      {'id': 'r3', 'fields': {'place': '堤防', 'size': 15}},
    ];

Map<String, dynamic> _doc({
  String? groupBy,
  String? aggregate,
  String? valueField,
  String? labelField,
}) {
  final chart = <String, dynamic>{
    'type': 'bar_chart',
    'id': 'chart1',
    'state_ref': 'records',
    'title': '場所ごと',
  };
  if (groupBy != null) chart['group_by'] = groupBy;
  if (aggregate != null) chart['aggregate'] = aggregate;
  if (valueField != null) chart['value_field'] = valueField;
  if (labelField != null) chart['label_field'] = labelField;

  return {
    'version': '1.9',
    'initial_screen_id': 's1',
    'record_schemas': {
      'catch': {
        'fields': [
          {'name': 'place', 'type': 'string', 'label': '場所', 'required': true},
          {'name': 'size', 'type': 'number', 'label': 'サイズ', 'required': true},
        ],
      },
    },
    'screens': [
      {
        'id': 's1',
        'title': '釣果',
        'state': {
          'records': {
            'type': 'record_list',
            'value': _catchRecords(),
            'schema_ref': 'catch',
          },
        },
        'body': {
          'type': 'column',
          'id': 'root',
          'children': [chart],
        },
      },
    ],
  };
}

void main() {
  testWidgets('集計あり: グループごとに1本の棒が描かれる', (tester) async {
    await tester.pumpWidget(_wrap(_doc(groupBy: 'place', aggregate: 'count')));
    await tester.pumpAndSettle();

    // グループ化キーがそのままラベルになる。
    expect(find.text('堤防'), findsOneWidget);
    expect(find.text('磯'), findsOneWidget);
    expect(tester.takeException(), isNull);
  });

  testWidgets('集計なし(従来動作)は一切変わらない', (tester) async {
    // v1.9はproperty-onlyの追加である。`group_by`が無ければ、
    // 以前と同じ「1 Record = 1本」で描かれなければならない。
    await tester.pumpWidget(
      _wrap(_doc(valueField: 'size', labelField: 'place')),
    );
    await tester.pumpAndSettle();

    // 3件それぞれが棒になるため、「堤防」は2回現れる。
    expect(find.text('堤防'), findsNWidgets(2));
    expect(find.text('磯'), findsOneWidget);
    expect(tester.takeException(), isNull);
  });

  testWidgets('sum集計: 場所ごとの合計で描画される', (tester) async {
    await tester.pumpWidget(
      _wrap(_doc(groupBy: 'place', aggregate: 'sum', valueField: 'size')),
    );
    await tester.pumpAndSettle();

    expect(find.text('堤防'), findsOneWidget, reason: '合計なので堤防は1本にまとまる');
    expect(find.text('磯'), findsOneWidget);
    expect(tester.takeException(), isNull);
  });

  testWidgets('countはvalue_field無しで描画できる', (tester) async {
    // 数えるだけなので値Fieldは不要。ここが必須のままだと、
    // Compilerが意味の無いFieldを埋めることになる。
    await tester.pumpWidget(_wrap(_doc(groupBy: 'place', aggregate: 'count')));
    await tester.pumpAndSettle();

    expect(find.text('堤防'), findsOneWidget);
    expect(tester.takeException(), isNull);
  });

  testWidgets('aggregate省略時はcountとして描画される', (tester) async {
    await tester.pumpWidget(_wrap(_doc(groupBy: 'place')));
    await tester.pumpAndSettle();

    expect(find.text('堤防'), findsOneWidget);
    expect(tester.takeException(), isNull);
  });

  testWidgets('Recordが空でもクラッシュしない', (tester) async {
    final doc = _doc(groupBy: 'place', aggregate: 'count');
    (doc['screens'] as List).first['state']['records']['value'] = <dynamic>[];
    await tester.pumpWidget(_wrap(doc));
    await tester.pumpAndSettle();

    expect(tester.takeException(), isNull);
  });

  testWidgets('未知のaggregate値は描画時に落ちない', (tester) async {
    // Validatorが弾くはずだが、Runtimeは壊れた文書でも落ちない方が良い
    // (他のWidgetと同じ多重防御の方針)。
    await tester.pumpWidget(_wrap(_doc(groupBy: 'place', aggregate: 'median')));
    await tester.pumpAndSettle();

    // Fallback表示になるだけで、例外は出ない。
    expect(tester.takeException(), isNull);
  });
}
