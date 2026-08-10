// Typed Record CRUD Test(FORGE v1.0 Workstream C)。
//
// record_schemaに基づくadd/select/update/deleteの型保持と、Legacy
// (schema_ref無し)経路の後方互換をテストする。指示書「CRUD」節
// (各型についてadd/select/update/delete)と「Atomicity」節をカバーする。

import 'package:flutter_test/flutter_test.dart';
import 'package:forge_app/json_ui/runtime/forge_state_store.dart';
import 'package:forge_app/json_ui/schema/forge_document.dart';

const _fishSchema = ForgeRecordSchema(fields: [
  ForgeRecordSchemaField(name: 'species', type: ForgeRecordFieldType.string, label: '魚種', required: true),
  ForgeRecordSchemaField(name: 'size', type: ForgeRecordFieldType.number, label: 'サイズ(cm)', required: false),
  ForgeRecordSchemaField(name: 'catch_date', type: ForgeRecordFieldType.date, label: '日付', required: false),
]);

const _habitSchema = ForgeRecordSchema(fields: [
  ForgeRecordSchemaField(name: 'name', type: ForgeRecordFieldType.string, label: '名称', required: true),
  ForgeRecordSchemaField(name: 'completed', type: ForgeRecordFieldType.boolean, label: '達成済み', required: false),
]);

const _budgetSchema = ForgeRecordSchema(fields: [
  ForgeRecordSchemaField(
    name: 'category', type: ForgeRecordFieldType.choice, label: 'カテゴリ', required: true,
    options: ['食費', '交通費', '娯楽'],
  ),
]);

void main() {
  group('number型: add/select/update/delete', () {
    test('add: 数値文字列がintとしてRecordへ保存される', () {
      final store = ForgeStateStore(
        {
          'records': const ForgeRecordListState([], schemaRef: 'fish'),
          'field_species': const ForgeStringState('アジ'),
          'field_size': const ForgeStringState('30'),
        },
        recordSchemas: {'fish': _fishSchema},
      );
      final outcome = store.addRecord('records', {'species': 'field_species', 'size': 'field_size'});
      expect(outcome, AddRecordOutcome.added);
      final record = store.readRecordList('records').first;
      expect(record.fields['size'], 30);
      expect(record.fields['size'], isA<int>());
    });

    test('add: 不正な数値文字列はvalidationFailedになり、Recordが追加されない', () {
      final store = ForgeStateStore(
        {
          'records': const ForgeRecordListState([], schemaRef: 'fish'),
          'field_species': const ForgeStringState('アジ'),
          'field_size': const ForgeStringState('abc'),
        },
        recordSchemas: {'fish': _fishSchema},
      );
      final outcome = store.addRecord('records', {'species': 'field_species', 'size': 'field_size'});
      expect(outcome, AddRecordOutcome.validationFailed);
      expect(store.readRecordList('records'), isEmpty);
      expect(store.lastFieldErrors.containsKey('size'), isTrue);
    });

    test('update: 数値Fieldを再入力すると、新しい数値型で置き換わる', () {
      final store = ForgeStateStore(
        {
          'records': ForgeRecordListState(
            [const ForgeRecordItem(id: 'rec_1', fields: {'species': 'アジ', 'size': 30})],
            schemaRef: 'fish',
          ),
          'selected': const ForgeSelectedRecordState(ForgeRecordItem(id: 'rec_1', fields: {'species': 'アジ', 'size': 30})),
          'edit_field_species': const ForgeStringState('アジ'),
          'edit_field_size': const ForgeStringState('45.5'),
        },
        recordSchemas: {'fish': _fishSchema},
      );
      final outcome = store.updateRecord(
        'records', 'selected', {'species': 'edit_field_species', 'size': 'edit_field_size'},
      );
      expect(outcome, RecordOperationOutcome.success);
      expect(store.readRecordList('records').first.fields['size'], 45.5);
    });
  });

  group('boolean型: add/select/update/delete', () {
    test('add: booleanのstateがそのままbool値として保存される', () {
      final store = ForgeStateStore(
        {
          'records': const ForgeRecordListState([], schemaRef: 'habit'),
          'field_name': const ForgeStringState('水を飲む'),
          'field_completed': const ForgeBooleanState(true),
        },
        recordSchemas: {'habit': _habitSchema},
      );
      final outcome = store.addRecord('records', {'name': 'field_name', 'completed': 'field_completed'});
      expect(outcome, AddRecordOutcome.added);
      expect(store.readRecordList('records').first.fields['completed'], true);
    });

    test('select: boolean Fieldがboolean型の編集stateへ正しく反映される(過去に発見したバグの回帰)', () {
      final store = ForgeStateStore(
        {
          'records': ForgeRecordListState(
            [const ForgeRecordItem(id: 'rec_1', fields: {'name': '水を飲む', 'completed': true})],
            schemaRef: 'habit',
          ),
          'selected': const ForgeSelectedRecordState(null),
          'edit_field_name': const ForgeStringState(''),
          'edit_field_completed': const ForgeBooleanState(false),
        },
        recordSchemas: {'habit': _habitSchema},
      );
      final outcome = store.selectRecord(
        'records', 'selected', 'rec_1', {'name': 'edit_field_name', 'completed': 'edit_field_completed'},
      );
      expect(outcome, RecordOperationOutcome.success);
      expect(store.read('edit_field_completed'), true);
    });

    test('update: booleanを反転させて更新できる', () {
      final store = ForgeStateStore(
        {
          'records': ForgeRecordListState(
            [const ForgeRecordItem(id: 'rec_1', fields: {'name': '水を飲む', 'completed': false})],
            schemaRef: 'habit',
          ),
          'selected': const ForgeSelectedRecordState(
            ForgeRecordItem(id: 'rec_1', fields: {'name': '水を飲む', 'completed': false}),
          ),
          'edit_field_name': const ForgeStringState('水を飲む'),
          'edit_field_completed': const ForgeBooleanState(true),
        },
        recordSchemas: {'habit': _habitSchema},
      );
      final outcome = store.updateRecord(
        'records', 'selected', {'name': 'edit_field_name', 'completed': 'edit_field_completed'},
      );
      expect(outcome, RecordOperationOutcome.success);
      expect(store.readRecordList('records').first.fields['completed'], true);
    });

    test('delete: booleanを含むRecordも他Fieldと同様に削除できる', () {
      final store = ForgeStateStore(
        {
          'records': ForgeRecordListState(
            [const ForgeRecordItem(id: 'rec_1', fields: {'name': '水を飲む', 'completed': true})],
            schemaRef: 'habit',
          ),
          'selected': const ForgeSelectedRecordState(
            ForgeRecordItem(id: 'rec_1', fields: {'name': '水を飲む', 'completed': true}),
          ),
        },
        recordSchemas: {'habit': _habitSchema},
      );
      expect(store.deleteRecord('records', 'selected'), RecordOperationOutcome.success);
      expect(store.readRecordList('records'), isEmpty);
    });
  });

  group('date型: add/select/update/delete', () {
    test('add: 有効なISO日付が正規化された文字列として保存される', () {
      final store = ForgeStateStore(
        {
          'records': const ForgeRecordListState([], schemaRef: 'fish'),
          'field_species': const ForgeStringState('アジ'),
          'field_catch_date': const ForgeStringState('2026-07-19'),
        },
        recordSchemas: {'fish': _fishSchema},
      );
      final outcome = store.addRecord('records', {'species': 'field_species', 'catch_date': 'field_catch_date'});
      expect(outcome, AddRecordOutcome.added);
      expect(store.readRecordList('records').first.fields['catch_date'], '2026-07-19');
    });

    test('add: 実在しない日付(2026-02-30)はvalidationFailedになる', () {
      final store = ForgeStateStore(
        {
          'records': const ForgeRecordListState([], schemaRef: 'fish'),
          'field_species': const ForgeStringState('アジ'),
          'field_catch_date': const ForgeStringState('2026-02-30'),
        },
        recordSchemas: {'fish': _fishSchema},
      );
      final outcome = store.addRecord('records', {'species': 'field_species', 'catch_date': 'field_catch_date'});
      expect(outcome, AddRecordOutcome.validationFailed);
      expect(store.readRecordList('records'), isEmpty);
    });
  });

  group('choice型: add/select/update/delete', () {
    test('add: options内の値は保存できる', () {
      final store = ForgeStateStore(
        {
          'records': const ForgeRecordListState([], schemaRef: 'budget'),
          'field_category': const ForgeStringState('交通費'),
        },
        recordSchemas: {'budget': _budgetSchema},
      );
      final outcome = store.addRecord('records', {'category': 'field_category'});
      expect(outcome, AddRecordOutcome.added);
      expect(store.readRecordList('records').first.fields['category'], '交通費');
    });

    test('add: options外の値は保存できない', () {
      final store = ForgeStateStore(
        {
          'records': const ForgeRecordListState([], schemaRef: 'budget'),
          'field_category': const ForgeStringState('サブスク'),
        },
        recordSchemas: {'budget': _budgetSchema},
      );
      final outcome = store.addRecord('records', {'category': 'field_category'});
      expect(outcome, AddRecordOutcome.validationFailed);
      expect(store.readRecordList('records'), isEmpty);
    });

    test('update: 編集時にoptions外の値へ変更しようとすると、既存値を黙って上書きしない', () {
      final store = ForgeStateStore(
        {
          'records': ForgeRecordListState(
            [const ForgeRecordItem(id: 'rec_1', fields: {'category': '食費'})],
            schemaRef: 'budget',
          ),
          'selected': const ForgeSelectedRecordState(ForgeRecordItem(id: 'rec_1', fields: {'category': '食費'})),
          'edit_field_category': const ForgeStringState('サブスク'), // optionsに無い
        },
        recordSchemas: {'budget': _budgetSchema},
      );
      final outcome = store.updateRecord('records', 'selected', {'category': 'edit_field_category'});
      expect(outcome, RecordOperationOutcome.invalidBinding);
      // 既存値がそのまま残っていること(黙って上書きされていない)。
      expect(store.readRecordList('records').first.fields['category'], '食費');
    });
  });

  group('Legacy Behavior(schema_refが無い場合)', () {
    test('schema_ref無しのrecord_listは、従来通りstring/number/booleanをそのまま転記する', () {
      final store = ForgeStateStore({
        'records': const ForgeRecordListState([]), // schemaRef無し
        'field_species': const ForgeStringState('アジ(未検証文字列)'),
      });
      final outcome = store.addRecord('records', {'species': 'field_species'});
      expect(outcome, AddRecordOutcome.added);
      expect(store.readRecordList('records').first.fields['species'], 'アジ(未検証文字列)');
    });

    test('recordSchemasを渡さないStateStoreでも、schema_ref無しのrecord_listは動作する', () {
      final store = ForgeStateStore({
        'records': const ForgeRecordListState([]),
        'field_species': const ForgeStringState('アジ'),
      });
      expect(store.addRecord('records', {'species': 'field_species'}), AddRecordOutcome.added);
    });
  });

  group('schemaRefの保持(実装中に発見・修正したバグの回帰)', () {
    test('update後もrecord_listのschemaRefが失われない', () {
      final store = ForgeStateStore(
        {
          'records': ForgeRecordListState(
            [const ForgeRecordItem(id: 'rec_1', fields: {'species': 'アジ'})],
            schemaRef: 'fish',
          ),
          'selected': const ForgeSelectedRecordState(ForgeRecordItem(id: 'rec_1', fields: {'species': 'アジ'})),
          'edit_field_species': const ForgeStringState('サバ'),
        },
        recordSchemas: {'fish': _fishSchema},
      );
      store.updateRecord('records', 'selected', {'species': 'edit_field_species'});
      expect(store.readRecordListSchemaRef('records'), 'fish');
    });

    test('delete後もrecord_listのschemaRefが失われない', () {
      final store = ForgeStateStore(
        {
          'records': ForgeRecordListState(
            [
              const ForgeRecordItem(id: 'rec_1', fields: {'species': 'アジ'}),
              const ForgeRecordItem(id: 'rec_2', fields: {'species': 'サバ'}),
            ],
            schemaRef: 'fish',
          ),
          'selected': const ForgeSelectedRecordState(ForgeRecordItem(id: 'rec_1', fields: {'species': 'アジ'})),
        },
        recordSchemas: {'fish': _fishSchema},
      );
      store.deleteRecord('records', 'selected');
      expect(store.readRecordListSchemaRef('records'), 'fish');
    });
  });

  group('Atomicity(Workstream C全型共通)', () {
    test('1 Field失敗時に全State不変', () {
      final store = ForgeStateStore(
        {
          'records': const ForgeRecordListState([], schemaRef: 'fish'),
          'field_species': const ForgeStringState('アジ'),
          'field_size': const ForgeStringState('not_a_number'),
        },
        recordSchemas: {'fish': _fishSchema},
      );
      store.addRecord('records', {'species': 'field_species', 'size': 'field_size'});
      expect(store.readRecordList('records'), isEmpty, reason: '1件でも失敗すれば追加されない');
    });

    test('選択失敗後に前Recordを誤更新しない(v0.8.1のAtomicity保証を型検証下でも維持)', () {
      final store = ForgeStateStore(
        {
          'records': ForgeRecordListState(
            [
              const ForgeRecordItem(id: 'rec_a', fields: {'species': 'アジ', 'size': 30}),
              const ForgeRecordItem(id: 'rec_b', fields: {'species': 'サバ'}), // sizeを持たない
            ],
            schemaRef: 'fish',
          ),
          'selected': const ForgeSelectedRecordState(null),
          'edit_field_species': const ForgeStringState(''),
          'edit_field_size': const ForgeStringState(''),
        },
        recordSchemas: {'fish': _fishSchema},
      );
      const bindings = {'species': 'edit_field_species', 'size': 'edit_field_size'};
      expect(store.selectRecord('records', 'selected', 'rec_a', bindings), RecordOperationOutcome.success);
      expect(store.read('edit_field_species'), 'アジ');

      // rec_bはsizeを持たないため、field_bindingsにsizeを要求すると失敗する。
      final failOutcome = store.selectRecord('records', 'selected', 'rec_b', bindings);
      expect(failOutcome, RecordOperationOutcome.invalidBinding);
      // 失敗後も選択・編集Fieldはrec_aのまま。
      expect(store.readSelectedRecord('selected')?.id, 'rec_a');
      expect(store.read('edit_field_species'), 'アジ');
    });

    test('update後にlist/selected/edit statesが一致する(型検証下でも)', () {
      final store = ForgeStateStore(
        {
          'records': ForgeRecordListState(
            [const ForgeRecordItem(id: 'rec_1', fields: {'species': 'アジ', 'size': 30})],
            schemaRef: 'fish',
          ),
          'selected': const ForgeSelectedRecordState(
            ForgeRecordItem(id: 'rec_1', fields: {'species': 'アジ', 'size': 30}),
          ),
          'edit_field_species': const ForgeStringState('サバ'),
          'edit_field_size': const ForgeStringState('25'),
        },
        recordSchemas: {'fish': _fishSchema},
      );
      store.updateRecord('records', 'selected', {'species': 'edit_field_species', 'size': 'edit_field_size'});
      final listRecord = store.readRecordList('records').first;
      final selectedRecord = store.readSelectedRecord('selected');
      expect(selectedRecord!.fields, listRecord.fields);
      expect(listRecord.fields['size'], 25);
      expect(listRecord.fields['size'], isA<int>());
    });

    test('delete後にselected/edit statesクリア(型検証下でも維持)', () {
      final store = ForgeStateStore(
        {
          'records': ForgeRecordListState(
            [const ForgeRecordItem(id: 'rec_1', fields: {'species': 'アジ'})],
            schemaRef: 'fish',
          ),
          'selected': const ForgeSelectedRecordState(ForgeRecordItem(id: 'rec_1', fields: {'species': 'アジ'})),
        },
        recordSchemas: {'fish': _fishSchema},
      );
      store.deleteRecord('records', 'selected');
      expect(store.readSelectedRecord('selected'), isNull);
    });
  });
}
