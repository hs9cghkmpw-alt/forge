// SharedPreferencesAppLibraryRepository Unit Test
// (FORGE-AI-QUALITY-001、2026-08-11、ローカル永続化対応で新設)。
//
// `loadRuntimeState`/`saveRuntimeStateForScreen`/`deleteRuntimeState`を
// 検証する(既存の`listSavedApps`/`saveApp`と同じ「1キーへJSON全体を
// まとめて読み書きする」方式)。
//
// 注記: Claudeのサンドボックスに Dart SDK が無いため、このファイルは
// 一度も `flutter test` で実行されていない。CEO環境での実行が必須。

import 'package:flutter_test/flutter_test.dart';
import 'package:forge_app/features/app_library/data/repositories/shared_preferences_app_library_repository.dart';
import 'package:shared_preferences/shared_preferences.dart';

void main() {
  late SharedPreferencesAppLibraryRepository repository;

  setUp(() async {
    SharedPreferences.setMockInitialValues({});
    final prefs = await SharedPreferences.getInstance();
    repository = SharedPreferencesAppLibraryRepository(prefs);
  });

  group('loadRuntimeState', () {
    test('保存が無いappIdはnullを返す', () async {
      final result = await repository.loadRuntimeState('unknown_app');
      expect(result, isNull);
    });

    test('保存直後に同じ内容を読み込める', () async {
      await repository.saveRuntimeStateForScreen('app1', 'generated_screen', {
        'items': {
          'type': 'checklist',
          'value': [
            {'id': 'item_1', 'text': '牛乳', 'done': false},
          ],
        },
      });
      final result = await repository.loadRuntimeState('app1');
      expect(result, isNotNull);
      expect(result!['generated_screen']!['items']['value'][0]['text'], '牛乳');
    });
  });

  group('saveRuntimeStateForScreen', () {
    test('同じappIdの別画面のStateを上書きしない', () async {
      await repository.saveRuntimeStateForScreen('app1', 'screen_a', {'x': 1});
      await repository.saveRuntimeStateForScreen('app1', 'screen_b', {'y': 2});
      final result = await repository.loadRuntimeState('app1');
      expect(result!['screen_a'], {'x': 1});
      expect(result['screen_b'], {'y': 2});
    });

    test('同じ画面への2回目の保存は上書きする(履歴を残さない)', () async {
      await repository.saveRuntimeStateForScreen('app1', 'screen_a', {'x': 1});
      await repository.saveRuntimeStateForScreen('app1', 'screen_a', {'x': 2});
      final result = await repository.loadRuntimeState('app1');
      expect(result!['screen_a'], {'x': 2});
    });

    test('別のappIdのStateには影響しない', () async {
      await repository.saveRuntimeStateForScreen('app1', 'screen_a', {'x': 1});
      await repository.saveRuntimeStateForScreen('app2', 'screen_a', {'x': 999});
      final app1Result = await repository.loadRuntimeState('app1');
      expect(app1Result!['screen_a'], {'x': 1});
    });
  });

  group('deleteRuntimeState', () {
    test('保存済みのStateを削除できる', () async {
      await repository.saveRuntimeStateForScreen('app1', 'screen_a', {'x': 1});
      await repository.deleteRuntimeState('app1');
      final result = await repository.loadRuntimeState('app1');
      expect(result, isNull);
    });

    test('存在しないappIdを削除してもクラッシュしない', () async {
      await repository.deleteRuntimeState('never_existed');
      // 例外が投げられなければ成功。
    });

    test('他のappIdのStateには影響しない', () async {
      await repository.saveRuntimeStateForScreen('app1', 'screen_a', {'x': 1});
      await repository.saveRuntimeStateForScreen('app2', 'screen_a', {'x': 2});
      await repository.deleteRuntimeState('app1');
      final app1Result = await repository.loadRuntimeState('app1');
      final app2Result = await repository.loadRuntimeState('app2');
      expect(app1Result, isNull);
      expect(app2Result!['screen_a'], {'x': 2});
    });
  });

  test('壊れたJSONが保存されていても、読み込み時にクラッシュせず空扱いになる', () async {
    SharedPreferences.setMockInitialValues({'forge.app_runtime_state.v1': '{this is not json'});
    final prefs = await SharedPreferences.getInstance();
    final brokenRepository = SharedPreferencesAppLibraryRepository(prefs);
    final result = await brokenRepository.loadRuntimeState('app1');
    expect(result, isNull);
  });
}
