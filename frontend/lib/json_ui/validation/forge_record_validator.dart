/// FORGE v1.0(Workstream E: Validation Architecture)。
///
/// `record_schema`全体に対して、複数Fieldの入力値をまとめて検証する。
/// **ValidatorはSchema制約の検証を担当する**(指示書のDesign
/// Requirements)。1件でも検証に失敗すれば、全体を失敗として返す
/// (Atomicity、Workstream C.2「全Bindingの事前検証」の実装)。
///
/// このクラス自体はStateを一切変更しない(副作用の無い、純粋な
/// 検証ロジック)。実際のState mutationは[ForgeStateStore]が担当する
/// (責務分離)。
library;

import '../schema/forge_document.dart';
import 'forge_field_value_parser.dart';

sealed class RecordValidationResult {
  const RecordValidationResult();
}

/// 全Fieldの検証に成功した。[fields]は型付き済みの値
/// (`String`/`int`/`double`/`bool`)で、非必須かつ空のFieldは
/// キー自体が含まれない。
class RecordValidationSuccess extends RecordValidationResult {
  final Map<String, Object> fields;
  const RecordValidationSuccess(this.fields);
}

/// 1件以上のFieldで検証に失敗した(Field名 → 失敗内容)。
class RecordValidationFailure extends RecordValidationResult {
  final Map<String, FieldParseFailure> fieldErrors;
  const RecordValidationFailure(this.fieldErrors);
}

class ForgeRecordValidator {
  final ForgeFieldValueParser _parser;
  const ForgeRecordValidator({ForgeFieldValueParser parser = const ForgeFieldValueParser()}) : _parser = parser;

  /// `rawValues`: Field名 → 生の入力値。値の型はSourceの実際のState型
  /// による(`text_field`系のFieldなら`String`、`checkbox`
  /// (boolean型Field)なら`bool`)。Schemaに存在するが`rawValues`に
  /// 対応するキーが無いFieldは、空文字列を渡したのと同じ扱いにする
  /// (=非必須なら省略、必須なら`requiredEmpty`失敗)。
  RecordValidationResult validate(ForgeRecordSchema schema, Map<String, Object?> rawValues) {
    final fields = <String, Object>{};
    final errors = <String, FieldParseFailure>{};

    for (final field in schema.fields) {
      final raw = rawValues[field.name];
      final FieldParseResult result;
      if (field.type == ForgeRecordFieldType.boolean && raw is bool) {
        result = _parser.parseBoolean(raw);
      } else {
        result = _parser.parse(raw == null ? '' : raw.toString(), field);
      }

      switch (result) {
        case FieldParseSuccess(:final value):
          fields[field.name] = value;
        case FieldParseEmpty():
          break;
        case FieldParseFailure():
          errors[field.name] = result;
      }
    }

    if (errors.isNotEmpty) {
      return RecordValidationFailure(errors);
    }
    return RecordValidationSuccess(fields);
  }
}
