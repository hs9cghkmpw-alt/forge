// v1.11 Hero KPI (`metric_view`) のWidget Test
// (FORGE-R1-ENTRY-AND-DESIGN-LANGUAGE-014、TD69、2026-08-17新設)。
//
// **このファイルが証明すること**
//
// v1.10でDesign Languageへ`metric.primary`(画面で最も重要な単一のKPI)
// を入れたとき、**その役割を持てるWidgetが1つも無かった**。ここでは
// 「Runtimeを通して実際に画面へ出る」ところまでを確認する——
// Validator・Schema・Registryのどれか1つでも欠けると落ちる
// (TD37と同じ形の事故: 3つの不一致で一度も描画されない)。

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:forge_app/core/theme/forge_theme.dart';
import 'package:forge_app/json_ui/renderer/forge_renderer.dart';
import 'package:forge_app/json_ui/widget_registry/widget_registry.dart';

Widget _wrap(Map<String, dynamic> doc) =>
    MaterialApp(theme: ForgeTheme.theme, home: ForgeDocumentView(rawJson: doc));

/// 家計の支出3件。「今月いくら使ったか」という、Golden Finance が
/// 答えなければならない問いにそのまま対応する。
List<Map<String, dynamic>> _expenseRecords() => [
      {'id': 'r1', 'fields': {'category': '食費', 'amount': 1200}},
      {'id': 'r2', 'fields': {'category': '交通費', 'amount': 480}},
      {'id': 'r3', 'fields': {'category': '食費', 'amount': 10500}},
    ];

Map<String, dynamic> _doc({
  String? aggregate = 'sum',
  String? valueField = 'amount',
  String? label = '支出の合計',
  String? unit = '円',
  String? emptyText,
  String? styleRole = 'metric.primary',
  List<Map<String, dynamic>>? records,
}) {
  final metric = <String, dynamic>{
    'type': 'metric_view',
    'id': 'hero',
    'state_ref': 'records',
  };
  if (aggregate != null) metric['aggregate'] = aggregate;
  if (valueField != null) metric['value_field'] = valueField;
  if (label != null) metric['label'] = label;
  if (unit != null) metric['unit'] = unit;
  if (emptyText != null) metric['empty_text'] = emptyText;
  if (styleRole != null) metric['style_role'] = styleRole;

  return {
    'version': '1.11',
    'initial_screen_id': 's1',
    'record_schemas': {
      'expense': {
        'fields': [
          {'name': 'category', 'type': 'string', 'label': 'カテゴリ', 'required': true},
          {'name': 'amount', 'type': 'number', 'label': '金額', 'required': true},
        ],
      },
    },
    'screens': [
      {
        'id': 's1',
        'title': '家計簿',
        'state': {
          'records': {
            'type': 'record_list',
            'value': records ?? _expenseRecords(),
            'schema_ref': 'expense',
          },
        },
        'body': {
          'type': 'column',
          'id': 'root',
          'children': [metric],
        },
      },
    ],
  };
}

void main() {
  group('描画', () {
    testWidgets('合計が画面に出る', (tester) async {
      await tester.pumpWidget(_wrap(_doc()));
      await tester.pumpAndSettle();

      // 1200 + 480 + 10500 = 12180。**桁区切りが入る** — 主KPIは
      // 桁を読み違えると意味が反転するため。
      expect(find.text('12,180'), findsOneWidget);
      expect(find.text('支出の合計'), findsOneWidget);
      expect(find.text('円'), findsOneWidget);
      expect(tester.takeException(), isNull);
    });

    testWidgets('平均も出せる', (tester) async {
      await tester.pumpWidget(_wrap(_doc(aggregate: 'average')));
      await tester.pumpAndSettle();
      expect(find.text('4,060'), findsOneWidget);
    });

    testWidgets('件数はvalue_fieldなしで出せる', (tester) async {
      await tester.pumpWidget(
        _wrap(_doc(aggregate: 'count', valueField: null, unit: '件')),
      );
      await tester.pumpAndSettle();
      expect(find.text('3'), findsOneWidget);
    });

    testWidgets('Registryにmetric_viewが登録されている', (tester) async {
      // TD37と同じ形の事故(Validatorは通るのにRegistryに無く、一度も
      // 描画されない)を、Registry側からも押さえる。
      expect(buildDefaultForgeRegistry().registeredTypes, contains('metric_view'));
    });
  });

  group('記録が無いとき', () {
    testWidgets('0とは書かない', (tester) async {
      // **「合計0円」と「まだ記録が無い」は違う。** 0と出すと
      // 「今月は0円使った」という、事実でない読み取りを招く。
      await tester.pumpWidget(
        _wrap(_doc(records: const [], emptyText: 'まだ記録がありません')),
      );
      await tester.pumpAndSettle();

      expect(find.text('まだ記録がありません'), findsOneWidget);
      expect(find.text('0'), findsNothing);
      expect(tester.takeException(), isNull);
    });

    testWidgets('件数だけは0件と出る', (tester) async {
      // 「0件である」は正しく数えた結果であって、欠落ではない。
      await tester.pumpWidget(
        _wrap(_doc(records: const [], aggregate: 'count', valueField: null)),
      );
      await tester.pumpAndSettle();
      expect(find.text('0'), findsOneWidget);
    });
  });

  group('壊れた文書でも落ちない', () {
    testWidgets('数値でないFieldは静かに無視される', (tester) async {
      await tester.pumpWidget(_wrap(_doc(records: [
        {'id': 'r1', 'fields': {'category': '食費', 'amount': 'たくさん'}},
        {'id': 'r2', 'fields': {'category': '食費', 'amount': 500}},
      ])));
      await tester.pumpAndSettle();

      expect(find.text('500'), findsOneWidget);
      expect(tester.takeException(), isNull);
    });

    testWidgets('存在しないFieldを指しても画面が落ちない', (tester) async {
      await tester.pumpWidget(
        _wrap(_doc(valueField: 'nonexistent', emptyText: '—')),
      );
      await tester.pumpAndSettle();
      expect(tester.takeException(), isNull);
    });
  });
}
