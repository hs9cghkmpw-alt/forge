import '../schema/forge_document.dart';
import 'forge_form_validator.dart';
import 'forge_state_store.dart';

/// Action実行結果の種別(FORGE-MILESTONE-003.1で導入)。
///
/// 個別のAction(add_item専用の`AddChecklistItemOutcome`等)がそれぞれ
/// バラバラな成功/失敗の語彙を持つのではなく、全Actionが最終的に
/// この共通のenumへ収束するようにした(CEOレビュー「Runtime契約が
/// 弱い」への対応)。`ForgeStateStore.addChecklistItem()`が返す
/// `AddChecklistItemOutcome`は、Store層固有の詳細(どのフィールドが
/// 問題か)を保持したまま、Dispatcher層でこの共通enumへ変換される
/// (Store側の型を廃止したわけではなく、「Store→Dispatcherの橋渡しで
/// 必ずこの共通enumに変換する」というルールを追加した)。
enum ActionResultKind {
  /// Actionが意図通りに完了した。
  success,

  /// 何も起こらなかったが、契約違反ではない(例: 空入力のまま追加ボタンを
  /// 押した)。呼び出し元が`result.success`だけを見た場合でも、正常な
  /// 「何もしなかった」ケースを誤ってエラー扱いしないよう、`success`は
  /// `true`のままにする(下記`ActionResult.success`ゲッター参照)。
  noOp,

  /// target(書き込み/参照先)のStateが存在しない、または型が違う。
  invalidTarget,

  /// source(読み取り元)のStateが存在しない、または型が違う。
  invalidSource,

  /// Form Validationに失敗した(`validationErrors`に詳細が入る)。
  validationError,

  /// 上記いずれにも当てはまらない実行時エラー(未知Action、
  /// composite再帰上限超過等)。
  runtimeError,
}

/// Action実行結果(FORGE-MILESTONE-003 Task 4、FORGE-MILESTONE-003.1で
/// `kind`を追加して拡張)。呼び出し元(Widget Builder等)が成功/失敗を
/// 判定できるようにする。
///
/// 後方互換性: `success`(bool)・`reason`(String?)・`validationErrors`は
/// FORGE-MILESTONE-003から存在するフィールドであり、既存のテスト
/// (`forge_action_dispatcher_test.dart`等)が具体的な`reason`文字列
/// (例: `'form_not_found'`)を検証しているため、既存の文字列値・意味は
/// 一切変更していない。`kind`は追加のフィールドであり、新しいコードは
/// こちらを使うことを推奨する。
class ActionResult {
  final bool success;
  final String? reason;
  final ActionResultKind kind;

  /// submit_form失敗時、どのフィールドがどう失敗したか(state_ref -> message)。
  final Map<String, String>? validationErrors;

  const ActionResult._({
    required this.success,
    required this.kind,
    this.reason,
    this.validationErrors,
  });

  factory ActionResult.success() =>
      const ActionResult._(success: true, kind: ActionResultKind.success);

  /// 何も起こらなかったが正常(契約違反ではない)。`success`は`true`のまま
  /// (エラーではないことを、既存のbool判定コードにもそのまま伝えるため)。
  factory ActionResult.noOp(String reason) =>
      ActionResult._(success: true, kind: ActionResultKind.noOp, reason: reason);

  /// 既定の`kind`は`runtimeError`(呼び出し元が明示的に指定しなければ
  /// 「その他の実行時エラー」として扱う、安全側のデフォルト)。
  factory ActionResult.failure(
    String reason, {
    Map<String, String>? validationErrors,
    ActionResultKind kind = ActionResultKind.runtimeError,
  }) =>
      ActionResult._(success: false, kind: kind, reason: reason, validationErrors: validationErrors);
}

/// 開発時診断ログの1件(FORGE-MILESTONE-003 Task 7)。
typedef ForgeDiagnosticSink = void Function(String category, String message);

/// すべてのActionを一元的に処理するAction Dispatcher(FORGE-MILESTONE-003 Task 4)。
///
/// Widget Builderは`store.dispatch(action)`(旧来通り)または
/// `ForgeActionDispatcher.execute(action)`のいずれを呼んでもよい設計にし、
/// Action種別ごとのif/switch分岐をWidget Builderへ書かせない。
///
/// 依存方向を守るため、[screenLookup]は「idからWidgetNodeを引く関数」という
/// 抽象化のみを受け取り、特定の画面・生成テンプレートを知らない。
class ForgeActionDispatcher {
  final ForgeStateStore store;
  final ForgeFormValidator validator;
  final void Function(ForgeAction navigationAction)? onNavigationAction;
  final ForgeWidgetNode? Function(String widgetId)? screenLookup;
  final ForgeDiagnosticSink? onDiagnostic;

  static const int maxCompositeDepth = 3;

  const ForgeActionDispatcher({
    required this.store,
    this.validator = const ForgeFormValidator(),
    this.onNavigationAction,
    this.screenLookup,
    this.onDiagnostic,
  });

  ActionResult execute(ForgeAction action, {int depth = 0}) {
    if (action is NavigateAction) {
      onNavigationAction?.call(action);
      return ActionResult.success();
    }
    if (action is GoBackAction) {
      onNavigationAction?.call(action);
      return ActionResult.success();
    }
    if (action is SetValueAction) {
      final ok = store.write(action.stateRef, action.value);
      if (!ok) {
        _diagnose('state_type_mismatch', 'set_state/set_value: "${action.stateRef}" への書き込みに失敗しました'
            '(既存の型と一致しない値、または未対応の型です)。');
        return ActionResult.failure('state_type_mismatch', kind: ActionResultKind.invalidTarget);
      }
      return ActionResult.success();
    }
    if (action is AddItemAction) {
      final outcome = store.addChecklistItem(action.targetStateRef, action.sourceStateRef);
      switch (outcome) {
        case AddChecklistItemOutcome.added:
          return ActionResult.success();
        case AddChecklistItemOutcome.emptySource:
          // FORGE-MILESTONE-003.1 PHASE2で修正: ユーザーが何も入力せず
          // 追加ボタンを押しただけの、完全に正常な操作。契約違反ではないため
          // ERRORログを出さず、noOpとして扱う(successはtrueのまま)。
          return ActionResult.noOp('add_item_empty_source');
        case AddChecklistItemOutcome.targetMissing:
          _diagnose('add_item_failed',
              'add_item: target="${action.targetStateRef}" がchecklist型のstateとして'
              '存在しません(AI生成JSONの契約違反の可能性があります)。');
          return ActionResult.failure('add_item_target_missing', kind: ActionResultKind.invalidTarget);
        case AddChecklistItemOutcome.sourceMissing:
          _diagnose('add_item_failed',
              'add_item: source="${action.sourceStateRef}" がstring型のstateとして'
              '存在しません(AI生成JSONの契約違反の可能性があります)。');
          return ActionResult.failure('add_item_source_missing', kind: ActionResultKind.invalidSource);
      }
    }
    if (action is AddRecordAction) {
      // FORGE v0.7新規(Record Runtime Phase1)。`add_record`は常に
      // `form.submit_action`経由(=`SubmitFormAction`によるValidation済み)
      // で呼ばれる設計のため、`AddChecklistItemOutcome.emptySource`に
      // 相当する「正常なnoOp」ケースは無い(`ForgeStateStore.addRecord`の
      // docコメント参照)。
      final outcome = store.addRecord(action.targetStateRef, action.fieldBindings);
      switch (outcome) {
        case AddRecordOutcome.added:
          return ActionResult.success();
        case AddRecordOutcome.targetMissing:
          _diagnose('add_record_failed',
              'add_record: target="${action.targetStateRef}" がrecord_list型のstateとして'
              '存在しません(AI生成JSONの契約違反の可能性があります)。');
          return ActionResult.failure('add_record_target_missing', kind: ActionResultKind.invalidTarget);
        case AddRecordOutcome.sourceMissing:
          _diagnose('add_record_failed',
              'add_record: field_bindings="${action.fieldBindings}" の参照先が、string/number/boolean型の'
              'stateとして存在しません(AI生成JSONの契約違反の可能性があります)。');
          return ActionResult.failure('add_record_source_missing', kind: ActionResultKind.invalidSource);
        case AddRecordOutcome.validationFailed:
          // FORGE v1.0新規(Workstream E)。契約違反ではなく、多くの
          // 場合ユーザーの入力ミス(数値/日付の書式不正・choice範囲外
          // 等)。`submit_form`の既存Validation失敗と同じ経路
          // (`ActionResult.validationErrors`)でWidget付近にエラー
          // 表示させる。
          return ActionResult.failure(
            'add_record_validation_failed',
            kind: ActionResultKind.invalidSource,
            validationErrors: _translateFieldErrors(store.lastFieldErrors, action.fieldBindings),
          );
      }
    }
    if (action is SelectRecordAction) {
      // FORGE v0.8新規(Record Runtime Phase2)。`record_id`は空文字列の
      // まま到達しないはず(`widget_registry_v1_3.dart`が必ず
      // `withRecordId()`で実際のidへ差し替えてから`dispatch()`する)。
      // 万一空のまま呼ばれた場合も、`recordNotFound`として安全に失敗する
      // (`selectRecord`は空文字列のidと一致するRecordを通常持たない)。
      //
      // FORGE v0.8.1(Hardening)対応: `selectRecord`は現在、
      // `fieldBindings`を全件事前検証してから一括反映するAtomicな
      // 実装になっている(`forge_state_store.dart`参照)。1件でも
      // 無効なら`invalidBinding`を返し、Stateは一切変更されない。
      final outcome = store.selectRecord(
        action.sourceStateRef, action.targetStateRef, action.recordId, action.fieldBindings,
      );
      switch (outcome) {
        case RecordOperationOutcome.success:
          return ActionResult.success();
        case RecordOperationOutcome.targetStateNotFound:
          _diagnose('select_record_failed',
              'select_record: source="${action.sourceStateRef}"またはtarget="${action.targetStateRef}"が'
              'Store内に存在しません(AI生成JSONの契約違反の可能性があります)。');
          return ActionResult.failure('select_record_target_state_not_found', kind: ActionResultKind.invalidTarget);
        case RecordOperationOutcome.targetStateTypeMismatch:
          _diagnose('select_record_failed',
              'select_record: source="${action.sourceStateRef}"がrecord_list型、'
              'target="${action.targetStateRef}"がselected_record型である必要がありますが、型が一致しません'
              '(AI生成JSONの契約違反の可能性があります)。');
          return ActionResult.failure('select_record_target_state_type_mismatch', kind: ActionResultKind.invalidTarget);
        case RecordOperationOutcome.recordNotFound:
          _diagnose('select_record_failed',
              'select_record: id="${action.recordId}" のRecordが"${action.sourceStateRef}"に見つかりません'
              '(表示直後に他の操作で削除された可能性があります)。');
          return ActionResult.failure('select_record_not_found', kind: ActionResultKind.invalidSource);
        case RecordOperationOutcome.invalidBinding:
          _diagnose('select_record_failed',
              'select_record: field_bindings="${action.fieldBindings}"の一部が無効です'
              '(選択対象のRecordに存在しないField、または書き込み先がstring型のstateでない可能性があります。'
              'AI生成JSONの契約違反の可能性があります)。選択は行われませんでした(Atomicity保証)。');
          return ActionResult.failure('select_record_invalid_binding', kind: ActionResultKind.invalidSource);
        case RecordOperationOutcome.noSelection:
          // selectRecordはこの値を返さない(到達しない、switchの網羅性のため残す)。
          return ActionResult.noOp('select_record_unexpected_no_selection');
      }
    }
    if (action is UpdateRecordAction) {
      // FORGE v0.8.1(Hardening)対応: 更新成功時、`selected_record`の
      // キャッシュも同時に最新化される(`forge_state_store.dart`
      // 参照)。これにより、更新直後は一覧とselected_recordの内容が
      // 必ず一致する。
      final outcome = store.updateRecord(action.targetStateRef, action.recordIdRef, action.fieldBindings);
      switch (outcome) {
        case RecordOperationOutcome.success:
          return ActionResult.success();
        case RecordOperationOutcome.targetStateNotFound:
          _diagnose('update_record_failed',
              'update_record: target="${action.targetStateRef}"またはrecord_id_ref='
              '"${action.recordIdRef}"がStore内に存在しません(AI生成JSONの契約違反の可能性があります)。');
          return ActionResult.failure('update_record_target_state_not_found', kind: ActionResultKind.invalidTarget);
        case RecordOperationOutcome.targetStateTypeMismatch:
          _diagnose('update_record_failed',
              'update_record: target="${action.targetStateRef}"またはrecord_id_ref='
              '"${action.recordIdRef}"の型が不正です(AI生成JSONの契約違反の可能性があります)。');
          return ActionResult.failure('update_record_target_state_type_mismatch', kind: ActionResultKind.invalidTarget);
        case RecordOperationOutcome.invalidBinding:
          if (store.lastFieldErrors.isNotEmpty) {
            // FORGE v1.0新規(Workstream E): Schema型検証の失敗
            // (契約違反ではなく、多くはユーザーの入力ミス)。
            return ActionResult.failure(
              'update_record_validation_failed',
              kind: ActionResultKind.invalidSource,
              validationErrors: _translateFieldErrors(store.lastFieldErrors, action.fieldBindings),
            );
          }
          _diagnose('update_record_failed',
              'update_record: field_bindings="${action.fieldBindings}" の参照先が、string/number/boolean型の'
              'stateとして存在しません(AI生成JSONの契約違反の可能性があります)。');
          return ActionResult.failure('update_record_invalid_binding', kind: ActionResultKind.invalidSource);
        case RecordOperationOutcome.noSelection:
          // 正常操作: 何も選択されていない状態で更新ボタンが押された
          // (UIが無効化し損ねた場合)。契約違反ではないためnoOpとして扱う。
          return ActionResult.noOp('update_record_no_selection');
        case RecordOperationOutcome.recordNotFound:
          _diagnose('update_record_failed',
              'update_record: 選択中のRecordが"${action.targetStateRef}"に見つかりません'
              '(表示直後に他の操作で削除された可能性があります)。');
          return ActionResult.failure('update_record_not_found', kind: ActionResultKind.invalidTarget);
      }
    }
    if (action is DeleteRecordAction) {
      // FORGE v0.8.1(Hardening)対応: 削除成功時、`selected_record`は
      // 必ず`null`へ解除される(`forge_state_store.dart`参照)。
      // 削除済みRecordを指したままのselected_recordが残ることはない。
      final outcome = store.deleteRecord(action.targetStateRef, action.recordIdRef);
      switch (outcome) {
        case RecordOperationOutcome.success:
          return ActionResult.success();
        case RecordOperationOutcome.targetStateNotFound:
          _diagnose('delete_record_failed',
              'delete_record: target="${action.targetStateRef}"またはrecord_id_ref='
              '"${action.recordIdRef}"がStore内に存在しません(AI生成JSONの契約違反の可能性があります)。');
          return ActionResult.failure('delete_record_target_state_not_found', kind: ActionResultKind.invalidTarget);
        case RecordOperationOutcome.targetStateTypeMismatch:
          _diagnose('delete_record_failed',
              'delete_record: target="${action.targetStateRef}"またはrecord_id_ref='
              '"${action.recordIdRef}"の型が不正です(AI生成JSONの契約違反の可能性があります)。');
          return ActionResult.failure('delete_record_target_state_type_mismatch', kind: ActionResultKind.invalidTarget);
        case RecordOperationOutcome.noSelection:
          return ActionResult.noOp('delete_record_no_selection');
        case RecordOperationOutcome.recordNotFound:
          _diagnose('delete_record_failed',
              'delete_record: 選択中のRecordが"${action.targetStateRef}"に見つかりません'
              '(既に削除済みの可能性があります)。');
          return ActionResult.failure('delete_record_not_found', kind: ActionResultKind.invalidTarget);
        case RecordOperationOutcome.invalidBinding:
          // deleteRecordはこの値を返さない(到達しない、switchの網羅性のため残す)。
          return ActionResult.noOp('delete_record_unexpected_invalid_binding');
      }
    }
    if (action is ToggleStateAction) {
      final ok = store.toggleBoolean(action.stateRef);
      if (!ok) {
        _diagnose('state_reference_invalid',
            'toggle_state: "${action.stateRef}" はboolean型のstateではありません。');
        return ActionResult.failure('state_reference_invalid', kind: ActionResultKind.invalidTarget);
      }
      return ActionResult.success();
    }
    if (action is ResetStateAction) {
      final ok = store.reset(action.stateRef);
      if (!ok) {
        _diagnose('state_reference_invalid', 'reset_state: "${action.stateRef}" が見つかりません。');
        return ActionResult.failure('state_reference_invalid', kind: ActionResultKind.invalidTarget);
      }
      return ActionResult.success();
    }
    if (action is SubmitFormAction) {
      return _executeSubmitForm(action, depth);
    }
    if (action is CompositeAction) {
      return _executeComposite(action, depth);
    }
    // ここには到達しないはず(sealed classなのでコンパイラが網羅性を検査する)。
    // ただし将来Action型が増えた際の多重防御として残す。
    _diagnose('unknown_action', 'Dispatcherが処理できないAction型です: ${action.runtimeType}');
    return ActionResult.failure('unknown_action', kind: ActionResultKind.runtimeError);
  }

  ActionResult _executeSubmitForm(SubmitFormAction action, int depth) {
    final formNode = screenLookup?.call(action.formRef);
    if (formNode is! ForgeFormWidgetNode) {
      _diagnose('form_not_found', 'submit_form: form_ref "${action.formRef}" が見つかりません。');
      return ActionResult.failure('form_not_found', kind: ActionResultKind.invalidTarget);
    }

    final fields = _collectValidatableFields(formNode);
    final errors = validator.validate(fields, store);
    if (errors.isNotEmpty) {
      _diagnose('validation_failed', 'submit_form: "${action.formRef}" の検証に失敗しました: $errors');
      return ActionResult.failure('validation_failed',
          validationErrors: errors, kind: ActionResultKind.validationError);
    }
    return execute(action.successAction, depth: depth);
  }

  ActionResult _executeComposite(CompositeAction action, int depth) {
    if (depth >= maxCompositeDepth) {
      _diagnose('max_composite_depth', 'composite: ネスト上限($maxCompositeDepth段)を超えました。');
      return ActionResult.failure('max_composite_depth', kind: ActionResultKind.runtimeError);
    }
    for (var i = 0; i < action.actions.length; i++) {
      final result = execute(action.actions[i], depth: depth + 1);
      if (!result.success) {
        _diagnose('composite_step_failed', 'composite: ステップ$i(${action.actions[i].runtimeType})で失敗しました'
            '(理由: ${result.reason})。以降のステップは実行しません。');
        // CEOレビュー対応: 一律runtimeErrorにせず、実際に失敗した内側の
        // Actionのkindをそのまま伝播させる(呼び出し元がより正確に原因種別を判定できる)。
        return ActionResult.failure('composite_step_failed_at_$i',
            validationErrors: result.validationErrors, kind: result.kind);
      }
    }
    return ActionResult.success();
  }

  /// formNodeの子孫のうち、validationRulesを持つtext_field/checkboxを集める。
  /// card/columnでラップされていても辿れるよう、containerは再帰的に潜る。
  List<ForgeValidatableField> _collectValidatableFields(ForgeFormWidgetNode formNode) {
    final fields = <ForgeValidatableField>[];
    void walk(ForgeWidgetNode node) {
      if (node is ForgeTextFieldWidgetNode && node.validationRules != null) {
        fields.add(ForgeValidatableField(stateRef: node.stateRef, rules: node.validationRules!));
      } else if (node is ForgeCheckboxWidgetNode && node.validationRules != null) {
        fields.add(ForgeValidatableField(stateRef: node.stateRef, rules: node.validationRules!));
      } else if (node is ForgeColumnWidgetNode) {
        for (final c in node.children) {
          walk(c);
        }
      } else if (node is ForgeRowWidgetNode) {
        for (final c in node.children) {
          walk(c);
        }
      } else if (node is ForgeCardWidgetNode) {
        for (final c in node.children) {
          walk(c);
        }
      }
      // form内にformが再帰的にネストされるケースは想定しない(Schema上は禁止していないが、
      // Mock Generatorも生成せず、実用上の必要性が無いため今回は辿らない)。
    }
    for (final child in formNode.children) {
      walk(child);
    }
    return fields;
  }

  void _diagnose(String category, String message) {
    onDiagnostic?.call(category, message);
  }

  /// FORGE v1.0新規(Workstream E)。[ForgeStateStore.lastFieldErrors]
  /// (Field名 → メッセージ)を、`fieldBindings`(Field名 → state_ref)を
  /// 使って`state_ref`キーへ変換する。既存の`submit_form`
  /// Validation失敗と同じ`ActionResult.validationErrors`の形
  /// (state_ref → メッセージ)に揃えるための、responsibility分離
  /// (StoreはField名の世界だけを知り、Forge Language固有のstate_ref
  /// への変換はDispatcher側の責務とする)。
  Map<String, String> _translateFieldErrors(Map<String, String> fieldErrors, Map<String, String> fieldBindings) {
    final translated = <String, String>{};
    for (final entry in fieldErrors.entries) {
      final stateRef = fieldBindings[entry.key];
      if (stateRef != null) {
        translated[stateRef] = entry.value;
      }
    }
    return translated;
  }
}
