import '../renderer/forge_runtime_state.dart';
import 'forge_expression.dart';

/// Binds the pure Forge expression engine to the live generated-app state.
///
/// This adapter intentionally depends only on the generic runtime state API.
/// It has no knowledge of app templates, widget kinds, domains, or screens.
/// That keeps GA-1 logic reusable for arbitrary generated applications.
extension ForgeRuntimeExpression on ForgeRuntimeState {
  dynamic evaluateExpression(Map<String, dynamic> expression) {
    return evaluateForgeExpression(
      expression,
      readState: read,
      readRecords: (key) => [
        for (final record in getRecordList(key))
          Map<String, dynamic>.from(record.fields),
      ],
    );
  }

  /// Strict boolean condition evaluation for conditional behavior/rendering.
  /// Non-boolean results fail closed instead of relying on truthy coercion.
  bool evaluateCondition(Map<String, dynamic> expression) {
    final result = evaluateExpression(expression);
    if (result is bool) return result;
    throw const ForgeExpressionException('condition expression must evaluate to boolean');
  }
}
