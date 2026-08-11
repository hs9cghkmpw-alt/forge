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
  static const _runtimeStateKey = 'forge.app_runtime_state.v1';
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

  // FORGE-AI-QUALITY-001(2026-08-11)新設(ローカル永続化対応)。
  //
  // `listSavedApps`/`saveApp`と同じ「1キーへJSON全体をまとめて読み書き
  // する」方式を踏襲する(`_appsKey`/`_historyKey`と同じ既知の制限
  // (TECH_DEBT.md参照)を承知の上で、既存の実績あるパターンに揃えた)。
  // 形式: `{appId: {screenId: {stateKey: {"type":..., "value":...}}}}`。
  Future<Map<String, dynamic>> _readAllRuntimeState() async {
    final raw = _prefs.getString(_runtimeStateKey);
    if (raw == null || raw.isEmpty) return {};
    try {
      final decoded = jsonDecode(raw);
      if (decoded is! Map) return {};
      return Map<String, dynamic>.from(decoded);
    } catch (e) {
      // JSON全体が壊れている場合、全体クラッシュはさせず空として扱う
      // (`listSavedApps`と同じ方針。個別アプリのStateが1件壊れているより
      // 悪い「全アプリのState消失」は避けたいが、壊れたJSON自体は
      // 復元不能なため、安全側でリセットする)。
      ForgeLogger.error(_scope, 'runtime state JSON is corrupted, treating as empty', error: e);
      return {};
    }
  }

  @override
  Future<Map<String, Map<String, dynamic>>?> loadRuntimeState(String appId) async {
    final all = await _readAllRuntimeState();
    final forApp = all[appId];
    if (forApp is! Map) return null;
    final result = <String, Map<String, dynamic>>{};
    forApp.forEach((screenId, screenState) {
      if (screenState is Map) {
        result[screenId] = Map<String, dynamic>.from(screenState);
      }
    });
    return result.isEmpty ? null : result;
  }

  @override
  Future<void> saveRuntimeStateForScreen(String appId, String screenId, Map<String, dynamic> stateJson) async {
    final all = await _readAllRuntimeState();
    final forApp = (all[appId] is Map) ? Map<String, dynamic>.from(all[appId] as Map) : <String, dynamic>{};
    forApp[screenId] = stateJson;
    all[appId] = forApp;
    await _prefs.setString(_runtimeStateKey, jsonEncode(all));
  }

  @override
  Future<void> deleteRuntimeState(String appId) async {
    final all = await _readAllRuntimeState();
    if (all.remove(appId) != null) {
      await _prefs.setString(_runtimeStateKey, jsonEncode(all));
    }
  }
}
