import 'package:flutter_test/flutter_test.dart';
import 'package:forge_app/json_ui/runtime/forge_expression.dart';

void main() {
  dynamic eval(Map<String, dynamic> expression, {Map<String, dynamic> state = const {}, List<Map<String, dynamic>> records = const []}) {
    return evaluateForgeExpression(
      expression,
      readState: (key) => state[key],
      readRecords: (_) => records,
    );
  }

  test('arithmetic composes state references', () {
    final value = eval(
      {
        'kind': 'binary',
        'op': 'subtract',
        'left': {'kind': 'state', 'key': 'income'},
        'right': {'kind': 'state', 'key': 'expense'},
      },
      state: {'income': 250000, 'expense': 180000},
    );

    expect(value, 70000.0);
  });

  test('comparison drives a negative-balance condition', () {
    final expression = {
      'kind': 'binary',
      'op': 'lt',
      'left': {
        'kind': 'binary',
        'op': 'subtract',
        'left': {'kind': 'state', 'key': 'income'},
        'right': {'kind': 'state', 'key': 'expense'},
      },
      'right': {'kind': 'literal', 'value': 0},
    };

    expect(eval(expression, state: {'income': 100, 'expense': 90}), isFalse);
    expect(eval(expression, state: {'income': 100, 'expense': 120}), isTrue);
  });

  test('aggregate sum is reusable across record domains', () {
    final value = eval(
      {'kind': 'aggregate', 'source': 'transactions', 'op': 'sum', 'field': 'amount'},
      records: [
        {'amount': 1200},
        {'amount': 800},
        {'amount': 3000},
      ],
    );

    expect(value, 5000.0);
  });

  test('boolean operators short circuit dead invalid branches', () {
    final value = eval({
      'kind': 'binary',
      'op': 'and',
      'left': {'kind': 'literal', 'value': false},
      'right': {
        'kind': 'binary',
        'op': 'divide',
        'left': {'kind': 'literal', 'value': 1},
        'right': {'kind': 'literal', 'value': 0},
      },
    });

    expect(value, isFalse);
  });

  test('division by zero fails closed', () {
    expect(
      () => eval({
        'kind': 'binary',
        'op': 'divide',
        'left': {'kind': 'literal', 'value': 10},
        'right': {'kind': 'literal', 'value': 0},
      }),
      throwsA(isA<ForgeExpressionException>()),
    );
  });

  test('unknown operations fail closed', () {
    expect(
      () => eval({
        'kind': 'binary',
        'op': 'execute_arbitrary_code',
        'left': {'kind': 'literal', 'value': 1},
        'right': {'kind': 'literal', 'value': 2},
      }),
      throwsA(isA<ForgeExpressionException>()),
    );
  });
}
