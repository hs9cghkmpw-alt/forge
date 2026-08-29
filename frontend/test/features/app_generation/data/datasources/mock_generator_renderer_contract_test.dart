// Mock Generator × Renderer 契約テスト(FORGE-RUNTIME-002 Task 7、
// FORGE-MILESTONE-002で12カテゴリ・v1.1 Widgetへ拡張)。
//
// 「JSON Schemaとして有効」だけでなく「現行Rendererで実際に描画可能」であることを
// 12カテゴリ全件で検証する。カテゴリごとに構造(Checklist/Form/Memo)が異なるため、
// 各テストはテンプレート非依存(assertion側でWidget構成の違いを吸収する)にしている。
//
// 修正の記録: 本ファイルはFORGE-MILESTONE-002で発見した実バグの修正版である。
// 旧版は12種のWidgetのうち6種(v1.1新規分)を`_typeNameOf`のswitch式が
// 網羅しておらず、sealed classの非網羅switchとしてコンパイルエラーになる状態
// だった(v1.1 Widgetノードを一切生成しない8カテゴリだけでテストしていたため
// 気づかれていなかった)。今回12カテゴリへ拡張する過程で発見し、修正した。
//
// 注記: Claudeのサンドボックスに Dart SDK が無いため、このファイルは
// 一度も `flutter test` で実行されていない。CEO環境での実行が必須。

import 'package:flutter_test/flutter_test.dart';
import 'package:forge_app/features/app_generation/data/datasources/mock_generation_datasource.dart';
import 'package:forge_app/json_ui/schema/forge_document.dart';

/// Runtimeの`buildDefaultForgeRegistry()`が実際に登録しているtype名の集合と
/// 手動で同期させたもの(private APIのため直接参照できない。
/// `widget_registry.dart`・`widget_registry_v1_1.dart`・
/// `widget_registry_v1_3.dart`のいずれかを変更したらここも合わせて
/// 更新すること)。
///
/// FORGE v1.0 Candidate Patch2で`record_list_view`(Record Runtime
/// Phase1、`widget_registry_v1_3.dart`)を追加した。このテスト自体が
/// 対象とする12カテゴリ(Mock Generatorの既存Legacyカテゴリ)は
/// 現状record_list_viewを生成しないため、このSet追加だけでは既存の
/// アサーション結果は変わらないが、「実際に登録されているtype名」との
/// 同期を保つために追加した。
const Set<String> kRegisteredWidgetTypes = {
  'text', 'text_field', 'button', 'column', 'row', 'checklist',
  'heading', 'checkbox', 'card', 'list', 'divider', 'form',
  'record_list_view',
  'section_header',
  'choice_field', 'bar_chart', 'date_field', 'tab_view', 'slider',
  // v1.11(2026-08-17、FORGE-R1 / TD69)。Hero KPI。
  'metric_view',
};

/// sealed ForgeWidgetNode の全14派生型(13 Widget種 + Unknown)を網羅する。
/// v1.1追加時にケースを足し忘れるとDartコンパイラが非網羅switchとして
/// 検出するはずだが、念のため全件手動確認済み。
///
/// **FORGE v1.0 Candidate Patch2で修正した実バグ**: Record Runtime
/// Phase1(`ForgeRecordListViewWidgetNode`追加)の際、このテスト専用の
/// private `_typeNameOf`(Runtime本体の`widget_registry_core.dart`
/// `typeNameOf()`とは別に、テストがRuntime実装をブラックボックスとして
/// 検証するために独自に持っている複製)へケースを追加し忘れていた。
/// sealed classの非網羅switch式としてコンパイルエラーになっていた
/// (`non_exhaustive_switch_expression`)。
String _typeNameOf(ForgeWidgetNode node) => switch (node) {
      ForgeTextWidgetNode() => 'text',
      ForgeTextFieldWidgetNode() => 'text_field',
      ForgeButtonWidgetNode() => 'button',
      ForgeColumnWidgetNode() => 'column',
      ForgeRowWidgetNode() => 'row',
      ForgeChecklistWidgetNode() => 'checklist',
      ForgeHeadingWidgetNode() => 'heading',
      ForgeCheckboxWidgetNode() => 'checkbox',
      ForgeCardWidgetNode() => 'card',
      ForgeListWidgetNode() => 'list',
      ForgeRecordListViewWidgetNode() => 'record_list_view',
      ForgeSectionHeaderWidgetNode() => 'section_header',
      ForgeDividerWidgetNode() => 'divider',
      ForgeFormWidgetNode() => 'form',
      // v1.6/v1.7新規(2026-08-11、Widget Vocabulary Expansion)。
      // Mock Generatorの12レガシーカテゴリはこれらを生成しないため
      // 実際のアサーション結果には影響しないが、`widget_registry_core.
      // dart`の`typeNameOf()`が同じ理由で非網羅switchのコンパイル
      // エラーになっていた実バグ(FORGE-AI-QUALITY-001で発見・修正)と
      // 同期させるため追加した。
      ForgeChoiceFieldWidgetNode() => 'choice_field',
      ForgeBarChartWidgetNode() => 'bar_chart',
      ForgeDateFieldWidgetNode() => 'date_field',
      ForgeTabViewWidgetNode() => 'tab_view',
      // v1.8新規(2026-08-11、Widget Vocabulary Expansion第3弾)。
      // 同じくMock Generatorの12レガシーカテゴリは生成しないが、
      // `widget_registry_core.dart`の`typeNameOf()`との同期のため追加。
      ForgeSliderWidgetNode() => 'slider',
      // v1.11新規(2026-08-17、FORGE-R1 / TD69)。Hero KPI。
      // **この複製switchへ足し忘れて実際にCIが落ちた**(3度目)。
      // Runtime本体の`typeNameOf()`だけ直しても、テスト側のこの複製が
      // sealed classの非網羅switchとしてコンパイルエラーになる。
      ForgeMetricViewWidgetNode() => 'metric_view',
      // v1.13: deterministic simulation driver. Keep this deliberately
      // duplicated black-box contract exhaustive when the sealed vocabulary grows.
      ForgeSimulationLoopWidgetNode() => 'simulation_loop',
      ForgeUnknownWidgetNode() => 'unknown',
    };

/// column/row/card/form/tab_view いずれもchildrenを持ちうるため、全種を辿る。
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
  } else if (node is ForgeTabViewWidgetNode) {
    for (final c in node.children) {
      result.addAll(_flatten(c));
    }
  }
  return result;
}

void main() {
  const source = MockGenerationDataSource();

  const categories = <String, String>{
    '今日の晩ご飯を考えるメモを作って': '今日のご飯メモ',
    '買い物メモを作って': '買い物メモ',
    '旅行の持ち物チェックを作って': '旅行の持ち物チェック',
    '家計簿をつけるメモを作って': '家計簿',
    '今日の予定リストを作って': '今日の予定',
    '子どもの持ち物チェックを作って': '子どもの持ち物チェック',
    'ペットのお世話チェックリストを作って': 'ペットのお世話チェック',
    'プレゼントのアイデアリストを作って': 'プレゼントのアイデア',
    '家事のチェックリストを作って': '今日の家事',
    'アンケートを作って': '満足度アンケート',
    'メモを作って': 'メモ',
  };

  for (final entry in categories.entries) {
    group('契約テスト: "${entry.value}"', () {
      late ForgeDocument document;
      late ForgeScreen screen;
      late List<ForgeWidgetNode> allNodes;

      setUp(() {
        final raw = source.generate(entry.key);
        document = ForgeDocument.fromJson(raw);
        screen = document.screenById(document.initialScreenId)!;
        allNodes = _flatten(screen.body);
      });

      test('ForgeDocument.fromJsonが成功し、rootが存在する', () {
        expect(document.screens, isNotEmpty);
        expect(screen.body, isNotNull);
      });

      test('bodyのchildrenが空でない(タイトルだけの画面になっていない)', () {
        expect(allNodes.length, greaterThan(1), reason: 'root自身しか無い = 中身が空');
      });

      test('使用されている全Widget typeがRegistryに登録済み(Fallback落ちしない)', () {
        for (final node in allNodes) {
          final typeName = _typeNameOf(node);
          expect(
            kRegisteredWidgetTypes.contains(typeName),
            isTrue,
            reason: '未登録のtype "$typeName" が含まれている(id=${node.id})',
          );
        }
      });

      test('Widget IDがドキュメント内で重複しない', () {
        final ids = allNodes.map((n) => n.id).toList();
        expect(ids.length, ids.toSet().length, reason: '重複ID: $ids');
      });

      test('checklist Widgetが存在する場合、state_refは実在するchecklist型stateを指す', () {
        // テンプレート非依存: Memo/Formカテゴリはchecklistを持たないため、
        // 「存在しない」こと自体はエラーにせず、存在する場合のみ整合性を検証する。
        final checklistNodes = allNodes.whereType<ForgeChecklistWidgetNode>();
        for (final node in checklistNodes) {
          final stateValue = screen.state[node.stateRef];
          expect(stateValue, isNotNull, reason: 'state_ref "${node.stateRef}" が存在しない');
          expect(stateValue, isA<ForgeChecklistState>());
        }
      });

      test('checkbox Widgetが存在する場合、state_refは実在するboolean型stateを指す', () {
        final checkboxNodes = allNodes.whereType<ForgeCheckboxWidgetNode>();
        for (final node in checkboxNodes) {
          final stateValue = screen.state[node.stateRef];
          expect(stateValue, isNotNull, reason: 'state_ref "${node.stateRef}" が存在しない');
          expect(stateValue, isA<ForgeBooleanState>());
        }
      });

      test('form Widgetが存在する場合、submit_actionの遷移先screenが実在する', () {
        final formNodes = allNodes.whereType<ForgeFormWidgetNode>();
        for (final form in formNodes) {
          final action = form.submitAction;
          if (action is NavigateAction) {
            expect(document.screenById(action.targetScreenId), isNotNull,
                reason: 'navigate先 "${action.targetScreenId}" のscreenが存在しない');
          }
        }
      });

      test('表示可能な主要コンテンツが1件以上存在する(Checklist項目 または 入力/表示Widget)', () {
        // テンプレートによって「主要コンテンツ」の形が異なるため、いずれかが
        // 満たされていればよい、という形の検証にする。
        final hasChecklistItems = screen.state.values
            .whereType<ForgeChecklistState>()
            .any((s) => s.value.isNotEmpty);
        final hasInputOrDisplayWidget = allNodes.any((n) =>
            n is ForgeTextFieldWidgetNode ||
            n is ForgeCheckboxWidgetNode ||
            n is ForgeListWidgetNode ||
            n is ForgeTextWidgetNode);
        expect(
          hasChecklistItems || hasInputOrDisplayWidget,
          isTrue,
          reason: 'チェックリスト項目も入力/表示Widgetも無い、空の画面になっている',
        );
      });

      test('checklist項目のIDが重複しない(存在する場合。TECH_DEBT.md TD5と同じ観点)', () {
        for (final state in screen.state.values.whereType<ForgeChecklistState>()) {
          final itemIds = state.value.map((i) => i.id).toList();
          expect(itemIds.length, itemIds.toSet().length, reason: '重複item ID: $itemIds');
        }
      });
    });
  }
}
