/// FORGE v1.0(Workstream E: Validation Architecture)。
///
/// 生の文字列(Form入力の`text_field`が持つ値)を、`record_schema`の
/// Field型情報に基づいて型付きの値へ変換する。
///
/// **責務分離(指示書のDesign Requirements)**:
/// - Widget(`widget_registry_*.dart`)は入力とエラー表示のみを担当する。
/// - **このクラスは、入力値から型付き値への変換のみを担当する**
///   (Schema制約全体の検証・複数Fieldにまたがる整合性は
///   [ForgeRecordValidator]が担当する)。
/// - Compilerはこのロジックを再実装しない(指示書「CompilerはRuntime
///   Validationを再実装しない」)。数値/日付の`pattern`
///   Validationルール(`forge_language_compiler.py`)は、あくまで
///   「明らかに不正な入力を早期にUIへ知らせる」補助であり、実際の
///   型変換・実在日付チェック等の権威ある判定はこのクラスが行う。
library;

import '../schema/forge_document.dart';

/// [ForgeFieldValueParser.parse]の結果。
sealed class FieldParseResult {
  const FieldParseResult();
}

/// パースに成功し、値が得られた。
class FieldParseSuccess extends FieldParseResult {
  /// `String` | `int` | `double` | `bool` のいずれか
  /// (`ForgeRecordSchemaField.type`に対応する)。
  final Object value;
  const FieldParseSuccess(this.value);
}

/// 非必須のFieldが空のまま送信された(失敗ではない、正常な「値なし」)。
/// 呼び出し側は、この場合Recordの`fields`から当該Fieldを省略する
/// (`null`を明示的に格納しない、5.1節の設計判断)。
class FieldParseEmpty extends FieldParseResult {
  const FieldParseEmpty();
}

/// パースに失敗した理由。
enum FieldParseFailureReason {
  requiredEmpty,
  invalidNumber,
  invalidDate,
  nonexistentDate,
  invalidChoice,
  invalidBoolean,
}

class FieldParseFailure extends FieldParseResult {
  final FieldParseFailureReason reason;
  final String message;
  const FieldParseFailure(this.reason, this.message);
}

class ForgeFieldValueParser {
  const ForgeFieldValueParser();

  static final RegExp _isoDatePattern = RegExp(r'^(\d{4})-(\d{2})-(\d{2})$');

  /// `raw`(Form入力の生文字列)を`field`の型に従ってパースする。
  ///
  /// 空文字列の扱い(指示書4.3節「空文字とnullをどう扱うか」への回答):
  /// - `field.required`が`true`の場合 → [FieldParseFailure]
  ///   (`requiredEmpty`)。
  /// - `field.required`が`false`の場合 → [FieldParseEmpty]
  ///   (型に関わらず「値なし」として扱う。Recordの`fields`には
  ///   当該Fieldを含めない)。
  FieldParseResult parse(String raw, ForgeRecordSchemaField field) {
    if (raw.isEmpty) {
      if (field.required) {
        return FieldParseFailure(FieldParseFailureReason.requiredEmpty, '${field.label}を入力してください');
      }
      return const FieldParseEmpty();
    }

    switch (field.type) {
      case ForgeRecordFieldType.string:
        return FieldParseSuccess(raw);
      case ForgeRecordFieldType.number:
        return _parseNumber(raw, field);
      case ForgeRecordFieldType.boolean:
        return _parseBooleanString(raw, field);
      case ForgeRecordFieldType.date:
        return _parseDate(raw, field);
      case ForgeRecordFieldType.choice:
        return _parseChoice(raw, field);
      case ForgeRecordFieldType.unknown:
        // 未知の型は安全側に倒し、文字列としてそのまま受け入れる
        // (既存の「未知Widgetは安全にFallback」という設計原則を
        // 型情報にも適用したもの、forge_document.dartのdocコメント参照)。
        return FieldParseSuccess(raw);
    }
  }

  /// [ForgeBooleanState]の値を直接パースする(checkbox入力の場合、
  /// 文字列を経由しないため、こちらを使う想定)。
  FieldParseResult parseBoolean(bool value) => FieldParseSuccess(value);

  FieldParseResult _parseNumber(String raw, ForgeRecordSchemaField field) {
    // 指示書「推奨はJSON numberとして保持し、整数はint、小数はdouble」
    // に従う: 小数点を含まない場合はintを優先的に試す。
    if (!raw.contains('.')) {
      final asInt = int.tryParse(raw);
      if (asInt != null) return FieldParseSuccess(asInt);
    }
    final asDouble = double.tryParse(raw);
    if (asDouble != null) return FieldParseSuccess(asDouble);
    return FieldParseFailure(FieldParseFailureReason.invalidNumber, '${field.label}は数字で入力してください');
  }

  FieldParseResult _parseBooleanString(String raw, ForgeRecordSchemaField field) {
    if (raw == 'true') return const FieldParseSuccess(true);
    if (raw == 'false') return const FieldParseSuccess(false);
    return FieldParseFailure(FieldParseFailureReason.invalidBoolean, '${field.label}の値が不正です');
  }

  FieldParseResult _parseDate(String raw, ForgeRecordSchemaField field) {
    final match = _isoDatePattern.firstMatch(raw);
    if (match == null) {
      return FieldParseFailure(
        FieldParseFailureReason.invalidDate, '${field.label}はYYYY-MM-DD形式で入力してください',
      );
    }
    final year = int.parse(match.group(1)!);
    final month = int.parse(match.group(2)!);
    final day = int.parse(match.group(3)!);

    // 実在する日付かどうかは、DateTimeコンストラクタが桁あふれを
    // 自動的に繰り上げる性質(例: 2026-02-30 -> 2026-03-02)を逆手に
    // とって検出する、よく知られた手法(標準ライブラリの機能だけで
    // 正確なカレンダー検証ができる)。
    final dt = DateTime(year, month, day);
    if (dt.year != year || dt.month != month || dt.day != day) {
      return FieldParseFailure(
        FieldParseFailureReason.nonexistentDate, '${field.label}に実在しない日付が指定されています',
      );
    }

    final normalized = '${year.toString().padLeft(4, '0')}-'
        '${month.toString().padLeft(2, '0')}-'
        '${day.toString().padLeft(2, '0')}';
    return FieldParseSuccess(normalized);
  }

  FieldParseResult _parseChoice(String raw, ForgeRecordSchemaField field) {
    final options = field.options ?? const <String>[];
    if (!options.contains(raw)) {
      final optionsText = options.isEmpty ? '(選択肢が定義されていません)' : options.join('・');
      return FieldParseFailure(
        FieldParseFailureReason.invalidChoice, '${field.label}は$optionsTextのいずれかを選択してください',
      );
    }
    return FieldParseSuccess(raw);
  }
}
