import 'package:flutter_test/flutter_test.dart';
import 'package:forge_app/json_ui/renderer/forge_runtime_state.dart';
import 'package:forge_app/json_ui/runtime/forge_expression.dart';
import 'package:forge_app/json_ui/runtime/forge_runtime_expression.dart';
import 'package:forge_app/json_ui/schema/forge_document.dart';

void main() {
  test('live state changes are reflected by derived expressions', () {
    final state = ForgeRuntimeState({
      'income': const ForgeNumberState(250000),
      'expense': const ForgeNumberState(180000),
    });

    final balance = <String, dynamic>{
      'kind': 'binary',
      'op': 'subtract',
      'left': {'kind': 'state', 'key': 'income'},
      'right': {'kind': 'state', 'key': 'expense'},
    };
    final isNegative = <String, dynamic>{
      'kind': 'binary',
      'op': 'lt',
      'left': balance,
      'right': {'kind': 'literal', 'value': 0},
    };

    expect(state.evaluateExpression(balance), 70000.0);
    expect(state.evaluateCondition(isNegative), isFalse);

    expect(state.write('expense', 300000), isTrue);
    expect(state.evaluateExpression(balance), -50000.0);
    expect(state.evaluateCondition(isNegative), isTrue);
  });

  test('condition binding rejects non-boolean expressions', () {
    final state = ForgeRuntimeState({
      'value': const ForgeNumberState(1),
    });

    expect(
      () => state.evaluateCondition({'kind': 'state', 'key': 'value'}),
      throwsA(isA<ForgeExpressionException>()),
    );
  });
}
