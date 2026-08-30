import '../renderer/forge_runtime_state.dart';
import 'forge_expression.dart';
import 'forge_runtime_expression.dart';

/// Declarative GA-1 logic attached to a generated Forge document.
///
/// This layer intentionally contains no app/domain knowledge. It only binds the
/// generic expression AST to named derived values and conditional visibility.
class ForgeLogicDocument {
  final Map<String, Map<String, dynamic>> derived;
  final Map<String, Map<String, dynamic>> visibleWhen;

  const ForgeLogicDocument({
    this.derived = const {},
    this.visibleWhen = const {},
  });

  factory ForgeLogicDocument.fromJson(Object? raw) {
    if (raw == null) return const ForgeLogicDocument();
    if (raw is! Map<String, dynamic>) {
      throw const ForgeExpressionException('logic must be an object');
    }

    Map<String, Map<String, dynamic>> readExpressionMap(String key) {
      final value = raw[key];
      if (value == null) return const {};
      if (value is! Map<String, dynamic>) {
        throw ForgeExpressionException('logic.$key must be an object');
      }
      final result = <String, Map<String, dynamic>>{};
      for (final entry in value.entries) {
        if (entry.key.isEmpty || entry.value is! Map<String, dynamic>) {
          throw ForgeExpressionException('logic.$key entries must be named expression objects');
        }
        result[entry.key] = Map<String, dynamic>.from(entry.value as Map<String, dynamic>);
      }
      return result;
    }

    return ForgeLogicDocument(
      derived: readExpressionMap('derived'),
      visibleWhen: readExpressionMap('visible_when'),
    );
  }
}

/// Runtime view over a [ForgeLogicDocument]. Derived values are computed on
/// demand from current state and therefore never become a second mutable source
/// of truth.
class ForgeLogicRuntime {
  final ForgeRuntimeState state;
  final ForgeLogicDocument logic;

  const ForgeLogicRuntime({required this.state, required this.logic});

  dynamic readDerived(String key) {
    final expression = logic.derived[key];
    if (expression == null) {
      throw ForgeExpressionException('unknown derived value: $key');
    }
    return state.evaluateExpression(expression);
  }

  bool isVisible(String widgetId) {
    final expression = logic.visibleWhen[widgetId];
    if (expression == null) return true;
    return state.evaluateCondition(expression);
  }

  Map<String, dynamic> snapshotDerived() => {
        for (final entry in logic.derived.entries)
          entry.key: state.evaluateExpression(entry.value),
      };
}
