/// FORGE v1.0(Workstream D: Schema-driven Record Display)。
///
/// `record_schema`の型情報に基づき、Record Field値を安全な表示文字列へ
/// 変換する。**FormatterはWidgetの表示直前にだけ使われ、Record自体の
/// 保存形式には一切影響しない**(表示専用の責務、指示書のDesign
/// Requirements)。
///
/// 今回は複雑なFormatter・ローカライズは行わない(指示書の制約)。
library;

import '../schema/forge_document.dart';

class ForgeValueFormatter {
  const ForgeValueFormatter();

  /// `value`(Recordの`fields`に格納されている実際の値、`null`もありうる)
  /// を、画面表示用の文字列へ変換する。
  String format(Object? value, ForgeRecordFieldType type) {
    if (value == null) {
      return '';
    }
    switch (type) {
      case ForgeRecordFieldType.boolean:
        return (value == true) ? 'はい' : 'いいえ';
      case ForgeRecordFieldType.number:
      case ForgeRecordFieldType.date:
      case ForgeRecordFieldType.string:
      case ForgeRecordFieldType.choice:
      case ForgeRecordFieldType.unknown:
        return value.toString();
    }
  }
}
