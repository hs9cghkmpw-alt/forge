import 'package:flutter_test/flutter_test.dart';
import 'package:forge_app/json_ui/renderer/forge_runtime_state.dart';
import 'package:forge_app/json_ui/runtime/forge_expression.dart';
import 'package:forge_app/json_ui/runtime/forge_logic_document.dart';
import 'package:forge_app/json_ui/schema/forge_document.dart';

void main() {
  test('derived values stay live and conditional visibility follows current state', () {
    final state = ForgeRuntimeState({
      'income': const ForgeNumberState(250000),
      'expense': const ForgeNumberState(180000),
    });

    final logic = ForgeLogicDocument.fromJson({
      'derived': {
        'balance': {
          'kind': 'binary',
          'op': 'subtract',
          'left': {'kind': 'state', 'key': 'income'},
          'right': {'kind': 'state', 'key': 'expense'},
        },
      },
      'visible_when': {
        'deficit_warning': {
          'kind': 'binary',
          'op': 'gt',
          'left': {'kind': 'state', 'key': 'expense'},
          'right': {'kind': 'state', 'key': 'income'},
        },
      },
    });

    final runtime = ForgeLogicRuntime(state: state, logic: logic);
    expect(runtime.readDerived('balance'), 70000.0);
    expect(runtime.isVisible('deficit_warning'), isFalse);

    expect(state.write('expense', 300000), isTrue);
    expect(runtime.readDerived('balance'), -50000.0);
    expect(runtime.isVisible('deficit_warning'), isTrue);
  });

  test('missing visibility condition defaults visible but unknown derived fails closed', () {
    final runtime = ForgeLogicRuntime(
      state: ForgeRuntimeState({'value': const ForgeNumberState(1)}),
      logic: const ForgeLogicDocument(),
    );
    expect(runtime.isVisible('ordinary_widget'), isTrue);
    expect(
      () => runtime.readDerived('missing'),
      throwsA(isA<ForgeExpressionException>()),
    );
  });

  test('logic parser rejects malformed expression maps', () {
    expect(
      () => ForgeLogicDocument.fromJson({'derived': <dynamic>[]}),
      throwsA(isA<ForgeExpressionException>()),
    );
    expect(
      () => ForgeLogicDocument.fromJson({
        'visible_when': {'widget': 1},
      }),
      throwsA(isA<ForgeExpressionException>()),
    );
  });
}
