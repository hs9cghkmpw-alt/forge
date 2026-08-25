import 'package:flutter_test/flutter_test.dart';
import 'package:forge_app/forge_019_visual.dart';
import 'package:forge_app/forge_019a_visual_fixture.dart';
import 'package:forge_app/json_ui/schema/forge_document.dart';

/// 撮影に使う文書が、**本番の出力**であることの回帰（FORGE-019A §7）。
///
/// 019は Before / After の両方を手書きしており、Backendが実際に作る
/// After とは別物だった。さらに Before は本番のValidatorに通らない
/// 文書だった（`negative_when` に `sign_field` が無い）。Dart側は
/// `fromJson` が通ることしか見ていなかったので気付けなかった。
///
/// Validatorそのものの照合と生成物との一致は
/// `backend/tests/test_visual_fixture_provenance.py` が行う。
/// ここでは **Flutter側が生成物をそのまま使っていること** を見る。
void main() {
  String roleOf(List<dynamic> children, String id) =>
      (children.firstWhere((dynamic child) => (child as Map)['id'] == id) as Map)['style_role']
          as String;

  List<dynamic> childrenOf(Map<String, dynamic> document) =>
      ((document['screens'] as List).first as Map)['body']['children'] as List<dynamic>;

  test('撮影用の文書は生成されたfixtureをそのまま使う', () {
    expect(forge019FinanceDocument(after: false), forge019aBeforeDocument());
    expect(forge019FinanceDocument(after: true), forge019aAfterDocument());
  });

  test('本番のschemaでparseできる', () {
    expect(() => ForgeDocument.fromJson(forge019aBeforeDocument()), returnsNormally);
    expect(() => ForgeDocument.fromJson(forge019aAfterDocument()), returnsNormally);
  });

  test('Afterは残高を主KPIへ、収入をfinance語彙へ移している', () {
    final before = childrenOf(forge019aBeforeDocument());
    final after = childrenOf(forge019aAfterDocument());

    expect(roleOf(before, 'balance'), 'metric.secondary');
    expect(roleOf(after, 'balance'), 'metric.primary');
    expect(roleOf(before, 'income'), 'metric.primary');
    expect(roleOf(after, 'income'), 'finance.income');
  });

  test('触っていないwidgetは1バイトも変わらない', () {
    final before = childrenOf(forge019aBeforeDocument());
    final after = childrenOf(forge019aAfterDocument());
    expect(after.length, before.length);
    for (var i = 0; i < before.length; i++) {
      final id = (before[i] as Map)['id'];
      if (id == 'income' || id == 'balance') continue;
      expect(after[i], before[i], reason: '$id が変わっている');
    }
  });

  test('系譜がどの操作の絵かを名乗る', () {
    final provenance = forge019aProvenance();
    expect(provenance['revision_mode'], 'local_semantic_patch');
    expect(provenance['semantic_operation'], 'select_primary_metric');
    expect(provenance['validator_passed'], isTrue);
    expect(provenance['critic_passed'], isTrue);
  });

  test('失効するIDを絵へ焼き込まない', () {
    final provenance = forge019aProvenance().toString();
    for (final forbidden in <String>['artifact_id', 'version_token', 'document_binding']) {
      expect(provenance.contains(forbidden), isFalse, reason: forbidden);
    }
  });
}
