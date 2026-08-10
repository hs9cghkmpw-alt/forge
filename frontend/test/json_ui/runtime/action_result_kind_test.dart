// ActionResultKind統一契約のテスト(FORGE-MILESTONE-003.1、CEOレビュー対応)。
//
// CEOレビュー:「AddChecklistItemOutcomeだけが特別扱いになっている。
// ActionResultへ統一したい」への対応。add_item専用の結果種別
// (AddChecklistItemOutcome)を廃止するのではなく、Dispatcher層で必ず
// 共通のActionResultKindへ変換されることを、全Action種別について
// 明示的に検証する。
//
// 既存の`forge_action_dispatcher_test.dart`は`success`/`reason`という
// 元々のフィールドだけを見ており、無改変のまま合格し続ける
// (このファイルは`kind`という新フィールドの検証に特化した追加テスト)。
//
// 注記: Claudeのサンドボックスに Dart SDK が無いため、このファイルは
// 一度も `flutter test` で実行されていない。CEO環境での実行が必須。

import 'package:flutter_test/flutter_test.dart';
import 'package:forge_app/json_ui/runtime/forge_action_dispatcher.dart';
import 'package:forge_app/json_ui/runtime/forge_state_store.dart';
import 'package:forge_app/json_ui/schema/forge_document.dart';

ForgeStateStore _storeWith(Map<String, ForgeStateValue> values) => ForgeStateStore(values);

void main() {
  group('ActionResultKind: 正常系はsuccess', () {
    test('navigate', () {
      final dispatcher = ForgeActionDispatcher(store: _storeWith(const {}));
      final result = dispatcher.execute(const NavigateAction('s2'));
      expect(result.kind, ActionResultKind.success);
      expect(result.success, isTrue);
    });

    test('go_back', () {
      final dispatcher = ForgeActionDispatcher(store: _storeWith(const {}));
      final result = dispatcher.execute(const GoBackAction());
      expect(result.kind, ActionResultKind.success);
    });

    test('set_value(有効なstate_ref)', () {
      final dispatcher = ForgeActionDispatcher(
        store: _storeWith({'name': const ForgeStringState('')}),
      );
      final result = dispatcher.execute(const SetValueAction('name', 'Yuta'));
      expect(result.kind, ActionResultKind.success);
    });

    test('toggle_state(有効なboolean state_ref)', () {
      final dispatcher = ForgeActionDispatcher(
        store: _storeWith({'flag': const ForgeBooleanState(false)}),
      );
      final result = dispatcher.execute(const ToggleStateAction('flag'));
      expect(result.kind, ActionResultKind.success);
    });

    test('reset_state(有効なstate_ref)', () {
      final dispatcher = ForgeActionDispatcher(
        store: _storeWith({'name': const ForgeStringState('初期値')}),
      );
      final result = dispatcher.execute(const ResetStateAction('name'));
      expect(result.kind, ActionResultKind.success);
    });

    test('add_item(有効な入力)', () {
      final dispatcher = ForgeActionDispatcher(
        store: _storeWith({
          'items': const ForgeChecklistState([]),
          'new_item_text': const ForgeStringState('牛乳'),
        }),
      );
      final result = dispatcher.execute(
        const AddItemAction(targetStateRef: 'items', sourceStateRef: 'new_item_text'),
      );
      expect(result.kind, ActionResultKind.success);
    });
  });

  group('ActionResultKind: 正常だが何もしないケースはnoOp(successはtrueのまま)', () {
    test('add_item(空入力)', () {
      final dispatcher = ForgeActionDispatcher(
        store: _storeWith({
          'items': const ForgeChecklistState([]),
          'new_item_text': const ForgeStringState(''),
        }),
      );
      final result = dispatcher.execute(
        const AddItemAction(targetStateRef: 'items', sourceStateRef: 'new_item_text'),
      );
      expect(result.kind, ActionResultKind.noOp);
      expect(result.success, isTrue, reason: 'noOpはエラーではない');
    });
  });

  group('ActionResultKind: target系の契約違反はinvalidTarget', () {
    test('set_value(存在しないstate_ref)', () {
      final dispatcher = ForgeActionDispatcher(store: _storeWith(const {}));
      final result = dispatcher.execute(const SetValueAction('does_not_exist', 'x'));
      expect(result.kind, ActionResultKind.invalidTarget);
      expect(result.success, isFalse);
    });

    test('add_item(targetがchecklist型ではない)', () {
      final dispatcher = ForgeActionDispatcher(
        store: _storeWith({
          'items': const ForgeStringState('checklistではない'),
          'new_item_text': const ForgeStringState('牛乳'),
        }),
      );
      final result = dispatcher.execute(
        const AddItemAction(targetStateRef: 'items', sourceStateRef: 'new_item_text'),
      );
      expect(result.kind, ActionResultKind.invalidTarget);
    });

    test('toggle_state(state_refがboolean型ではない)', () {
      final dispatcher = ForgeActionDispatcher(
        store: _storeWith({'flag': const ForgeStringState('boolじゃない')}),
      );
      final result = dispatcher.execute(const ToggleStateAction('flag'));
      expect(result.kind, ActionResultKind.invalidTarget);
    });

    test('reset_state(存在しないstate_ref)', () {
      final dispatcher = ForgeActionDispatcher(store: _storeWith(const {}));
      final result = dispatcher.execute(const ResetStateAction('does_not_exist'));
      expect(result.kind, ActionResultKind.invalidTarget);
    });

    test('submit_form(form_refが見つからない)', () {
      final dispatcher = ForgeActionDispatcher(store: _storeWith(const {}), screenLookup: (_) => null);
      final result = dispatcher.execute(
        const SubmitFormAction(formRef: 'nope', successAction: GoBackAction()),
      );
      expect(result.kind, ActionResultKind.invalidTarget);
    });
  });

  group('ActionResultKind: source系の契約違反はinvalidSource', () {
    test('add_item(sourceがstring型ではない)', () {
      final dispatcher = ForgeActionDispatcher(
        store: _storeWith({
          'items': const ForgeChecklistState([]),
          'new_item_text': const ForgeBooleanState(true),
        }),
      );
      final result = dispatcher.execute(
        const AddItemAction(targetStateRef: 'items', sourceStateRef: 'new_item_text'),
      );
      expect(result.kind, ActionResultKind.invalidSource);
    });
  });

  group('ActionResultKind: composite/runtimeErrorの伝播', () {
    test('composite再帰上限超過はruntimeError', () {
      final dispatcher = ForgeActionDispatcher(store: _storeWith(const {}));
      // depthを直接maxCompositeDepth以上にして呼ぶことはpublic APIから
      // できないため、実際にネストしたcomposite Actionを組み立てて超過させる。
      ForgeAction action = const GoBackAction();
      for (var i = 0; i < ForgeActionDispatcher.maxCompositeDepth + 1; i++) {
        action = CompositeAction([action]);
      }
      final result = dispatcher.execute(action);
      expect(result.kind, ActionResultKind.runtimeError);
    });

    test('compositeは内側で失敗したActionのkindをそのまま伝播する', () {
      final dispatcher = ForgeActionDispatcher(store: _storeWith(const {}));
      final result = dispatcher.execute(
        const CompositeAction([SetValueAction('does_not_exist', 'x')]),
      );
      // 一律runtimeErrorにせず、内側(set_value)の実際のkindを反映する。
      expect(result.kind, ActionResultKind.invalidTarget);
    });
  });
}
