import 'package:flutter/foundation.dart';

import '../schema/forge_document.dart';
import '../runtime/forge_action_dispatcher.dart';
import '../runtime/forge_state_store.dart';

/// AIが生成したJSONの `state` を保持する、実行時サイズ可変の状態コンテナ。
///
/// FORGE-MILESTONE-003で、実際のストレージとAction処理を[ForgeStateStore]・
/// [ForgeActionDispatcher](json_ui/runtime/)へ委譲する形に再編した。
/// 既存のWidget Builder(text_field/checklist/checkbox等)が呼んでいた
/// メソッド(getString/setString/dispatch等)は、シグネチャも挙動もそのまま
/// 維持している(呼び出し側コードの変更は不要)。
///
/// なぜRiverpodのProviderで持たないか(DECISIONS.md参照):
/// Riverpodのproviderはコンパイル時に型・個数が決まっている前提の設計であり、
/// 「実行時にAIが決めたキー・型の集合」を表現するのには向かない。
/// Studioアプリ自体の状態(プロジェクト一覧・認証など)はこれまで通りRiverpodが適切だが、
/// AI生成アプリの内部状態は、この[ForgeRuntimeState](ChangeNotifier)が担当する。
class ForgeRuntimeState extends ChangeNotifier {
  final ForgeStateStore _store;
  late final ForgeActionDispatcher _dispatcher;
  final void Function(ForgeAction action)? onNavigationAction;

  /// FORGE v0.9新規(Typed Record Runtime Phase1)。文書トップレベルの
  /// `record_schemas`(`ForgeDocument.recordSchemas`)をそのまま保持する。
  /// **今回は型情報を保持するだけであり、Widget構築・Action実行・
  /// Validationのいずれからも参照されない**(指示書の制約
  /// 「Runtime動作も変更しません」)。将来のPhaseで、Validation強化・
  /// 型に応じた入力Widgetの自動選択等に使うための土台。
  final Map<String, ForgeRecordSchema> recordSchemas;

  /// FORGE v1.0新規(Product Quality Sprint1)。文書トップレベルの
  /// `design_tokens`(色・角丸・余白)。`design_tokens`を持たない
  /// 文書(Legacy)では`null`——Widget側は必ずnullチェックし、無ければ
  /// ネイティブのテーマ既定値を使うこと。
  final ForgeDesignTokens? designTokens;

  /// submit_form失敗時のフィールド単位エラー(state_ref -> message)。
  /// text_field/checkbox Builderがこれを見て、Widget付近にエラー文言を出す
  /// (FORGE-MILESTONE-003 Task 5「エラーメッセージはWidget付近に表示する」)。
  Map<String, String> _validationErrors = const <String, String>{};

  ForgeRuntimeState(
    Map<String, ForgeStateValue> initial, {
    this.onNavigationAction,
    ForgeWidgetNode? screenRoot,
    ForgeDiagnosticSink? onDiagnostic,
    this.recordSchemas = const {},
    this.designTokens,
  }) : _store = ForgeStateStore(initial, recordSchemas: recordSchemas) {
    _dispatcher = ForgeActionDispatcher(
      store: _store,
      onNavigationAction: onNavigationAction,
      screenLookup: screenRoot == null ? null : (id) => _findById(screenRoot, id),
      onDiagnostic: onDiagnostic ?? _defaultDiagnostic,
    );
  }

  static void _defaultDiagnostic(String category, String message) {
    if (kDebugMode) {
      debugPrint('[ForgeRuntime][$category] $message');
    }
  }

  static ForgeWidgetNode? _findById(ForgeWidgetNode node, String id) {
    if (node.id == id) return node;
    if (node is ForgeColumnWidgetNode) {
      for (final c in node.children) {
        final found = _findById(c, id);
        if (found != null) return found;
      }
    } else if (node is ForgeRowWidgetNode) {
      for (final c in node.children) {
        final found = _findById(c, id);
        if (found != null) return found;
      }
    } else if (node is ForgeCardWidgetNode) {
      for (final c in node.children) {
        final found = _findById(c, id);
        if (found != null) return found;
      }
    } else if (node is ForgeFormWidgetNode) {
      for (final c in node.children) {
        final found = _findById(c, id);
        if (found != null) return found;
      }
    }
    return null;
  }

  // ---------------------------------------------------------------------
  // 既存Widget BuilderがFORGE-MERGE-001〜FORGE-MILESTONE-002で使ってきた
  // 型別API。シグネチャ・挙動を変えていない(内部実装だけStoreへ委譲)。
  // ---------------------------------------------------------------------

  String getString(String key) {
    final v = _store.read(key);
    return v is String ? v : '';
  }

  List<ForgeChecklistItem> getChecklist(String key) => _store.readChecklist(key);

  /// FORGE v0.7新規(Record Runtime Phase1)。
  List<ForgeRecordItem> getRecordList(String key) => _store.readRecordList(key);

  /// FORGE v1.0新規(Workstream D)。`key`が指すrecord_list型stateの
  /// `schema_ref`を返す(無ければ`null`、Legacy文書)。record_list_view
  /// Widgetが、表示用に対応する[ForgeRecordSchema]を解決するために使う。
  String? getRecordListSchemaRef(String key) => _store.readRecordListSchemaRef(key);

  /// FORGE v0.8新規(Record Runtime Phase2)。
  ForgeRecordItem? getSelectedRecord(String key) => _store.readSelectedRecord(key);

  /// 型取得(FORGE v0.9新規、Typed Record Runtime Phase1)。`schemaRef`
  /// に対応する[ForgeRecordSchema]を返す。
  ForgeRecordSchema? getRecordSchema(String schemaRef) => recordSchemas[schemaRef];

  /// 型取得(FORGE v0.9新規)。`schemaRef`が指すSchema内の、`fieldName`
  /// というFieldの型を返す。Schema自体が見つからない、またはFieldが
  /// 見つからない場合は`null`。
  ForgeRecordFieldType? getRecordFieldType(String schemaRef, String fieldName) {
    return recordSchemas[schemaRef]?.fieldByName(fieldName)?.type;
  }

  bool getBoolean(String key) {
    final v = _store.read(key);
    return v is bool ? v : false;
  }

  List<String> getStringList(String key) {
    final v = _store.read(key);
    return v is List<String> ? v : const [];
  }

  /// v1.2新規(FORGE-MILESTONE-003)。number Widgetが将来追加された際に使う想定。
  double getNumber(String key) {
    final v = _store.read(key);
    return v is num ? v.toDouble() : 0;
  }

  void setBoolean(String key, bool value, {bool notify = true}) {
    _store.writeTyped(key, ForgeBooleanState(value));
    if (notify) notifyListeners();
  }

  void setString(String key, String value, {bool notify = true}) {
    _store.writeTyped(key, ForgeStringState(value));
    if (notify) notifyListeners();
  }

  void toggleChecklistItem(String checklistKey, String itemId) {
    if (_store.toggleChecklistItem(checklistKey, itemId)) {
      notifyListeners();
    }
  }

  void deleteChecklistItem(String checklistKey, String itemId) {
    if (_store.deleteChecklistItem(checklistKey, itemId)) {
      notifyListeners();
    }
  }

  void addChecklistItem(String targetChecklistKey, String sourceTextKey) {
    final outcome = _store.addChecklistItem(targetChecklistKey, sourceTextKey);
    if (outcome == AddChecklistItemOutcome.added) {
      notifyListeners();
    }
  }

  /// FORGE-MILESTONE-003 Task 1新規。特定の型に依存しない汎用read/write
  /// (Action Dispatcher・Validatorなど、型を後から判定する処理向け)。
  dynamic read(String key) => _store.read(key);

  bool write(String key, dynamic value) {
    final ok = _store.write(key, value);
    if (ok) notifyListeners();
    return ok;
  }

  bool contains(String key) => _store.contains(key);

  /// FORGE-AI-QUALITY-001(2026-08-11)新設(ローカル永続化対応)。現在の
  /// 全State値を、`ForgeStateValue.fromJson`が読める形(`{"type":...,
  /// "value":...}`)でJSON化して返す。呼び出し元(`GeneratedAppHostShell`
  /// 等)がこれをローカルストレージへ保存し、次回開いた際に
  /// `mergePersistedState`で復元する想定(`forge_document.dart`参照)。
  Map<String, dynamic> exportStateJson() =>
      {for (final entry in _store.snapshot().entries) entry.key: entry.value.toJson()};

  /// FORGE-MILESTONE-003 Task 5新規。text_field/checkbox Builderが、
  /// 自分のstate_refに対応するエラーメッセージが無いかを見るためのAPI。
  String? getValidationError(String stateRef) => _validationErrors[stateRef];

  /// 汎用Action処理の入口(FORGE-MILESTONE-003 Task 4で[ForgeActionDispatcher]へ
  /// 一元化)。戻り値[ActionResult]は追加されたが、既存の
  /// `onPressed: () => state.dispatch(action)` という呼び出し方は
  /// (Dartが`void Function()`コンテキストで非voidの戻り値を許容するため)
  /// 変更せずにそのまま動く。
  ActionResult dispatch(ForgeAction action) {
    final result = _dispatcher.execute(action);

    if (action is SubmitFormAction) {
      // submit_form実行後は、そのフォームに関するエラー表示を結果に合わせて更新する。
      _validationErrors = result.validationErrors ?? const <String, String>{};
    }
    notifyListeners();
    return result;
  }
}
