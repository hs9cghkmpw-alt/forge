import '../schema/forge_document.dart';
import '../validation/forge_record_schema_resolver.dart';
import '../validation/forge_record_validator.dart';

/// Forge Runtimeの単一State Store(FORGE-MILESTONE-003 Task 1)。
///
/// 依存方向を守るため、このクラスは`ForgeWidgetNode`・特定の画面名・
/// 特定の生成テンプレートを一切知らない。知っているのは
/// `ForgeStateValue`(schema/forge_document.dart)という、Widgetから独立した
/// データ表現だけである。
///
/// 「単一のState Store」という要求を、既存の[ForgeRuntimeState]
/// (Widgetから直接使われてきた、実績のあるAPI)を置き換える形ではなく、
/// [ForgeRuntimeState]が内部でこのクラスへ委譲する形で実現した
/// (DECISIONS.md参照。既存Widget Builderのコードを一切変更せずに済む)。
class ForgeStateStore {
  final Map<String, ForgeStateValue> _values;

  /// 画面の初期化時点の値のコピー。`reset_state`で使う。
  /// 「画面を開いた瞬間の値」であり、直近の値ではない点に注意
  /// (指示書Task 3: 個別ResetとState全体一括Resetは明確に区別する。
  /// 一括Resetは今回導入していない)。
  final Map<String, ForgeStateValue> _initialValues;

  /// FORGE v1.0新規(Typed Schema-Driven Application Runtime)。
  /// `schema_ref`を持つ`record_list`のadd/update/select時、Fieldの
  /// 型情報を解決するために使う。空の場合(Legacy文書、v1.3以前)は、
  /// 従来通りのstring中心の挙動にフォールバックする
  /// (指示書Workstream C.5「Legacy Behavior」)。
  final Map<String, ForgeRecordSchema> _recordSchemas;
  final ForgeRecordSchemaResolver _schemaResolver;
  final ForgeRecordValidator _recordValidator;

  ForgeStateStore(
    Map<String, ForgeStateValue> initial, {
    Map<String, ForgeRecordSchema> recordSchemas = const {},
    ForgeRecordSchemaResolver schemaResolver = const ForgeRecordSchemaResolver(),
    ForgeRecordValidator recordValidator = const ForgeRecordValidator(),
  })  : _values = Map.of(initial),
        _initialValues = Map.of(initial),
        _recordSchemas = recordSchemas,
        _schemaResolver = schemaResolver,
        _recordValidator = recordValidator;

  bool contains(String key) => _values.containsKey(key);

  /// 型を問わない汎用read。Widget Builderからではなく、Action Dispatcher・
  /// Validatorなど「値の型を後から判定する」処理から使うことを想定する
  /// (指示書Task 1のAPI例に対応)。
  dynamic read(String key) {
    final v = _values[key];
    return switch (v) {
      ForgeStringState s => s.value,
      ForgeBooleanState b => b.value,
      ForgeNumberState n => n.value,
      ForgeStringListState l => l.value,
      ForgeChecklistState c => c.value,
      ForgeRecordListState r => r.value,
      ForgeSelectedRecordState sr => sr.value,
      null => null,
    };
  }

  ForgeStateValue? readTyped(String key) => _values[key];

  /// FORGE-AI-QUALITY-001(2026-08-11)新設(ローカル永続化対応)。現在の
  /// 全State値のコピーを返す(呼び出し元がこのStoreの内部Mapを直接
  /// 保持・変更できないようにするための防御的コピー)。
  Map<String, ForgeStateValue> snapshot() => Map.of(_values);

  /// 汎用write。既存の型と矛盾する値が来た場合は書き込まず`false`を返す
  /// (Widget Builder個別ではなくここで一元的に型検証する。指示書Task 2)。
  /// 存在しないキーへの書き込みも`false`を返す(FORGE-MILESTONE-003.1で修正。
  /// Forge Languageの契約上、state_refは必ず事前宣言されている前提のため、
  /// 存在しないキーへのwriteは常に「対象が存在しない」という失敗として扱う。
  /// 詳細は[_coerce]のコメント参照)。
  bool write(String key, dynamic value) {
    final current = _values[key];
    final next = _coerce(current, value);
    if (next == null) return false;
    _values[key] = next;
    return true;
  }

  /// 型が完全に分かっている場合の直接書き込み(内部・テスト用)。
  void writeTyped(String key, ForgeStateValue value) {
    _values[key] = value;
  }

  ForgeStateValue? _coerce(ForgeStateValue? current, dynamic value) {
    if (current is ForgeStringState && value is String) return ForgeStringState(value);
    if (current is ForgeBooleanState && value is bool) return ForgeBooleanState(value);
    if (current is ForgeNumberState && value is num) return ForgeNumberState(value.toDouble());
    if (current is ForgeStringListState && value is List) {
      final strings = value.whereType<String>().toList();
      if (strings.length == value.length) return ForgeStringListState(strings);
      return null;
    }
    // checklistはtoggle/delete/add専用の操作を経由するため、write()の汎用
    // coercion対象には含めない(意図的。個別メソッド側で扱う)。
    //
    // CEO実機検証で発見・修正(FORGE-MILESTONE-003.1): 以前はここに
    // 「current == null(=対象キーが存在しない)なら、valueの実行時型から
    // State型を推測して新規作成する」という分岐があった。しかしForge
    // Languageの契約上、set_value/set_stateが参照するstate_refは必ず
    // screen.stateへ事前宣言されている前提であり(Validatorもそれを
    // 検査している)、存在しないキーへのwriteは「AI生成JSONの契約違反」
    // として弾くべきものだった。この分岐があったせいで、存在しない
    // state_refへのset_valueが静かに成功してしまい(ActionResultKindが
    // successになってしまい)、CEO実機のflutter testで検出された
    // (action_result_kind_test.dartの2件が失敗)。
    // 対象キーが無い場合は常にnullを返す(=書き込み失敗)よう修正した。
    return null;
  }

  /// `reset_state`: 画面初期化時点の値へ戻す。存在しないキーは無視する
  /// (Validatorが事前に存在確認しているはずだが、Runtime側でも多重防御する)。
  bool reset(String key) {
    final initial = _initialValues[key];
    if (initial == null) return false;
    _values[key] = initial;
    return true;
  }

  /// `toggle_state`: boolean以外には作用しない(false=失敗を返す)。
  bool toggleBoolean(String key) {
    final current = _values[key];
    if (current is! ForgeBooleanState) return false;
    _values[key] = ForgeBooleanState(!current.value);
    return true;
  }

  int _itemIdCounter = 0;

  List<ForgeChecklistItem> readChecklist(String key) => switch (_values[key]) {
        ForgeChecklistState c => c.value,
        _ => const <ForgeChecklistItem>[],
      };

  bool toggleChecklistItem(String checklistKey, String itemId) {
    final current = _values[checklistKey];
    if (current is! ForgeChecklistState) return false;
    final updated = [
      for (final item in current.value)
        if (item.id == itemId) item.copyWith(done: !item.done) else item,
    ];
    _values[checklistKey] = ForgeChecklistState(updated);
    return true;
  }

  bool deleteChecklistItem(String checklistKey, String itemId) {
    final current = _values[checklistKey];
    if (current is! ForgeChecklistState) return false;
    _values[checklistKey] = ForgeChecklistState(current.value.where((i) => i.id != itemId).toList());
    return true;
  }

  /// `add_item`: sourceのテキストを読み、targetのchecklistへ新規itemとして追加し、
  /// sourceを空へ戻す(Prototype v0.1.3の`_addItem()`と同じ挙動。DECISIONS.md参照)。
  ///
  /// FORGE-MILESTONE-003.1 PHASE1/2で修正: 以前はbool一値(成功/失敗)しか
  /// 返さず、「sourceが空文字(=ユーザーが何も入力せず追加を押しただけの、
  /// 完全に正常な操作)」と「target/sourceのStateが存在しない・型が違う
  /// (=AI生成JSONの契約違反、本物の不具合)」を同じ`false`として
  /// 呼び出し側(ForgeActionDispatcher)へ返していた。その結果、ただ
  /// 「何も入力せず追加を押した」だけでRuntime ERRORログが出ていた
  /// (CEO実機で確認された`add_item_failed`。詳細はFORGE-MILESTONE-003.1-report.md
  /// 1章)。[AddChecklistItemOutcome]で両者を明確に区別する。
  AddChecklistItemOutcome addChecklistItem(String targetKey, String sourceKey) {
    final targetCurrent = _values[targetKey];
    final sourceCurrent = _values[sourceKey];
    if (targetCurrent is! ForgeChecklistState) {
      return AddChecklistItemOutcome.targetMissing;
    }
    if (sourceCurrent is! ForgeStringState) {
      return AddChecklistItemOutcome.sourceMissing;
    }
    final text = sourceCurrent.value.trim();
    if (text.isEmpty) {
      // 正常な操作: ユーザーが何も入力せず追加ボタンを押した。
      // 契約違反ではないため、targetMissing/sourceMissingとは区別する。
      return AddChecklistItemOutcome.emptySource;
    }
    _itemIdCounter += 1;
    final newItem = ForgeChecklistItem(
      id: 'runtime_item_${DateTime.now().microsecondsSinceEpoch}_$_itemIdCounter',
      text: text,
      done: false,
    );
    _values[targetKey] = ForgeChecklistState([...targetCurrent.value, newItem]);
    _values[sourceKey] = const ForgeStringState('');
    return AddChecklistItemOutcome.added;
  }

  List<ForgeRecordItem> readRecordList(String key) => switch (_values[key]) {
        ForgeRecordListState r => r.value,
        _ => const <ForgeRecordItem>[],
      };

  /// FORGE v1.0新規(Workstream D)。
  String? readRecordListSchemaRef(String key) => switch (_values[key]) {
        ForgeRecordListState r => r.schemaRef,
        _ => null,
      };

  /// `add_record`(FORGE v0.7新規、Record Runtime Phase1)。
  ///
  /// `fieldBindings`(Record field名 → source state key)の各エントリの
  /// **現在値**を読み、1つの[ForgeRecordItem]へ束ねて`targetKey`
  /// (record_list型)へ追加する(`FORGE-IR-V1-PROPOSAL.md` 4.3節
  /// 「宣言的なField束ね」方式の実装)。動的な式評価は行わない。
  ///
  /// [addChecklistItem]と異なり、`add_record`は常に`form.submit_action`
  /// 経由(`SubmitFormAction`によるValidation)で呼ばれる設計のため
  /// (`buildForm`が`submitAction`を無条件に`SubmitFormAction`で包む、
  /// `widget_registry_v1_1.dart`参照)、必須Fieldが空のまま到達すること
  /// は無い想定である。ただし、任意(非必須)Fieldは空文字列のまま
  /// 追加されうる(これは正常な操作であり、失敗として扱わない)。
  ///
  /// source stateが1つでも存在しない、またはstring/number/boolean以外の
  /// 型の場合は`AddRecordOutcome.sourceMissing`を返す(AI生成JSONの
  /// 契約違反、`addChecklistItem`の`sourceMissing`と同じ位置づけ)。
  /// FORGE v1.0新規。直前の`addRecord`/`updateRecord`/`selectRecord`
  /// 呼び出しが型検証エラー(`invalidBinding`)で失敗した場合、
  /// Field名 → エラーメッセージを保持する(呼び出し成功時・Legacy
  /// パス経由の場合は空)。[ForgeActionDispatcher]がこれを読み、
  /// `field_bindings`(Field名 → state_ref)を使って`state_ref`
  /// キーへ変換した上で、既存の`ActionResult.validationErrors`
  /// (`submit_form`と同じ仕組み、Widget付近にエラー表示する)へ渡す。
  Map<String, String> lastFieldErrors = const {};

  /// `add_record`(FORGE v0.7新規、Record Runtime Phase1。
  /// FORGE v1.0でSchema-driven型検証に対応、Workstream C.1)。
  ///
  /// `targetKey`(record_list型)が`schema_ref`を持つ場合、対応する
  /// [ForgeRecordSchema]に従って`fieldBindings`の各値を型付きへ
  /// 変換・検証する([ForgeRecordValidator]、Atomicity: 1件でも失敗
  /// すればStateを一切変更しない)。`schema_ref`が無い(v1.3以前の
  /// Legacy文書)場合は、**従来通り**Source Stateの型をそのまま
  /// 転記するだけの挙動を維持する(指示書Workstream C.5「Legacy
  /// Behavior」)。
  AddRecordOutcome addRecord(String targetKey, Map<String, String> fieldBindings) {
    lastFieldErrors = const {};
    final targetCurrent = _values[targetKey];
    if (targetCurrent is! ForgeRecordListState) {
      return AddRecordOutcome.targetMissing;
    }

    final schema = _schemaResolver.resolve(_recordSchemas, targetCurrent.schemaRef);
    final Map<String, dynamic> fields;
    if (schema == null) {
      // Legacy path(v1.3以前、schema_ref無し): 無変更。
      final legacyFields = <String, dynamic>{};
      for (final entry in fieldBindings.entries) {
        final sourceCurrent = _values[entry.value];
        if (sourceCurrent is ForgeStringState) {
          legacyFields[entry.key] = sourceCurrent.value;
        } else if (sourceCurrent is ForgeNumberState) {
          legacyFields[entry.key] = sourceCurrent.value;
        } else if (sourceCurrent is ForgeBooleanState) {
          legacyFields[entry.key] = sourceCurrent.value;
        } else {
          return AddRecordOutcome.sourceMissing;
        }
      }
      fields = legacyFields;
    } else {
      final rawValues = _gatherRawFieldValues(fieldBindings);
      if (rawValues == null) {
        return AddRecordOutcome.sourceMissing;
      }
      final result = _recordValidator.validate(schema, rawValues);
      if (result is RecordValidationFailure) {
        lastFieldErrors = {for (final e in result.fieldErrors.entries) e.key: e.value.message};
        return AddRecordOutcome.validationFailed;
      }
      fields = (result as RecordValidationSuccess).fields;
    }

    _itemIdCounter += 1;
    final newRecord = ForgeRecordItem(
      id: 'runtime_record_${DateTime.now().microsecondsSinceEpoch}_$_itemIdCounter',
      fields: fields,
    );
    _values[targetKey] = ForgeRecordListState([...targetCurrent.value, newRecord], schemaRef: targetCurrent.schemaRef);
    return AddRecordOutcome.added;
  }

  /// `fieldBindings`の各Field名に対応するsource stateの**生の値**を
  /// 集める(`ForgeStringState`→`String`、`ForgeBooleanState`→`bool`、
  /// `ForgeNumberState`→`double`)。参照先のstateが1件でも存在しない
  /// 場合は`null`を返す(契約違反、呼び出し側は`sourceMissing`として
  /// 扱う)。値の妥当性([ForgeRecordValidator]が担当)はここでは検査
  /// しない(責務分離)。
  Map<String, Object?>? _gatherRawFieldValues(Map<String, String> fieldBindings) {
    final raw = <String, Object?>{};
    for (final entry in fieldBindings.entries) {
      final sourceCurrent = _values[entry.value];
      if (sourceCurrent is ForgeStringState) {
        raw[entry.key] = sourceCurrent.value;
      } else if (sourceCurrent is ForgeBooleanState) {
        raw[entry.key] = sourceCurrent.value;
      } else if (sourceCurrent is ForgeNumberState) {
        raw[entry.key] = sourceCurrent.value;
      } else {
        return null;
      }
    }
    return raw;
  }

  ForgeRecordItem? readSelectedRecord(String key) => switch (_values[key]) {
        ForgeSelectedRecordState s => s.value,
        _ => null,
      };

  /// FORGE v0.8.1(Record CRUD Runtime Hardening)新設。
  ///
  /// `key`が存在し、かつ`T`型であることを検証する共通ヘルパー。
  /// [selectRecord]/[updateRecord]/[deleteRecord]で重複していた
  /// 「存在確認」と「型確認」を1箇所へ集約した(指示書のDesign Policy
  /// 「コード重複よりも責務分離」を踏襲)。**「存在しない」と「型が
  /// 違う」を明確に区別する**(指示書の要求、[RecordOperationOutcome]
  /// 参照)。問題が無ければ`null`を返す。
  RecordOperationOutcome? _checkStateExistsAndTyped<T extends ForgeStateValue>(String key) {
    if (!_values.containsKey(key)) {
      return RecordOperationOutcome.targetStateNotFound;
    }
    if (_values[key] is! T) {
      return RecordOperationOutcome.targetStateTypeMismatch;
    }
    return null;
  }

  /// `select_record`(FORGE v0.8 Record Runtime Phase2、
  /// FORGE v0.8.1でAtomicityを強化)。
  ///
  /// `sourceKey`(record_list型)の中から`recordId`と一致するRecordを
  /// 探し、`targetKey`(selected_record型)へ設定する。`fieldBindings`
  /// (Record field名 → 書き込み先state key)が指定されていれば、
  /// 見つかったRecordの各Field値を、対応するstring型stateへ反映する
  /// (編集フォームの事前入力用)。
  ///
  /// **FORGE v0.8.1での変更(重要な修正)**: 以前は`fieldBindings`の
  /// 反映を「ベストエフォート」とし、選択(target設定)は`fieldBindings`
  /// の一部が失敗しても常に成立させていた。これにより、「選択自体は
  /// 成功したが、一部の編集Fieldだけ前回選択していたRecordの値が
  /// 残ったまま」という**不整合な状態**が起こりうることが判明した
  /// (指示書の指摘通り、誤ったRecord更新につながるリスクがある)。
  ///
  /// 今回、**全`fieldBindings`を先に検証し、1件でも無効ならStateを
  /// 一切変更せずに`invalidBinding`を返す**方式(指示書「推奨方式」)へ
  /// 変更した。検証を全て通過した場合のみ、`selected_record`と
  /// 全ての編集Field Stateを**まとめて**更新する(Atomicity)。
  /// **FORGE v1.0での修正(実装中に発見した実在のバグ)**: 以前は
  /// 書き込み先が`ForgeStringState`であることしか許容しておらず、
  /// boolean型Field(Workstream B.4対応でcheckbox+`ForgeBooleanState`
  /// を使うようになった)を選択すると、常に`invalidBinding`になって
  /// いた。今回、書き込み先の実際の型(String/Boolean)に応じて、
  /// Recordの値をそのまま(Boolean)、または文字列化して(String)
  /// 反映するよう修正した。
  RecordOperationOutcome selectRecord(
    String sourceKey,
    String targetKey,
    String recordId,
    Map<String, String> fieldBindings,
  ) {
    final sourceCheck = _checkStateExistsAndTyped<ForgeRecordListState>(sourceKey);
    if (sourceCheck != null) return sourceCheck;
    final targetCheck = _checkStateExistsAndTyped<ForgeSelectedRecordState>(targetKey);
    if (targetCheck != null) return targetCheck;

    final sourceCurrent = _values[sourceKey] as ForgeRecordListState;

    ForgeRecordItem? found;
    for (final record in sourceCurrent.value) {
      if (record.id == recordId) {
        found = record;
        break;
      }
    }
    if (found == null) {
      return RecordOperationOutcome.recordNotFound;
    }

    // Phase1: 全field_bindingsを事前検証する(Stateはまだ一切変更しない)。
    // 宛先の実際の型(String/Boolean)に応じて反映方法を変える。
    final Map<String, Object> resolvedWrites = {};
    for (final entry in fieldBindings.entries) {
      final fieldValue = found.fields[entry.key];
      if (fieldValue == null) {
        return RecordOperationOutcome.invalidBinding;
      }
      final destCurrent = _values[entry.value];
      if (destCurrent is ForgeStringState) {
        resolvedWrites[entry.value] = fieldValue.toString();
      } else if (destCurrent is ForgeBooleanState) {
        if (fieldValue is! bool) {
          return RecordOperationOutcome.invalidBinding;
        }
        resolvedWrites[entry.value] = fieldValue;
      } else {
        return RecordOperationOutcome.invalidBinding;
      }
    }

    // Phase2: 検証が全て通った場合のみ、selected_record + 編集Fieldを
    // まとめて反映する。
    _values[targetKey] = ForgeSelectedRecordState(found);
    for (final entry in resolvedWrites.entries) {
      final v = entry.value;
      _values[entry.key] = (v is bool) ? ForgeBooleanState(v) : ForgeStringState(v as String);
    }
    return RecordOperationOutcome.success;
  }

  /// `update_record`(FORGE v0.8 Record Runtime Phase2、
  /// FORGE v0.8.1で`selected_record`同期を強化、
  /// FORGE v1.0でSchema-driven型検証に対応、Workstream C.3)。
  ///
  /// `recordIdRef`(selected_record型)が指すRecordのidを`targetKey`
  /// (record_list型)から探し、`fieldBindings`の現在値で丸ごと置き
  /// 換える。無選択(`recordIdRef`の値が`null`)の場合は`noSelection`を
  /// 返す(契約違反ではない。UIが「更新」ボタンを無効化し損ねた場合の
  /// 安全な失敗として扱う)。
  ///
  /// `targetKey`が`schema_ref`を持つ場合、[addRecord]と同じ
  /// [ForgeRecordValidator]による型検証・Atomicityを適用する。無い
  /// 場合はLegacy挙動(Source Stateの型をそのまま転記)を維持する。
  RecordOperationOutcome updateRecord(String targetKey, String recordIdRef, Map<String, String> fieldBindings) {
    lastFieldErrors = const {};
    final targetCheck = _checkStateExistsAndTyped<ForgeRecordListState>(targetKey);
    if (targetCheck != null) return targetCheck;
    final refCheck = _checkStateExistsAndTyped<ForgeSelectedRecordState>(recordIdRef);
    if (refCheck != null) return refCheck;

    final targetCurrent = _values[targetKey] as ForgeRecordListState;
    final idRefCurrent = _values[recordIdRef] as ForgeSelectedRecordState;
    final selected = idRefCurrent.value;
    if (selected == null) {
      return RecordOperationOutcome.noSelection;
    }
    final index = targetCurrent.value.indexWhere((r) => r.id == selected.id);
    if (index == -1) {
      // 指示書の明示的な検証項目: 「存在しないrecord更新失敗」。
      // (例: 選択後、別の操作でそのRecordが既に削除されていた場合)
      return RecordOperationOutcome.recordNotFound;
    }

    final schema = _schemaResolver.resolve(_recordSchemas, targetCurrent.schemaRef);
    final Map<String, dynamic> fields;
    if (schema == null) {
      // Legacy path(v1.3以前、schema_ref無し): 無変更。
      final legacyFields = <String, dynamic>{};
      for (final entry in fieldBindings.entries) {
        final sourceCurrent = _values[entry.value];
        if (sourceCurrent is ForgeStringState) {
          legacyFields[entry.key] = sourceCurrent.value;
        } else if (sourceCurrent is ForgeNumberState) {
          legacyFields[entry.key] = sourceCurrent.value;
        } else if (sourceCurrent is ForgeBooleanState) {
          legacyFields[entry.key] = sourceCurrent.value;
        } else {
          return RecordOperationOutcome.invalidBinding;
        }
      }
      fields = legacyFields;
    } else {
      final rawValues = _gatherRawFieldValues(fieldBindings);
      if (rawValues == null) {
        return RecordOperationOutcome.invalidBinding;
      }
      final result = _recordValidator.validate(schema, rawValues);
      if (result is RecordValidationFailure) {
        lastFieldErrors = {for (final e in result.fieldErrors.entries) e.key: e.value.message};
        return RecordOperationOutcome.invalidBinding;
      }
      fields = (result as RecordValidationSuccess).fields;
    }

    final updatedRecord = ForgeRecordItem(id: selected.id, fields: fields);
    final updatedList = [...targetCurrent.value];
    updatedList[index] = updatedRecord;

    // FORGE v1.0で発見・修正したバグ: 以前はここで`schemaRef`を
    // 引き継いでおらず、1回でもupdateすると`record_list`の`schema_ref`
    // が失われ、以降の操作がLegacy pathへ意図せず落ちてしまっていた。
    _values[targetKey] = ForgeRecordListState(updatedList, schemaRef: targetCurrent.schemaRef);
    // Hardening: selected_recordのキャッシュも同じ内容へ揃える。
    _values[recordIdRef] = ForgeSelectedRecordState(updatedRecord);
    return RecordOperationOutcome.success;
  }

  /// `delete_record`(FORGE v0.8 Record Runtime Phase2、
  /// FORGE v0.8.1で選択解除を強化)。
  ///
  /// `recordIdRef`(selected_record型)が指すRecordのidを`targetKey`
  /// (record_list型)から探して削除する。[updateRecord]と対称的な
  /// 設計(無選択は`noSelection`、対象が既に無ければ`recordNotFound`)。
  ///
  /// **FORGE v0.8.1での変更**: 削除成功時、`recordIdRef`
  /// (selected_record)を**必ず`null`へ解除する**ようにした。以前は
  /// Compilerが生成する`composite`側の`reset_state`にのみ依存して
  /// おり、Runtime自体は「削除したRecordを指したままのselected_record」
  /// を許容してしまっていた(指示書「選択中のRecordを削除した場合、
  /// selected_recordを解除する」を、Runtime自身の保証にする)。
  RecordOperationOutcome deleteRecord(String targetKey, String recordIdRef) {
    final targetCheck = _checkStateExistsAndTyped<ForgeRecordListState>(targetKey);
    if (targetCheck != null) return targetCheck;
    final refCheck = _checkStateExistsAndTyped<ForgeSelectedRecordState>(recordIdRef);
    if (refCheck != null) return refCheck;

    final targetCurrent = _values[targetKey] as ForgeRecordListState;
    final idRefCurrent = _values[recordIdRef] as ForgeSelectedRecordState;
    final selected = idRefCurrent.value;
    if (selected == null) {
      return RecordOperationOutcome.noSelection;
    }

    final newList = targetCurrent.value.where((r) => r.id != selected.id).toList();
    if (newList.length == targetCurrent.value.length) {
      // 指示書の明示的な検証項目: 「存在しないrecord削除失敗」。
      return RecordOperationOutcome.recordNotFound;
    }
    // FORGE v1.0で発見・修正したバグ(updateRecordと同種): schemaRefを
    // 引き継がないと、削除後にschema_refが失われてしまう。
    _values[targetKey] = ForgeRecordListState(newList, schemaRef: targetCurrent.schemaRef);
    // Hardening: 削除したRecordを指したままのselected_recordを残さない。
    _values[recordIdRef] = const ForgeSelectedRecordState(null);
    return RecordOperationOutcome.success;
  }
}

/// FORGE-MILESTONE-003.1新規。[ForgeStateStore.addChecklistItem]の結果種別。
/// `emptySource`(ユーザーが未入力のまま追加を押した、正常操作)と
/// `targetMissing`/`sourceMissing`(AI生成JSONの契約違反、本物の不具合)を
/// 明確に区別するために導入した(1つのboolに落とし込まない)。
enum AddChecklistItemOutcome {
  /// 追加に成功した。
  added,

  /// sourceのテキストが空だった(ユーザーが未入力のまま追加を押した)。
  /// 正常な操作であり、契約違反ではない。
  emptySource,

  /// targetがchecklist型のStateとして存在しない(契約違反)。
  targetMissing,

  /// sourceがstring型のStateとして存在しない(契約違反)。
  sourceMissing,
}

/// FORGE v0.7新規(Record Runtime Phase1)。[ForgeStateStore.addRecord]の
/// 結果種別。[AddChecklistItemOutcome]と同じ設計方針(正常操作と契約違反を
/// 明確に区別する)を踏襲する。`add_record`は常にForm Validation経由で
/// 呼ばれる設計のため、[AddChecklistItemOutcome.emptySource]に相当する
/// ケース(必須値が空のまま送信された)は存在しない。
enum AddRecordOutcome {
  /// 追加に成功した。
  added,

  /// targetがrecord_list型のStateとして存在しない(契約違反)。
  targetMissing,

  /// field_bindingsが参照するsourceのいずれかが、string/number/boolean型の
  /// Stateとして存在しない(契約違反、Legacy pathまたは参照先state自体の欠落)。
  sourceMissing,

  /// FORGE v1.0新規。schema_refがある場合の型検証([ForgeRecordValidator])に
  /// 1件以上失敗した(必須未入力・数値/日付書式不正・choice範囲外等)。
  /// `lastFieldErrors`に詳細が入る。契約違反とは限らない(ユーザーの
  /// 入力ミスの方が典型的)。
  validationFailed,
}

/// FORGE v0.8.1(Record CRUD Runtime Hardening)新設。
///
/// [ForgeStateStore.selectRecord]/[updateRecord]/[deleteRecord]で
/// 共有する結果種別。以前(FORGE v0.8)はこの3メソッドがそれぞれ
/// 独自の`SelectRecordOutcome`/`UpdateRecordOutcome`/
/// `DeleteRecordOutcome`を持っていたが、失敗理由の呼び方が微妙に
/// 揃っていなかった(例: 「対象が存在しない」と「型が違う」を
/// どちらも`targetMissing`という1つの値に丸めていた)。今回、
/// 指示書が明示した6種類の結果へ統合し、**「存在しない」と「型が
/// 違う」を明確に区別する**ようにした(`targetStateNotFound`と
/// `targetStateTypeMismatch`)。
///
/// [ForgeStateStore.addRecord]の`AddRecordOutcome`は、この統合の
/// 対象に含めていない(意図的な判断): `add_record`は「選択」という
/// 概念を持たず、`noSelection`・`recordNotFound`に相当する状況が
/// 存在しないため、無理に同じenumへ揃えるとかえって意味の無い値を
/// 増やすことになる。今回のHardeningの対象(指示書「Record選択と
/// 編集フォーム同期の安全性」)はselect/update/deleteの3操作である。
enum RecordOperationOutcome {
  /// 操作に成功した。
  success,

  /// 操作対象となるRecordが選択されていない状態で、選択前提の操作
  /// (update/delete)が呼ばれた。契約違反ではない(UIが「更新」
  /// 「削除」ボタンを無効化し損ねた場合の、安全な失敗として扱う)。
  noSelection,

  /// 探索対象のidと一致するRecordが見つからなかった(表示直後に
  /// 他の操作で削除された場合等に起こりうる。必ずしも契約違反とは
  /// 限らない)。
  recordNotFound,

  /// `fieldBindings`のいずれかが無効(参照先のFieldがRecordに存在
  /// しない、または書き込み/読み出し先のStateが期待する型でない)。
  /// AI生成JSONの契約違反の可能性が高い。
  invalidBinding,

  /// 操作対象の主要なState(record_list型・selected_record型)の
  /// キー自体が、Store内に存在しない(契約違反)。
  targetStateNotFound,

  /// 操作対象の主要なStateのキーは存在するが、期待する型
  /// (record_list型・selected_record型)ではない(契約違反)。
  targetStateTypeMismatch,
}
