// TRANSFORM Primitive「グループごとの集計」のテスト
// (FORGE-USER-GUIDED-SELF-EXTENSION-006 Phase 4、2026-08-13新設)。
//
// この関数は**Widgetではない**ため、Widget Testではなく純粋な単体テストで
// 検証する。それ自体が「TRANSFORMはVIEWとは別の層である」という設計が
// 実体を伴っていることの証拠でもある。

import 'package:flutter_test/flutter_test.dart';
import 'package:forge_app/json_ui/runtime/forge_aggregate.dart';
import 'package:forge_app/json_ui/schema/forge_document.dart';

ForgeRecordItem _record(String id, Map<String, dynamic> fields) =>
    ForgeRecordItem(id: id, fields: fields);

/// 釣果3件。堤防2件・磯1件。
final _catches = <ForgeRecordItem>[
  _record('r1', {'place': '堤防', 'size': 25}),
  _record('r2', {'place': '磯', 'size': 40}),
  _record('r3', {'place': '堤防', 'size': 15}),
];

void main() {
  group('count', () {
    test('場所ごとの件数を数える', () {
      final groups = aggregateRecords(
        _catches, groupBy: 'place', op: ForgeAggregateOp.count,
      );
      expect(groups.map((g) => g.label).toList(), ['堤防', '磯']);
      expect(groups.map((g) => g.value).toList(), [2.0, 1.0]);
    });

    test('countはvalueFieldを必要としない', () {
      // 数えるだけなので値Fieldは要らない。ここを必須にすると、
      // Compilerが意味の無いFieldを埋めることになる。
      final groups = aggregateRecords(
        _catches, groupBy: 'place', op: ForgeAggregateOp.count,
      );
      expect(groups, isNotEmpty);
    });
  });

  group('sum / average', () {
    test('場所ごとの合計', () {
      final groups = aggregateRecords(
        _catches, groupBy: 'place', op: ForgeAggregateOp.sum, valueField: 'size',
      );
      expect(groups.firstWhere((g) => g.label == '堤防').value, 40.0);
      expect(groups.firstWhere((g) => g.label == '磯').value, 40.0);
    });

    test('場所ごとの平均', () {
      final groups = aggregateRecords(
        _catches, groupBy: 'place', op: ForgeAggregateOp.average, valueField: 'size',
      );
      expect(groups.firstWhere((g) => g.label == '堤防').value, 20.0);
      expect(groups.firstWhere((g) => g.label == '堤防').recordCount, 2);
    });

    test('valueFieldが無いsum/averageは何も集計しない(例外にしない)', () {
      expect(
        aggregateRecords(_catches, groupBy: 'place', op: ForgeAggregateOp.sum),
        isEmpty,
      );
    });
  });

  group('壊れた入力でも落ちない', () {
    test('groupByのFieldが無いRecordは静かに無視される', () {
      final records = [..._catches, _record('r4', {'size': 10})];
      final groups = aggregateRecords(
        records, groupBy: 'place', op: ForgeAggregateOp.count,
      );
      expect(groups.length, 2, reason: 'place を持たない1件が混ざってはいけない');
    });

    test('数値でない値はsumから除外される', () {
      final records = [..._catches, _record('r5', {'place': '堤防', 'size': 'たくさん'})];
      final groups = aggregateRecords(
        records, groupBy: 'place', op: ForgeAggregateOp.sum, valueField: 'size',
      );
      expect(groups.firstWhere((g) => g.label == '堤防').value, 40.0);
    });

    test('空のRecordリストは空を返す', () {
      expect(
        aggregateRecords(const [], groupBy: 'place', op: ForgeAggregateOp.count),
        isEmpty,
      );
    });

    test('groupByが空文字なら何もしない', () {
      expect(
        aggregateRecords(_catches, groupBy: '', op: ForgeAggregateOp.count),
        isEmpty,
      );
    });
  });

  group('決定的であること', () {
    test('同じ入力なら常に同じ順序・同じ値', () {
      List<String> run() => aggregateRecords(
            _catches, groupBy: 'place', op: ForgeAggregateOp.count,
          ).map((g) => '${g.label}:${g.value}').toList();
      expect(run(), run());
    });

    test('並び順は最初に出現したグループ順(並べ替えはしない)', () {
      // 並べ替えは`transform.sort`という別のPrimitiveの仕事である。
      // ここで件数降順にすると、2つの関心が混ざる。
      final groups = aggregateRecords(
        _catches, groupBy: 'place', op: ForgeAggregateOp.count,
      );
      expect(groups.first.label, '堤防', reason: '出現順が保たれていない');
    });

    test('入力のRecordリストを変更しない', () {
      final before = _catches.map((r) => Map<String, dynamic>.from(r.fields)).toList();
      aggregateRecords(_catches, groupBy: 'place', op: ForgeAggregateOp.sum, valueField: 'size');
      for (var i = 0; i < _catches.length; i++) {
        expect(_catches[i].fields, before[i]);
      }
    });
  });

  group('ForgeAggregateOp.fromJson', () {
    test('既知の値を解釈する', () {
      expect(ForgeAggregateOp.fromJson('count'), ForgeAggregateOp.count);
      expect(ForgeAggregateOp.fromJson('sum'), ForgeAggregateOp.sum);
      expect(ForgeAggregateOp.fromJson('average'), ForgeAggregateOp.average);
    });

    test('未知の値はnull(勝手に既定へ倒さない)', () {
      // 黙ってcountへ倒すと、書き間違いが検出されないまま動いてしまう。
      expect(ForgeAggregateOp.fromJson('median'), isNull);
      expect(ForgeAggregateOp.fromJson(null), isNull);
    });
  });
}
