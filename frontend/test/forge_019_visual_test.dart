import 'package:flutter_test/flutter_test.dart';
import 'package:forge_app/forge_019_visual.dart';
import 'package:forge_app/json_ui/schema/forge_document.dart';

void main() {
  test('FORGE-019 visual fixtures parse through the production schema', () {
    expect(() => ForgeDocument.fromJson(forge019FinanceDocument(after: false)), returnsNormally);
    expect(() => ForgeDocument.fromJson(forge019FinanceDocument(after: true)), returnsNormally);
  });

  test('before and after differ only in the intended metric roles', () {
    final before = forge019FinanceDocument(after: false);
    final after = forge019FinanceDocument(after: true);
    final beforeChildren = (before['screens'] as List).first['body']['children'] as List;
    final afterChildren = (after['screens'] as List).first['body']['children'] as List;
    expect(beforeChildren[1]['style_role'], 'metric.primary');
    expect(afterChildren[1]['style_role'], 'finance.income');
    expect(beforeChildren[2]['style_role'], 'metric.secondary');
    expect(afterChildren[2]['style_role'], 'metric.primary');
    for (final index in [0, 3, 4, 5, 6]) {
      expect(afterChildren[index], beforeChildren[index]);
    }
  });
}
