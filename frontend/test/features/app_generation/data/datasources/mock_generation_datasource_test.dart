// MockGenerationDataSource Test(FORGE-RUNTIME-001 Task 3、静的監査対応)。
//
// backend/tests/test_mock_generator.py と同じ観点(8種のInspiration Card全対応・
// 「子ども」vs「持ち物」の判定順衝突の回帰)に加え、Dart版ならではの利点として、
// 生成したMapを実際に `ForgeDocument.fromJson()` へ通し、Runtime側のパーサーが
// 例外を投げずに受理できることまで確認する(擬似End-to-End)。
//
// 注記: `analysis_options.yaml` で `strict-casts`/`strict-inference` を
// 有効にしているため、`dynamic`の暗黙アクセスに頼らず、全箇所で明示的に
// `as Map<String, dynamic>` / `as List<dynamic>` へキャストしている
// (FORGE-MERGE-005で達成した analyze 0 issues を壊さないため)。
//
// 注記2: Claudeのサンドボックスに Dart SDK が無いため、このファイルは
// 一度も `flutter test` で実行されていない。CEO環境での実行が必須。

import 'package:flutter_test/flutter_test.dart';
import 'package:forge_app/features/app_generation/data/datasources/mock_generation_datasource.dart';
import 'package:forge_app/json_ui/schema/forge_document.dart';

String _titleOf(Map<String, dynamic> doc) {
  final app = doc['app'] as Map<String, dynamic>;
  return app['title'] as String;
}

List<String> _itemTextsOf(Map<String, dynamic> doc) {
  final screens = doc['screens'] as List<dynamic>;
  final screen = screens[0] as Map<String, dynamic>;
  final state = screen['state'] as Map<String, dynamic>;
  final items = state['items'] as Map<String, dynamic>;
  final value = items['value'] as List<dynamic>;
  return value.map((dynamic e) => (e as Map<String, dynamic>)['text'] as String).toList();
}

void main() {
  const source = MockGenerationDataSource();

  group('カテゴリ判定', () {
    test('買い物キーワードで買い物メモになる', () {
      final doc = source.generate('買い物メモを作って');
      expect(_titleOf(doc), '買い物メモ');
      expect(_itemTextsOf(doc), ['卵', '牛乳', '食パン', '野菜', '洗剤']);
    });

    test('空入力は汎用フォールバックになる', () {
      final doc = source.generate('   ');
      expect(_titleOf(doc), '新しいリスト');
    });

    test('未対応の入力はそのままタイトルになる', () {
      final doc = source.generate('犬の名前を考える');
      expect(_titleOf(doc), '犬の名前を考える');
    });
  });

  group('8種のInspiration Card全対応(Python版と同じ回帰テスト)', () {
    const cases = <String, String>{
      '今日の晩ご飯を考えるメモを作って': '今日のご飯メモ',
      '買い物メモを作って': '買い物メモ',
      '旅行の持ち物チェックを作って': '旅行の持ち物チェック',
      '家計簿をつけるメモを作って': '家計簿',
      '今日の予定リストを作って': '今日の予定',
      '子どもの持ち物チェックを作って': '子どもの持ち物チェック',
      'ペットのお世話チェックリストを作って': 'ペットのお世話チェック',
      'プレゼントのアイデアリストを作って': 'プレゼントのアイデア',
    };

    for (final entry in cases.entries) {
      test('"${entry.key}" -> "${entry.value}"', () {
        expect(_titleOf(source.generate(entry.key)), entry.value);
      });
    }

    test('「子どもの持ち物チェック」が「持ち物」キーワードで旅行に誤分類されない', () {
      final items = _itemTextsOf(source.generate('子どもの持ち物チェックを作って'));
      expect(items, contains('オムツ'));
      expect(items, isNot(contains('パスポート')));
    });
  });

  group('生成結果はForgeDocument.fromJson()で例外なくパースできる(擬似E2E)', () {
    const phrases = <String>[
      '買い物メモを作って', 'todoリストを作って', '今日の晩ご飯を考えるメモを作って',
      '家計簿をつけるメモを作って', '今日の予定リストを作って', '子どもの持ち物チェックを作って',
      'ペットのお世話チェックリストを作って', 'プレゼントのアイデアリストを作って',
      '旅行の持ち物チェックを作って', '', '適当な入力文字列123',
    ];

    for (final phrase in phrases) {
      test('入力="$phrase"がパース可能', () {
        final raw = source.generate(phrase);
        final parsed = ForgeDocument.fromJson(raw);
        expect(parsed.screens, hasLength(1));
        expect(parsed.screenById(parsed.initialScreenId), isNotNull);
      });
    }
  });
}
