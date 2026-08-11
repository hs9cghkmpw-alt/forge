import '../entities/generation_history_entry.dart';
import '../entities/saved_forge_app.dart';

/// FORGE v0.2 P5対応。マイアプリ・履歴の永続化契約(interface)。
/// 実装は data/repositories/ に置く(SharedPreferencesへの依存を隠す)。
abstract class AppLibraryRepository {
  Future<List<SavedForgeApp>> listSavedApps();
  Future<void> saveApp(SavedForgeApp app);
  Future<void> deleteApp(String id);

  Future<List<GenerationHistoryEntry>> listHistory();
  Future<void> addHistoryEntry(GenerationHistoryEntry entry);

  /// FORGE-AI-QUALITY-001(2026-08-11)新設(ローカル永続化対応)。
  /// `appId`で保存されているアプリの実行時State(画面ID→State全体の
  /// JSON)を読み込む。保存が無ければ`null`(呼び出し側は文書の初期値の
  /// まま扱う)。
  Future<Map<String, Map<String, dynamic>>?> loadRuntimeState(String appId);

  /// `appId`の`screenId`画面のStateを丸ごと上書き保存する
  /// (`loadRuntimeState`で読める形と対称)。他の画面のStateには影響
  /// しない。
  Future<void> saveRuntimeStateForScreen(String appId, String screenId, Map<String, dynamic> stateJson);

  /// `appId`の実行時State(全画面分)を削除する(`deleteApp`と併せて
  /// 呼ぶ想定。アプリ定義を消してもStateだけ残り続けることを防ぐ)。
  Future<void> deleteRuntimeState(String appId);
}
