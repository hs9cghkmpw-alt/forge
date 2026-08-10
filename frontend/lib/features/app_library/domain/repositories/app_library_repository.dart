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
}
