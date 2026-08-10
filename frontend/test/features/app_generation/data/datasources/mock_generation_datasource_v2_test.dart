// Mock Generator v2(Dart版)の新規カテゴリのテスト(FORGE-MILESTONE-002 PHASE5/9)。
//
// Python版(test_mock_generator_v2.py)と同じ観点を検証する。
//
// 注記: Claudeのサンドボックスに Dart SDK が無いため、このファイルは
// 一度も `flutter test` で実行されていない。CEO環境での実行が必須。

import 'package:flutter_test/flutter_test.dart';
import 'package:forge_app/features/app_generation/data/datasources/mock_generation_datasource.dart';
import 'package:forge_app/json_ui/schema/forge_document.dart';

void main() {
  const source = MockGenerationDataSource();

  group('Household(家事)カテゴリ', () {
    test('家事キーワードで今日の家事になる', () {
      final doc = source.generate('今日の家事リストを作って');
      expect(doc['app']['title'], '今日の家事');
      expect(doc['version'], '1.0');
    });

    test('家事と家計簿は誤分類されない', () {
      final household = source.generate('掃除のチェックリストを作って');
      expect(household['app']['title'], '今日の家事');
      final budget = source.generate('家計簿をつけたい');
      expect(budget['app']['title'], '家計簿');
    });

    test('生成結果はForgeDocument.fromJsonでパースできる', () {
      final doc = source.generate('家事のチェックリストを作って');
      expect(() => ForgeDocument.fromJson(doc), returnsNormally);
    });
  });

  group('Survey(アンケート)カテゴリ → Formテンプレート', () {
    test('アンケートキーワードでform構造になる', () {
      final doc = source.generate('満足度アンケートを作って');
      // FORGE-MILESTONE-003でコメント欄にvalidation(max_length)を追加したため、
      // v1.1からv1.2へ更新した(validationはv1.2専用プロパティ)。
      expect(doc['version'], '1.2');
      expect((doc['screens'] as List).length, 2, reason: 'Formテンプレートは送信先画面込みで2画面のはず');
    });

    test('生成結果はForgeDocument.fromJsonでパースでき、formとcardを含む', () {
      final raw = source.generate('アンケートを作って');
      final parsed = ForgeDocument.fromJson(raw);
      final screen = parsed.screenById(parsed.initialScreenId)!;
      final nodes = _flatten(screen.body);
      expect(nodes.whereType<ForgeFormWidgetNode>(), isNotEmpty);
      expect(nodes.whereType<ForgeCardWidgetNode>(), isNotEmpty);
      expect(nodes.whereType<ForgeCheckboxWidgetNode>(), isNotEmpty);
      expect(nodes.whereType<ForgeHeadingWidgetNode>(), isNotEmpty);
    });

    test('submit_actionはnavigateで、遷移先画面が実在する', () {
      final raw = source.generate('survey');
      final parsed = ForgeDocument.fromJson(raw);
      final screen = parsed.screenById(parsed.initialScreenId)!;
      final form = _flatten(screen.body).whereType<ForgeFormWidgetNode>().first;
      final action = form.submitAction;
      expect(action, isA<NavigateAction>());
      final targetId = (action as NavigateAction).targetScreenId;
      expect(parsed.screenById(targetId), isNotNull);
    });
  });

  group('Memo(メモ)カテゴリ', () {
    test('メモキーワードでMemoテンプレートになる(checklistを含まない)', () {
      final raw = source.generate('メモを作って');
      final parsed = ForgeDocument.fromJson(raw);
      final screen = parsed.screenById(parsed.initialScreenId)!;
      final nodes = _flatten(screen.body);
      expect(nodes.whereType<ForgeTextFieldWidgetNode>().length, 1);
      expect(nodes.whereType<ForgeHeadingWidgetNode>(), isNotEmpty);
      expect(nodes.whereType<ForgeChecklistWidgetNode>(), isEmpty);
    });

    test('「買い物メモ」のメモには反応せず、買い物カテゴリのままになる', () {
      final doc = source.generate('買い物メモを作って');
      expect(doc['app']['title'], '買い物メモ');
      final parsed = ForgeDocument.fromJson(doc);
      final screen = parsed.screenById(parsed.initialScreenId)!;
      expect(_flatten(screen.body).whereType<ForgeChecklistWidgetNode>(), isNotEmpty);
    });
  });

  group('12カテゴリ全件がパース可能', () {
    const phrases = [
      '買い物メモを作って', 'todoリストを作って', '今日の晩ご飯を考えるメモを作って',
      '家計簿をつけるメモを作って', '今日の予定リストを作って', '子どもの持ち物チェックを作って',
      'ペットのお世話チェックリストを作って', 'プレゼントのアイデアリストを作って',
      '旅行の持ち物チェックを作って', '家事のチェックリストを作って',
      '満足度アンケートを作って', 'メモを作って',
    ];

    for (final phrase in phrases) {
      test('入力="$phrase"がパース可能', () {
        final raw = source.generate(phrase);
        expect(() => ForgeDocument.fromJson(raw), returnsNormally);
      });
    }
  });
}

List<ForgeWidgetNode> _flatten(ForgeWidgetNode node) {
  final result = <ForgeWidgetNode>[node];
  if (node is ForgeColumnWidgetNode) {
    for (final c in node.children) {
      result.addAll(_flatten(c));
    }
  } else if (node is ForgeRowWidgetNode) {
    for (final c in node.children) {
      result.addAll(_flatten(c));
    }
  } else if (node is ForgeCardWidgetNode) {
    for (final c in node.children) {
      result.addAll(_flatten(c));
    }
  } else if (node is ForgeFormWidgetNode) {
    for (final c in node.children) {
      result.addAll(_flatten(c));
    }
  }
  return result;
}
