// ForgeStateValue.toJson() / mergePersistedState() Unit Test
// (FORGE-AI-QUALITY-001、2026-08-11、ローカル永続化対応)。
//
// `AI生成アプリの状態はアプリ再起動で消える`(KNOWN_ISSUES.md)への対応の
// 一部。`toJson()`が`fromJson()`と厳密に対称であること(round-trip)、
// および`mergePersistedState()`が「宣言された初期Stateへ、保存済みの
// 実行時Stateを安全にマージする(壊れたデータでクラッシュしない)」を
// 検証する。
//
// 注記: Claudeのサンドボックスに Dart SDK が無いため、このファイルは
// 一度も `flutter test` で実行されていない。CEO環境での実行が必須。

import 'package:flutter_test/flutter_test.dart';
import 'package:forge_app/json_ui/schema/forge_document.dart';

void main() {
  group('ForgeStateValue.toJson() round-trip', () {
    test('ForgeStringState', () {
      const original = ForgeStringState('こんにちは');
      final restored = ForgeStateValue.fromJson(original.toJson(), '/x') as ForgeStringState;
      expect(restored.value, 'こんにちは');
    });

    test('ForgeBooleanState', () {
      const original = ForgeBooleanState(true);
      final restored = ForgeStateValue.fromJson(original.toJson(), '/x') as ForgeBooleanState;
      expect(restored.value, isTrue);
    });

    test('ForgeNumberState', () {
      const original = ForgeNumberState(42.5);
      final restored = ForgeStateValue.fromJson(original.toJson(), '/x') as ForgeNumberState;
      expect(restored.value, 42.5);
    });

    test('ForgeStringListState', () {
      const original = ForgeStringListState(['a', 'b', 'c']);
      final restored = ForgeStateValue.fromJson(original.toJson(), '/x') as ForgeStringListState;
      expect(restored.value, ['a', 'b', 'c']);
    });

    test('ForgeChecklistState', () {
      const original = ForgeChecklistState([
        ForgeChecklistItem(id: 'item_1', text: '牛乳', done: false),
        ForgeChecklistItem(id: 'item_2', text: '卵', done: true),
      ]);
      final restored = ForgeStateValue.fromJson(original.toJson(), '/x') as ForgeChecklistState;
      expect(restored.value.length, 2);
      expect(restored.value[0].id, 'item_1');
      expect(restored.value[0].text, '牛乳');
      expect(restored.value[0].done, isFalse);
      expect(restored.value[1].done, isTrue);
    });

    test('ForgeRecordListState(schemaRefあり)', () {
      const original = ForgeRecordListState(
        [
          ForgeRecordItem(id: 'r1', fields: {'amount': 500, 'category': '食費'}),
        ],
        schemaRef: 'transaction_schema',
      );
      final restored = ForgeStateValue.fromJson(original.toJson(), '/x') as ForgeRecordListState;
      expect(restored.schemaRef, 'transaction_schema');
      expect(restored.value.single.id, 'r1');
      expect(restored.value.single.fields['category'], '食費');
    });

    test('ForgeRecordListState(schemaRef無し)', () {
      const original = ForgeRecordListState([]);
      final json = original.toJson();
      expect(json.containsKey('schema_ref'), isFalse);
      final restored = ForgeStateValue.fromJson(json, '/x') as ForgeRecordListState;
      expect(restored.schemaRef, isNull);
      expect(restored.value, isEmpty);
    });

    test('ForgeSelectedRecordState(選択あり)', () {
      const original = ForgeSelectedRecordState(ForgeRecordItem(id: 'r1', fields: {'name': '太郎'}));
      final restored = ForgeStateValue.fromJson(original.toJson(), '/x') as ForgeSelectedRecordState;
      expect(restored.value?.id, 'r1');
      expect(restored.value?.fields['name'], '太郎');
    });

    test('ForgeSelectedRecordState(無選択)', () {
      const original = ForgeSelectedRecordState(null);
      final restored = ForgeStateValue.fromJson(original.toJson(), '/x') as ForgeSelectedRecordState;
      expect(restored.value, isNull);
    });
  });

  group('mergePersistedState()', () {
    test('保存が無い(null)場合はdeclaredをそのまま返す', () {
      final declared = {'items': const ForgeChecklistState([])};
      final merged = mergePersistedState(declared, null);
      expect(identical(merged, declared), isTrue);
    });

    test('保存が空Mapの場合もdeclaredをそのまま返す', () {
      final declared = {'items': const ForgeChecklistState([])};
      final merged = mergePersistedState(declared, {});
      expect(identical(merged, declared), isTrue);
    });

    test('型が一致するキーは保存値で上書きされる', () {
      final declared = {'items': const ForgeChecklistState([])};
      final persisted = {
        'items': const ForgeChecklistState([
          ForgeChecklistItem(id: 'item_1', text: '牛乳', done: false),
        ]).toJson(),
      };
      final merged = mergePersistedState(declared, persisted);
      final restoredItems = (merged['items'] as ForgeChecklistState).value;
      expect(restoredItems.length, 1);
      expect(restoredItems.single.text, '牛乳');
    });

    test('declaredに無いキーは無視される(AIが再生成してScreen構造が変わった場合)', () {
      final declared = {'items': const ForgeChecklistState([])};
      final persisted = {
        'items': const ForgeChecklistState([]).toJson(),
        'ghost_key': const ForgeStringState('old value').toJson(),
      };
      final merged = mergePersistedState(declared, persisted);
      expect(merged.containsKey('ghost_key'), isFalse);
      expect(merged.length, 1);
    });

    test('型が不一致のキーはdeclared側の値のまま(黙って無視)', () {
      final declared = {'flag': const ForgeBooleanState(false)};
      final persisted = {'flag': const ForgeStringState('not a boolean').toJson()};
      final merged = mergePersistedState(declared, persisted);
      expect(merged['flag'], isA<ForgeBooleanState>());
      expect((merged['flag'] as ForgeBooleanState).value, isFalse);
    });

    test('壊れたJSON(未知のtype)はクラッシュせずdeclared側のまま', () {
      final declared = {'note': const ForgeStringState('元の値')};
      final persisted = {
        'note': {'type': 'totally_unknown_type', 'value': 123},
      };
      final merged = mergePersistedState(declared, persisted);
      expect((merged['note'] as ForgeStringState).value, '元の値');
    });

    test('値がMapでないキーは無視される', () {
      final declared = {'note': const ForgeStringState('元の値')};
      final persisted = {'note': 'not a map at all'};
      final merged = mergePersistedState(declared, persisted);
      expect((merged['note'] as ForgeStringState).value, '元の値');
    });

    test('複数キーの混在(一部成功・一部失敗)を正しく処理する', () {
      final declared = {
        'items': const ForgeChecklistState([]),
        'note': const ForgeStringState('初期メモ'),
      };
      final persisted = {
        'items': const ForgeChecklistState([
          ForgeChecklistItem(id: 'item_1', text: '復元されたはず', done: true),
        ]).toJson(),
        // 'note' は保存に含まれない(declared側のまま)。
      };
      final merged = mergePersistedState(declared, persisted);
      expect((merged['items'] as ForgeChecklistState).value.single.text, '復元されたはず');
      expect((merged['note'] as ForgeStringState).value, '初期メモ');
    });
  });
}
