// ForgeRecordValidator Unit Test(FORGE v1.0 Workstream E)。
//
// 複数Fieldをまとめて検証する際のAtomicity(1件でも失敗すれば全体を
// failureとして返す)を中心にテストする。

import 'package:flutter_test/flutter_test.dart';
import 'package:forge_app/json_ui/schema/forge_document.dart';
import 'package:forge_app/json_ui/validation/forge_record_validator.dart';

ForgeRecordSchema _fishRecordSchema() {
  return const ForgeRecordSchema(fields: [
    ForgeRecordSchemaField(name: 'species', type: ForgeRecordFieldType.string, label: '魚種', required: true),
    ForgeRecordSchemaField(name: 'size', type: ForgeRecordFieldType.number, label: 'サイズ(cm)', required: false),
  ]);
}

void main() {
  final validator = const ForgeRecordValidator();

  test('全Fieldが有効な場合、型付き済みのfieldsを返す', () {
    final result = validator.validate(_fishRecordSchema(), {'species': 'アジ', 'size': '30'});
    expect(result, isA<RecordValidationSuccess>());
    final fields = (result as RecordValidationSuccess).fields;
    expect(fields['species'], 'アジ');
    expect(fields['size'], 30);
  });

  test('非必須Fieldが空の場合、そのFieldはfieldsから省略される', () {
    final result = validator.validate(_fishRecordSchema(), {'species': 'アジ', 'size': ''});
    expect(result, isA<RecordValidationSuccess>());
    final fields = (result as RecordValidationSuccess).fields;
    expect(fields.containsKey('size'), isFalse);
  });

  test('1Fieldでも検証に失敗すれば、全体がfailureになる(Atomicity)', () {
    final result = validator.validate(_fishRecordSchema(), {'species': 'アジ', 'size': 'not_a_number'});
    expect(result, isA<RecordValidationFailure>());
    final errors = (result as RecordValidationFailure).fieldErrors;
    expect(errors.containsKey('size'), isTrue);
    // 検証に失敗した場合、成功したはずのFieldの値も一切返さない
    // (呼び出し側がpartialな結果を誤って使わないようにするため)。
  });

  test('必須Fieldが空の場合もfailureになる', () {
    final result = validator.validate(_fishRecordSchema(), {'species': '', 'size': '30'});
    expect(result, isA<RecordValidationFailure>());
    expect((result as RecordValidationFailure).fieldErrors.containsKey('species'), isTrue);
  });

  test('rawValuesに存在しないFieldは空文字列として扱われる', () {
    final result = validator.validate(_fishRecordSchema(), {'species': 'アジ'});
    // sizeは非必須なので、キーが無くてもEmpty扱いになり成功する。
    expect(result, isA<RecordValidationSuccess>());
  });

  test('boolean型のFieldはbool値をそのまま渡すとparseBoolean経由で処理される', () {
    const schema = ForgeRecordSchema(fields: [
      ForgeRecordSchemaField(name: 'completed', type: ForgeRecordFieldType.boolean, label: '達成済み', required: false),
    ]);
    final result = validator.validate(schema, {'completed': true});
    expect(result, isA<RecordValidationSuccess>());
    expect((result as RecordValidationSuccess).fields['completed'], true);
  });

  test('複数のField失敗があれば、両方ともfieldErrorsに含まれる', () {
    const schema = ForgeRecordSchema(fields: [
      ForgeRecordSchemaField(name: 'a', type: ForgeRecordFieldType.number, label: 'A', required: true),
      ForgeRecordSchemaField(name: 'b', type: ForgeRecordFieldType.date, label: 'B', required: true),
    ]);
    final result = validator.validate(schema, {'a': 'not_a_number', 'b': 'not_a_date'});
    expect(result, isA<RecordValidationFailure>());
    final errors = (result as RecordValidationFailure).fieldErrors;
    expect(errors.length, 2);
  });
}
