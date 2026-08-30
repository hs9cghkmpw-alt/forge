/// Pure deterministic expression engine for Forge General App Mode.
///
/// Expressions are data, not executable Dart. This keeps generated app logic
/// inspectable, serializable and fail-closed. The evaluator deliberately has no
/// IO, clock, randomness, network, device or navigation access.
library;

typedef ForgeStateReader = dynamic Function(String key);
typedef ForgeRecordReader = List<Map<String, dynamic>> Function(String key);

class ForgeExpressionException implements Exception {
  final String message;
  const ForgeExpressionException(this.message);

  @override
  String toString() => 'ForgeExpressionException: $message';
}

dynamic evaluateForgeExpression(
  Map<String, dynamic> expression, {
  required ForgeStateReader readState,
  required ForgeRecordReader readRecords,
}) {
  dynamic eval(Object? raw) {
    if (raw is! Map<String, dynamic>) {
      throw const ForgeExpressionException('expression node must be an object');
    }
    final kind = raw['kind'];
    if (kind is! String) {
      throw const ForgeExpressionException('expression.kind is required');
    }

    switch (kind) {
      case 'literal':
        return raw['value'];
      case 'state':
        final key = raw['key'];
        if (key is! String || key.isEmpty) {
          throw const ForgeExpressionException('state.key is required');
        }
        return readState(key);
      case 'unary':
        final op = raw['op'];
        final value = eval(raw['value']);
        return switch (op) {
          'not' => !_asBool(value, 'not'),
          'negate' => -_asNum(value, 'negate'),
          _ => throw ForgeExpressionException('unsupported unary op: $op'),
        };
      case 'binary':
        final op = raw['op'];
        // Short-circuit boolean operators so expressions are predictable and
        // invalid/dead branches cannot accidentally fail evaluation.
        if (op == 'and') {
          final left = _asBool(eval(raw['left']), 'and');
          return left ? _asBool(eval(raw['right']), 'and') : false;
        }
        if (op == 'or') {
          final left = _asBool(eval(raw['left']), 'or');
          return left ? true : _asBool(eval(raw['right']), 'or');
        }
        final left = eval(raw['left']);
        final right = eval(raw['right']);
        return _binary(op, left, right);
      case 'aggregate':
        return _aggregate(raw, eval, readRecords);
      default:
        throw ForgeExpressionException('unsupported expression kind: $kind');
    }
  }

  return eval(expression);
}

dynamic _binary(Object? op, dynamic left, dynamic right) {
  switch (op) {
    case 'add':
      return _asNum(left, 'add') + _asNum(right, 'add');
    case 'subtract':
      return _asNum(left, 'subtract') - _asNum(right, 'subtract');
    case 'multiply':
      return _asNum(left, 'multiply') * _asNum(right, 'multiply');
    case 'divide':
      final divisor = _asNum(right, 'divide');
      if (divisor == 0) {
        throw const ForgeExpressionException('division by zero');
      }
      return _asNum(left, 'divide') / divisor;
    case 'eq':
      return left == right;
    case 'neq':
      return left != right;
    case 'lt':
      return _compare(left, right, 'lt') < 0;
    case 'lte':
      return _compare(left, right, 'lte') <= 0;
    case 'gt':
      return _compare(left, right, 'gt') > 0;
    case 'gte':
      return _compare(left, right, 'gte') >= 0;
    default:
      throw ForgeExpressionException('unsupported binary op: $op');
  }
}

dynamic _aggregate(
  Map<String, dynamic> node,
  dynamic Function(Object? raw) eval,
  ForgeRecordReader readRecords,
) {
  final source = node['source'];
  final op = node['op'];
  if (source is! String || source.isEmpty) {
    throw const ForgeExpressionException('aggregate.source is required');
  }
  if (op is! String) {
    throw const ForgeExpressionException('aggregate.op is required');
  }

  Iterable<Map<String, dynamic>> records = readRecords(source);
  final where = node['where'];
  if (where != null) {
    if (where is! Map<String, dynamic>) {
      throw const ForgeExpressionException('aggregate.where must be an object');
    }
    records = records.where((record) {
      dynamic evalRecord(Object? raw) {
        if (raw is Map<String, dynamic> && raw['kind'] == 'field') {
          final field = raw['field'];
          if (field is! String || field.isEmpty) {
            throw const ForgeExpressionException('field.field is required');
          }
          return record[field];
        }
        if (raw is Map<String, dynamic>) {
          final rewritten = <String, dynamic>{};
          for (final entry in raw.entries) {
            final value = entry.value;
            rewritten[entry.key] = value is Map<String, dynamic> && value['kind'] == 'field'
                ? {'kind': 'literal', 'value': evalRecord(value)}
                : value;
          }
          return eval(rewritten);
        }
        return raw;
      }

      return _asBool(evalRecord(where), 'aggregate.where');
    });
  }

  final materialized = records.toList(growable: false);
  if (op == 'count') return materialized.length.toDouble();

  final field = node['field'];
  if (field is! String || field.isEmpty) {
    throw ForgeExpressionException('aggregate.$op requires field');
  }
  final values = materialized.map((record) => _asNum(record[field], 'aggregate.$op')).toList(growable: false);
  if (op == 'sum') return values.fold<double>(0, (sum, value) => sum + value);
  if (values.isEmpty) return 0.0;
  if (op == 'average') return values.fold<double>(0, (sum, value) => sum + value) / values.length;
  if (op == 'min') return values.reduce((a, b) => a < b ? a : b);
  if (op == 'max') return values.reduce((a, b) => a > b ? a : b);
  throw ForgeExpressionException('unsupported aggregate op: $op');
}

double _asNum(dynamic value, String op) {
  if (value is num) return value.toDouble();
  throw ForgeExpressionException('$op requires numeric operands');
}

bool _asBool(dynamic value, String op) {
  if (value is bool) return value;
  throw ForgeExpressionException('$op requires boolean operands');
}

int _compare(dynamic left, dynamic right, String op) {
  if (left is num && right is num) return left.toDouble().compareTo(right.toDouble());
  if (left is String && right is String) return left.compareTo(right);
  throw ForgeExpressionException('$op requires two numbers or two strings');
}
