// TRANSFORM Primitive「1つの数値へ畳む集計」(`aggregateAll`)のテスト
// (FORGE-R1、TD69、2026-08-17新設)。
//
// `aggregateRecords`(グループごと)と同じく、これは**Widgetではない**
// ので純粋な単体テストで検証する。`metric_view`はこの関数の利用者に
// すぎず、所有者ではない。

import 'package:flutter_test/flutter_test.dart';
import 'package:forge_app/json_ui/runtime/forge_aggregate.dart';
import 'package:forge_app/json_ui/schema/forge_document.dart';

ForgeRecordItem _record(String id, Map<String, dynamic> fields) =>
    ForgeRecordItem(id: id, fields: fields);

final _expenses = <ForgeRecordItem>[
  _record('r1', {'category': '食費', 'amount': 1200}),
  _record('r2', {'category': '交通費', 'amount': 480}),
  _record('r3', {'category': '食費', 'amount': 10500}),
];

void main() {
  group('sum / average / count', () {
    test('合計', () {
      expect(
        aggregateAll(_expenses, op: ForgeAggregateOp.sum, valueField: 'amount'),
        12180.0,
      );
    });

    test('平均', () {
      expect(
        aggregateAll(_expenses, op: ForgeAggregateOp.average, valueField: 'amount'),
        4060.0,
      );
    });

    test('件数はvalueFieldを必要としない', () {
      expect(aggregateAll(_expenses, op: ForgeAggregateOp.count), 3.0);
    });
  });

  group('0件のとき', () {
    test('sumはnullを返す(0ではない)', () {
      // **「合計0」と「記録が無い」を区別できなくしない。** 0を返すと
      // 呼び出し側がその区別を復元できず、「0円使った」と表示される。
      expect(
        aggregateAll(const [], op: ForgeAggregateOp.sum, valueField: 'amount'),
        isNull,
      );
    });

    test('averageもnullを返す', () {
      expect(
        aggregateAll(const [], op: ForgeAggregateOp.average, valueField: 'amount'),
        isNull,
      );
    });

    test('countは0を返す', () {
      // 「0件である」は正しく数えた結果であって、欠落ではない。
      expect(aggregateAll(const [], op: ForgeAggregateOp.count), 0.0);
    });
  });

  group('壊れた入力', () {
    test('数値でないFieldは無視される', () {
      final mixed = [
        _record('r1', {'amount': 'たくさん'}),
        _record('r2', {'amount': 500}),
      ];
      expect(
        aggregateAll(mixed, op: ForgeAggregateOp.sum, valueField: 'amount'),
        500.0,
      );
    });

    test('全件が数値でなければnull(0ではない)', () {
      final broken = [_record('r1', {'amount': 'たくさん'})];
      expect(
        aggregateAll(broken, op: ForgeAggregateOp.sum, valueField: 'amount'),
        isNull,
      );
    });

    test('sumにvalueFieldが無ければnull(0ではない)', () {
      expect(aggregateAll(_expenses, op: ForgeAggregateOp.sum), isNull);
    });
  });
}
