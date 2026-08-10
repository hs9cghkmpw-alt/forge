// record_schema parsing / holding / type-retrieval tests
// (FORGE v0.9 Typed Record Runtime Phase1)。
//
// 指示書「Runtime」節の3項目(schema parse・schema保持・型取得)を
// カバーする。実行未検証(Claudeのサンドボックスに Dart SDK が無い)。

import 'package:flutter_test/flutter_test.dart';
import 'package:forge_app/json_ui/renderer/forge_runtime_state.dart';
import 'package:forge_app/json_ui/schema/forge_document.dart';

Map<String, dynamic> _fishRecordSchemaJson() {
  // 指示書の record_schema 例そのもの。
  return {
    'fields': [
      {'name': 'species', 'type': 'string', 'label': '魚種', 'required': true},
      {'name': 'size', 'type': 'number', 'label': 'サイズ(cm)', 'required': false},
      {'name': 'date', 'type': 'date', 'label': '日付', 'required': false},
      {'name': 'memo', 'type': 'string', 'label': 'メモ', 'required': false},
    ],
  };
}

void main() {
  group('schema parse', () {
    test('ForgeRecordSchema.fromJsonが全Fieldを正しく解析する', () {
      final schema = ForgeRecordSchema.fromJson(_fishRecordSchemaJson(), '/record_schemas/fish_record');
      expect(schema.fields, hasLength(4));
      expect(schema.fields.map((f) => f.name), ['species', 'size', 'date', 'memo']);
    });

    test('各Fieldのtype/label/requiredが正しく解析される', () {
      final schema = ForgeRecordSchema.fromJson(_fishRecordSchemaJson(), '/record_schemas/fish_record');
      final species = schema.fieldByName('species')!;
      expect(species.type, ForgeRecordFieldType.string);
      expect(species.label, '魚種');
      expect(species.required, isTrue);

      final size = schema.fieldByName('size')!;
      expect(size.type, ForgeRecordFieldType.number);
      expect(size.required, isFalse);

      final date = schema.fieldByName('date')!;
      expect(date.type, ForgeRecordFieldType.date);
    });

    test('Supported Typesの5種(string/number/boolean/date/choice)全てを解析できる', () {
      final json = {
        'fields': [
          {'name': 'a', 'type': 'string', 'label': 'A'},
          {'name': 'b', 'type': 'number', 'label': 'B'},
          {'name': 'c', 'type': 'boolean', 'label': 'C'},
          {'name': 'd', 'type': 'date', 'label': 'D'},
          {'name': 'e', 'type': 'choice', 'label': 'E', 'options': ['x', 'y']},
        ],
      };
      final schema = ForgeRecordSchema.fromJson(json, '/record_schemas/sample');
      expect(schema.fieldByName('a')!.type, ForgeRecordFieldType.string);
      expect(schema.fieldByName('b')!.type, ForgeRecordFieldType.number);
      expect(schema.fieldByName('c')!.type, ForgeRecordFieldType.boolean);
      expect(schema.fieldByName('d')!.type, ForgeRecordFieldType.date);
      expect(schema.fieldByName('e')!.type, ForgeRecordFieldType.choice);
    });

    test('choice型のoptionsが正しく解析される', () {
      final json = {
        'fields': [
          {'name': 'category', 'type': 'choice', 'label': 'カテゴリ', 'options': ['食費', '交通費', '娯楽']},
        ],
      };
      final schema = ForgeRecordSchema.fromJson(json, '/record_schemas/sample');
      expect(schema.fieldByName('category')!.options, ['食費', '交通費', '娯楽']);
    });

    test('requiredを省略した場合は既定でtrueになる', () {
      final json = {
        'fields': [
          {'name': 'a', 'type': 'string', 'label': 'A'},
        ],
      };
      final schema = ForgeRecordSchema.fromJson(json, '/record_schemas/sample');
      expect(schema.fieldByName('a')!.required, isTrue);
    });

    test('未知の型はunknownへ安全にフォールバックする(後方互換)', () {
      final json = {
        'fields': [
          {'name': 'a', 'type': 'future_type_not_yet_supported', 'label': 'A'},
        ],
      };
      final schema = ForgeRecordSchema.fromJson(json, '/record_schemas/sample');
      expect(schema.fieldByName('a')!.type, ForgeRecordFieldType.unknown);
    });

    test('fields欠落はForgeParseExceptionを送出する', () {
      expect(
        () => ForgeRecordSchema.fromJson({}, '/record_schemas/sample'),
        throwsA(isA<ForgeParseException>()),
      );
    });

    test('name欠落のFieldはForgeParseExceptionを送出する', () {
      final json = {
        'fields': [
          {'type': 'string', 'label': 'A'},
        ],
      };
      expect(
        () => ForgeRecordSchema.fromJson(json, '/record_schemas/sample'),
        throwsA(isA<ForgeParseException>()),
      );
    });
  });

  group('ForgeDocument経由でのrecord_schemas parse', () {
    test('文書トップレベルのrecord_schemasが解析され、ForgeDocument.recordSchemasへ格納される', () {
      final doc = ForgeDocument.fromJson({
        'version': '1.4',
        'initial_screen_id': 's1',
        'record_schemas': {'fish_record': _fishRecordSchemaJson()},
        'screens': [
          {
            'id': 's1', 'title': 'S1',
            'state': {'records': {'type': 'record_list', 'value': [], 'schema_ref': 'fish_record'}},
            'body': {'type': 'record_list_view', 'id': 'rlv1', 'state_ref': 'records'},
          },
        ],
      });
      expect(doc.recordSchemas, hasLength(1));
      expect(doc.recordSchemas.containsKey('fish_record'), isTrue);
      expect(doc.recordSchemaByRef('fish_record')?.fields, hasLength(4));
    });

    test('record_schemasが無い文書ではrecordSchemasが空のMapになる(後方互換)', () {
      final doc = ForgeDocument.fromJson({
        'version': '1.3',
        'initial_screen_id': 's1',
        'screens': [
          {
            'id': 's1', 'title': 'S1',
            'state': {'records': {'type': 'record_list', 'value': []}},
            'body': {'type': 'record_list_view', 'id': 'rlv1', 'state_ref': 'records'},
          },
        ],
      });
      expect(doc.recordSchemas, isEmpty);
    });

    test('record_listのschema_refが正しく解析される', () {
      final doc = ForgeDocument.fromJson({
        'version': '1.4',
        'initial_screen_id': 's1',
        'record_schemas': {'fish_record': _fishRecordSchemaJson()},
        'screens': [
          {
            'id': 's1', 'title': 'S1',
            'state': {'records': {'type': 'record_list', 'value': [], 'schema_ref': 'fish_record'}},
            'body': {'type': 'record_list_view', 'id': 'rlv1', 'state_ref': 'records'},
          },
        ],
      });
      final recordsState = doc.screens.first.state['records'];
      expect(recordsState, isA<ForgeRecordListState>());
      expect((recordsState as ForgeRecordListState).schemaRef, 'fish_record');
    });

    test('schema_refが無いrecord_listはnullのまま(後方互換、既存Phase1/2文書)', () {
      final doc = ForgeDocument.fromJson({
        'version': '1.3',
        'initial_screen_id': 's1',
        'screens': [
          {
            'id': 's1', 'title': 'S1',
            'state': {'records': {'type': 'record_list', 'value': []}},
            'body': {'type': 'record_list_view', 'id': 'rlv1', 'state_ref': 'records'},
          },
        ],
      });
      final recordsState = doc.screens.first.state['records'] as ForgeRecordListState;
      expect(recordsState.schemaRef, isNull);
    });
  });

  group('schema保持', () {
    test('ForgeRuntimeStateがrecordSchemasを保持し、そのまま取り出せる', () {
      final schema = ForgeRecordSchema.fromJson(_fishRecordSchemaJson(), '/record_schemas/fish_record');
      final state = ForgeRuntimeState(
        {'records': const ForgeRecordListState([], schemaRef: 'fish_record')},
        recordSchemas: {'fish_record': schema},
      );
      addTearDown(state.dispose);

      expect(state.recordSchemas, hasLength(1));
      expect(state.recordSchemas['fish_record'], same(schema));
    });

    test('recordSchemasを渡さない場合は空のMapが既定値になる(後方互換)', () {
      final state = ForgeRuntimeState({'x': const ForgeStringState('')});
      addTearDown(state.dispose);
      expect(state.recordSchemas, isEmpty);
    });
  });

  group('型取得', () {
    test('getRecordSchemaでschemaRefから正しいSchemaを取得できる', () {
      final schema = ForgeRecordSchema.fromJson(_fishRecordSchemaJson(), '/record_schemas/fish_record');
      final state = ForgeRuntimeState({}, recordSchemas: {'fish_record': schema});
      addTearDown(state.dispose);

      expect(state.getRecordSchema('fish_record'), same(schema));
      expect(state.getRecordSchema('does_not_exist'), isNull);
    });

    test('getRecordFieldTypeでField名から直接型を取得できる', () {
      final schema = ForgeRecordSchema.fromJson(_fishRecordSchemaJson(), '/record_schemas/fish_record');
      final state = ForgeRuntimeState({}, recordSchemas: {'fish_record': schema});
      addTearDown(state.dispose);

      expect(state.getRecordFieldType('fish_record', 'species'), ForgeRecordFieldType.string);
      expect(state.getRecordFieldType('fish_record', 'size'), ForgeRecordFieldType.number);
      expect(state.getRecordFieldType('fish_record', 'date'), ForgeRecordFieldType.date);
    });

    test('存在しないSchema・Fieldの型取得はnullを返す(クラッシュしない)', () {
      final state = ForgeRuntimeState({});
      addTearDown(state.dispose);

      expect(state.getRecordFieldType('does_not_exist', 'species'), isNull);

      final schema = ForgeRecordSchema.fromJson(_fishRecordSchemaJson(), '/record_schemas/fish_record');
      final state2 = ForgeRuntimeState({}, recordSchemas: {'fish_record': schema});
      addTearDown(state2.dispose);
      expect(state2.getRecordFieldType('fish_record', 'does_not_exist_field'), isNull);
    });
  });
}
