import 'dart:convert';

import 'package:shared_preferences/shared_preferences.dart';

import '../../../../core/utils/forge_logger.dart';
import '../../domain/entities/generation_history_entry.dart';
import '../../domain/entities/saved_forge_app.dart';
import '../../domain/repositories/app_library_repository.dart';

/// FORGE v0.2 P5対応。`shared_preferences`によるローカル永続化。
///
/// **既知の制限**: `shared_preferences`は単純なKey-Valueストアであり、
/// 本格的なクエリ・大量データには向かない。今回はリスト全体を1つの
/// JSON配列としてまとめて読み書きする、最小限の実装とした
/// (指示書16.1・16.2節の要求を満たす範囲に限定。将来的に件数が
/// 大きく増える場合はsqlite等への移行を検討する、既知の制限として記録)。
///
/// 履歴は直近`_maxHistoryEntries`件のみ保持する(無制限に増え続けることを
/// 防ぐ)。
class SharedPreferencesAppLibraryRepository implements AppLibraryRepository {
  static const _appsKey = 'forge.saved_apps.v1';
  static const _historyKey = 'forge.generation_history.v1';
  static const _maxHistoryEntries = 50;
  static const _scope = 'AppLibraryRepository';

  final SharedPreferences _prefs;
  const SharedPreferencesAppLibraryRepository(this._prefs);

  @override
  Future<List<SavedForgeApp>> listSavedApps() async {
    final raw = _prefs.getString(_appsKey);
    if (raw == null || raw.isEmpty) return const [];
    final apps = <SavedForgeApp>[];
    try {
      final decoded = jsonDecode(raw) as List<dynamic>;
      for (final item in decoded) {
        if (item is! Map) continue;
        final app = SavedForgeApp.tryFromJson(item.cast<String, dynamic>());
        // 個々のレコードが壊れていても、他のレコードの読み込みは続ける
        // (指示書16.2節「破損レコードだけを隔離または無視」)。
        if (app != null) apps.add(app);
      }
    } catch (e) {
      // JSON全体が壊れている場合、全体クラッシュはさせず空リストとして扱う。
      ForgeLogger.error(_scope, 'saved apps JSON is corrupted, treating as empty', error: e);
      return const [];
    }
    apps.sort((a, b) => b.updatedAt.compareTo(a.updatedAt));
    return apps;
  }

  @override
  Future<void> saveApp(SavedForgeApp app) async {
    final apps = await listSavedApps();
    final withoutExisting = apps.where((a) => a.id != app.id).toList();
    final updated = [app, ...withoutExisting];
    await _prefs.setString(_appsKey, jsonEncode(updated.map((a) => a.toJson()).toList()));
  }

  @override
  Future<void> deleteApp(String id) async {
    final apps = await listSavedApps();
    final updated = apps.where((a) => a.id != id).toList();
    await _prefs.setString(_appsKey, jsonEncode(updated.map((a) => a.toJson()).toList()));
  }

  @override
  Future<List<GenerationHistoryEntry>> listHistory() async {
    final raw = _prefs.getString(_historyKey);
    if (raw == null || raw.isEmpty) return const [];
    final entries = <GenerationHistoryEntry>[];
    try {
      final decoded = jsonDecode(raw) as List<dynamic>;
      for (final item in decoded) {
        if (item is! Map) continue;
        final entry = GenerationHistoryEntry.tryFromJson(item.cast<String, dynamic>());
        if (entry != null) entries.add(entry);
      }
    } catch (e) {
      ForgeLogger.error(_scope, 'history JSON is corrupted, treating as empty', error: e);
      return const [];
    }
    entries.sort((a, b) => b.createdAt.compareTo(a.createdAt));
    return entries;
  }

  @override
  Future<void> addHistoryEntry(GenerationHistoryEntry entry) async {
    final entries = await listHistory();
    final updated = [entry, ...entries].take(_maxHistoryEntries).toList();
    await _prefs.setString(_historyKey, jsonEncode(updated.map((e) => e.toJson()).toList()));
  }
}
