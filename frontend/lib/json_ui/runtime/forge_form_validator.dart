import '../schema/forge_document.dart';
import 'forge_state_store.dart';

/// 1フィールド分の検証対象(state_ref + そのルール一覧)。
class ForgeValidatableField {
  final String stateRef;
  final List<ForgeValidationRule> rules;
  const ForgeValidatableField({required this.stateRef, required this.rules});
}

/// Form Validation(FORGE-MILESTONE-003 Task 5)。
///
/// [ForgeStateStore]と[ForgeValidatableField]のリストだけを受け取り、
/// 特定のWidget構造やRendererの詳細を知らない(依存方向を守る)。
class ForgeFormValidator {
  const ForgeFormValidator();

  /// フォーム内の全フィールドを検証する。戻り値は
  /// `state_ref -> エラーメッセージ`(合格したフィールドはキーを含まない)。
  Map<String, String> validate(List<ForgeValidatableField> fields, ForgeStateStore store) {
    final errors = <String, String>{};
    for (final field in fields) {
      final message = _validateField(field, store);
      if (message != null) {
        errors[field.stateRef] = message;
      }
    }
    return errors;
  }

  String? _validateField(ForgeValidatableField field, ForgeStateStore store) {
    final value = store.read(field.stateRef);
    for (final rule in field.rules) {
      final error = _checkRule(rule, value);
      if (error != null) return error;
    }
    return null;
  }

  /// 1ルールを検証する。State型に適用できないルールは、クラッシュさせず
  /// 「合格扱い」で安全に無視する(指示書Task 5「不正なValidation定義でも
  /// クラッシュしない」「State型に適用できないValidationは安全に失敗または
  /// 無視し、開発ログへ理由を残す」。ログはActionDispatcher側で行う。
  /// このクラス単体では診断ログを持たない — 依存方向を守るため、
  /// diagnosticsへの依存はDispatcher層に閉じ込めている)。
  String? _checkRule(ForgeValidationRule rule, dynamic value) {
    switch (rule.type) {
      case 'required':
        if (value is String && value.trim().isEmpty) return rule.message;
        if (value is bool && value == false) return rule.message;
        if (value == null) return rule.message;
        return null;
      case 'min_length':
        if (value is! String) return null; // 適用不能、安全に無視
        final min = _asInt(rule.value);
        if (min != null && value.length < min) return rule.message;
        return null;
      case 'max_length':
        if (value is! String) return null;
        final max = _asInt(rule.value);
        if (max != null && value.length > max) return rule.message;
        return null;
      case 'min':
        if (value is! num) return null;
        final min = _asNum(rule.value);
        if (min != null && value < min) return rule.message;
        return null;
      case 'max':
        if (value is! num) return null;
        final max = _asNum(rule.value);
        if (max != null && value > max) return rule.message;
        return null;
      case 'pattern':
        if (value is! String) return null;
        final pattern = rule.value;
        if (pattern is! String) return null;
        try {
          if (!RegExp(pattern).hasMatch(value)) return rule.message;
        } catch (_) {
          // 不正な正規表現(Validatorで既に弾かれているはずだが、多重防御)。
          // クラッシュさせず、ルール自体を無視する。
          return null;
        }
        return null;
      default:
        // 未知ルール種別。クラッシュさせず無視する。
        return null;
    }
  }

  int? _asInt(dynamic v) => v is int ? v : (v is double ? v.toInt() : null);
  num? _asNum(dynamic v) => v is num ? v : null;
}
