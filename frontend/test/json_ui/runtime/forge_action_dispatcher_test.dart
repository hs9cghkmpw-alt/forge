// ForgeActionDispatcher Unit Test(FORGE-MILESTONE-003)。
//
// 指示書5章「Action Dispatcher」の項目を網羅する: set_state成功・
// toggle_state成功・reset_state成功・navigate成功・submit_form成功・
// submit_form検証失敗・composite順次実行・composite途中失敗・未知Action・
// 不正なstate_ref・不正なtarget・再帰上限。
//
// 注記: Claudeのサンドボックスに Dart SDK が無いため、このファイルは
// 一度も `flutter test` で実行されていない。CEO環境での実行が必須。

import 'package:flutter_test/flutter_test.dart';
import 'package:forge_app/json_ui/runtime/forge_action_dispatcher.dart';
import 'package:forge_app/json_ui/runtime/forge_state_store.dart';
import 'package:forge_app/json_ui/schema/forge_document.dart';

void main() {
  test('set_state成功', () {
    final store = ForgeStateStore({'name': const ForgeStringState('')});
    final dispatcher = ForgeActionDispatcher(store: store);
    final result = dispatcher.execute(const SetValueAction('name', '花子'));
    expect(result.success, isTrue);
    expect(store.read('name'), '花子');
  });

  test('toggle_state成功', () {
    final store = ForgeStateStore({'agreed': const ForgeBooleanState(false)});
    final dispatcher = ForgeActionDispatcher(store: store);
    final result = dispatcher.execute(const ToggleStateAction('agreed'));
    expect(result.success, isTrue);
    expect(store.read('agreed'), true);
  });

  test('reset_state成功', () {
    final store = ForgeStateStore({'note': const ForgeStringState('初期')});
    store.write('note', '変更後');
    final dispatcher = ForgeActionDispatcher(store: store);
    final result = dispatcher.execute(const ResetStateAction('note'));
    expect(result.success, isTrue);
    expect(store.read('note'), '初期');
  });

  test('navigate成功: onNavigationActionへ委譲される', () {
    final store = ForgeStateStore(<String, ForgeStateValue>{});
    ForgeAction? captured;
    final dispatcher = ForgeActionDispatcher(store: store, onNavigationAction: (a) => captured = a);
    final result = dispatcher.execute(const NavigateAction('next_screen'));
    expect(result.success, isTrue);
    expect(captured, isA<NavigateAction>());
    expect((captured as NavigateAction).targetScreenId, 'next_screen');
  });

  group('submit_form', () {
    ForgeFormWidgetNode buildForm({List<ForgeValidationRule>? rules}) {
      return ForgeFormWidgetNode(
        'my_form',
        children: [
          ForgeTextFieldWidgetNode('name_field', stateRef: 'name', validationRules: rules),
        ],
        submitLabel: '送信',
        submitAction: const NavigateAction('thanks_screen'),
      );
    }

    test('submit_form成功: 検証を通過するとsuccess_actionが実行される', () {
      final store = ForgeStateStore({'name': const ForgeStringState('入力済み')});
      final form = buildForm(rules: const [
        ForgeValidationRule(type: 'required', value: null, message: '必須です'),
      ]);
      ForgeAction? captured;
      final dispatcher = ForgeActionDispatcher(
        store: store,
        onNavigationAction: (a) => captured = a,
        screenLookup: (id) => id == 'my_form' ? form : null,
      );
      final result = dispatcher.execute(
        SubmitFormAction(formRef: 'my_form', successAction: form.submitAction),
      );
      expect(result.success, isTrue);
      expect(captured, isA<NavigateAction>(), reason: 'success_action(navigate)が実行されたはず');
    });

    test('submit_form検証失敗: requiredルールに違反すると失敗し、success_actionは実行されない', () {
      final store = ForgeStateStore({'name': const ForgeStringState('')}); // 空
      final form = buildForm(rules: const [
        ForgeValidationRule(type: 'required', value: null, message: '名前が必須です'),
      ]);
      ForgeAction? captured;
      final dispatcher = ForgeActionDispatcher(
        store: store,
        onNavigationAction: (a) => captured = a,
        screenLookup: (id) => id == 'my_form' ? form : null,
      );
      final result = dispatcher.execute(
        SubmitFormAction(formRef: 'my_form', successAction: form.submitAction),
      );
      expect(result.success, isFalse);
      expect(result.validationErrors, {'name': '名前が必須です'});
      expect(captured, isNull, reason: '検証失敗時はsuccess_actionを実行してはならない');
    });

    test('submit_form: form_refが見つからない場合は失敗する', () {
      final store = ForgeStateStore(<String, ForgeStateValue>{});
      final dispatcher = ForgeActionDispatcher(store: store, screenLookup: (_) => null);
      final result = dispatcher.execute(
        const SubmitFormAction(formRef: 'nonexistent', successAction: GoBackAction()),
      );
      expect(result.success, isFalse);
      expect(result.reason, 'form_not_found');
    });
  });

  group('composite', () {
    test('composite順次実行: 複数Actionが順番に実行される', () {
      final store = ForgeStateStore({
        'a': const ForgeStringState(''),
        'b': const ForgeBooleanState(false),
      });
      final dispatcher = ForgeActionDispatcher(store: store);
      final result = dispatcher.execute(const CompositeAction([
        SetValueAction('a', 'set済み'),
        ToggleStateAction('b'),
      ]));
      expect(result.success, isTrue);
      expect(store.read('a'), 'set済み');
      expect(store.read('b'), true);
    });

    test('composite途中失敗: 途中のstepが失敗すると、以降のstepは実行されない', () {
      final store = ForgeStateStore({
        'a': const ForgeStringState(''),
        'b': const ForgeStringState(''),
      });
      final dispatcher = ForgeActionDispatcher(store: store);
      final result = dispatcher.execute(const CompositeAction([
        SetValueAction('a', '1つ目は成功'),
        ToggleStateAction('does_not_exist'), // ここで失敗する(存在しない・boolean型でもない)
        SetValueAction('b', '3つ目は実行されないはず'),
      ]));
      expect(result.success, isFalse);
      expect(store.read('a'), '1つ目は成功', reason: '失敗より前のstepの結果は残る(ロールバックしない)');
      expect(store.read('b'), '', reason: '失敗より後のstepは実行されない');
    });

    test('再帰上限: ネストがmaxCompositeDepthを超えると失敗する', () {
      final store = ForgeStateStore(<String, ForgeStateValue>{});
      final dispatcher = ForgeActionDispatcher(store: store, onNavigationAction: (_) {});
      // maxCompositeDepth(3)を超える4段ネスト。
      const action = CompositeAction([
        CompositeAction([
          CompositeAction([
            CompositeAction([GoBackAction()]),
          ]),
        ]),
      ]);
      final result = dispatcher.execute(action);
      expect(result.success, isFalse);
    });

    test('ちょうど上限(3段)のネストは成功する', () {
      final store = ForgeStateStore(<String, ForgeStateValue>{});
      var navigated = false;
      final dispatcher = ForgeActionDispatcher(store: store, onNavigationAction: (_) => navigated = true);
      const action = CompositeAction([
        CompositeAction([
          CompositeAction([GoBackAction()]),
        ]),
      ]);
      final result = dispatcher.execute(action);
      expect(result.success, isTrue);
      expect(navigated, isTrue);
    });
  });

  test('不正なstate_ref: 存在しないstateへのtoggle_stateは失敗する', () {
    final store = ForgeStateStore(<String, ForgeStateValue>{});
    final dispatcher = ForgeActionDispatcher(store: store);
    final result = dispatcher.execute(const ToggleStateAction('does_not_exist'));
    expect(result.success, isFalse);
    expect(result.reason, 'state_reference_invalid');
  });

  test('不正なtarget: add_itemでtarget/sourceの型が合わないと失敗する', () {
    final store = ForgeStateStore({
      'items': const ForgeStringState('checklistではない'), // 型が違う
      'source': const ForgeStringState('x'),
    });
    final dispatcher = ForgeActionDispatcher(store: store);
    final result = dispatcher.execute(
      const AddItemAction(targetStateRef: 'items', sourceStateRef: 'source'),
    );
    expect(result.success, isFalse);
  });

  // FORGE-MILESTONE-003.1 PHASE1/2/5: CEO実機で発見された add_item_failed の
  // Dispatcherレベルでの回帰テスト。「何も入力せず追加ボタンを押した」は
  // 正常な操作であり、Actionとしては成功扱いになり、診断ログ(ERROR)も
  // 出ないべきである。
  test('sourceが空文字のadd_itemは成功扱いになり、診断ログも出ない(正常操作)', () {
    final store = ForgeStateStore({
      'items': const ForgeChecklistState([]),
      'new_item_text': const ForgeStringState(''),
    });
    final diagnostics = <String>[];
    final dispatcher = ForgeActionDispatcher(
      store: store,
      onDiagnostic: (category, message) => diagnostics.add(category),
    );
    final result = dispatcher.execute(
      const AddItemAction(targetStateRef: 'items', sourceStateRef: 'new_item_text'),
    );
    expect(result.success, isTrue, reason: '空入力での追加操作はエラーではない');
    expect(diagnostics, isEmpty, reason: '正常操作なのでERRORログは出ないはず');
    expect(store.readChecklist('items'), isEmpty, reason: '何も追加されない');
  });

  test('診断ログ: 失敗時にonDiagnosticが呼ばれる', () {
    final store = ForgeStateStore(<String, ForgeStateValue>{});
    final diagnostics = <String>[];
    final dispatcher = ForgeActionDispatcher(
      store: store,
      onDiagnostic: (category, message) => diagnostics.add(category),
    );
    dispatcher.execute(const ToggleStateAction('missing'));
    expect(diagnostics, contains('state_reference_invalid'));
  });
}
