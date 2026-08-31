// 獲得した Capability の widget が、**実際に Flutter で描かれる**こと（020F 後半）。
//
// 前半（backend Validator）は
// `backend/tests/test_forge_020f_runtime_attested_widgets.py` で閉じた。
// ここは後半——Validator を通った widget が Dart の runtime へ届くか。
//
// 獲得能力の生成コードは、載るときに**2つとも**自分で登録する。
//
//   1. Parser 側の受け口 `forgeAcquiredWidgetTypes`（型と必須 property の宣言）
//   2. Widget Registry（実際の描き方）
//
// **片方だけでは描かない。** 描けないものを「描けたことにしない」ためである。

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:forge_app/json_ui/renderer/forge_runtime_state.dart';
import 'package:forge_app/json_ui/schema/acquired_widget_types.dart';
import 'package:forge_app/json_ui/schema/forge_document.dart';
import 'package:forge_app/json_ui/widget_registry/widget_registry.dart';

const String acquiredType = 'acquired_grid_view';

/// 獲得能力の生成コードが行う登録を模した最小の形。
/// **Forge 本体に capability ごとの分岐は無い。**
void registerAcquiredParserSpec() {
  forgeAcquiredWidgetTypes.register(const ForgeAcquiredWidgetSpec(
    typeName: acquiredType,
    requiredProperties: <String>['columns'],
  ));
}

ForgeWidgetRegistry registryWithAcquiredBuilder() {
  return buildDefaultForgeRegistry()
    ..register(acquiredType, (context, node, state, recurse) {
      final acquired = node as ForgeAcquiredWidgetNode;
      return Text('列数: ${acquired.properties['columns']}');
    });
}

/// 生成 Document は widget の属性を**平らに**持つ（出荷済みの型と同じ）。
Map<String, dynamic> acquiredJson({Map<String, dynamic>? properties}) =>
    <String, dynamic>{
      'type': acquiredType,
      'id': 'acquired_grid',
      ...(properties ?? <String, dynamic>{'columns': 3}),
    };

Future<void> pumpNode(WidgetTester tester, ForgeWidgetNode node,
    ForgeWidgetRegistry registry) async {
  final runtime = ForgeRuntimeState(const <String, ForgeStateValue>{});
  await tester.pumpWidget(MaterialApp(
    home: Builder(
      builder: (context) => buildForgeWidget(
          context, node, runtime, registry, (_) => const SizedBox.shrink()),
    ),
  ));
}

void main() {
  tearDown(forgeAcquiredWidgetTypes.clear);

  test('宣言していない型は登録されていない', () {
    // 「表が空である」ではなく「**この型が**入っていない」を見る。
    // 実際に能力を獲得した checkout では表は空でないのが正しく、
    // 空を期待すると獲得を壊れたことにしてしまう。
    expect(forgeAcquiredWidgetTypes.registeredTypes,
        isNot(contains(acquiredType)));
  });

  testWidgets('両方登録すれば、獲得 widget は実際に描かれる', (tester) async {
    registerAcquiredParserSpec();
    final node = ForgeWidgetNode.fromJson(acquiredJson(), '/body');

    expect(node, isA<ForgeAcquiredWidgetNode>());
    expect((node as ForgeAcquiredWidgetNode).rawType, acquiredType);

    await pumpNode(tester, node, registryWithAcquiredBuilder());

    expect(find.text('列数: 3'), findsOneWidget);
    expect(find.byType(ForgeFallbackWidget), findsNothing);
  });

  testWidgets('Parser だけ登録して描き方が無ければ描かない（fail-closed）',
      (tester) async {
    registerAcquiredParserSpec();
    final node = ForgeWidgetNode.fromJson(acquiredJson(), '/body');
    await pumpNode(tester, node, buildDefaultForgeRegistry());
    expect(find.byType(ForgeFallbackWidget), findsOneWidget,
        reason: '描き方を持たない型を、描けたことにしない');
  });

  testWidgets('Registry だけ登録して Parser の宣言が無ければ描かない',
      (tester) async {
    final node = ForgeWidgetNode.fromJson(acquiredJson(), '/body');
    expect(node, isA<ForgeUnknownWidgetNode>());
    await pumpNode(tester, node, registryWithAcquiredBuilder());
    expect(find.text('列数: 3'), findsNothing);
    expect(find.byType(ForgeFallbackWidget), findsOneWidget);
  });

  test('必須 property が欠けていれば parse で落ちる', () {
    registerAcquiredParserSpec();
    expect(
      () => ForgeWidgetNode.fromJson(
          acquiredJson(properties: <String, dynamic>{}), '/body'),
      throwsA(isA<ForgeParseException>()),
      reason: '足りないまま黙って空の widget を描かない',
    );
  });

  test('出荷済みの型は、この表では乗っ取れない', () {
    forgeAcquiredWidgetTypes.register(
        const ForgeAcquiredWidgetSpec(typeName: 'text'));
    final node = ForgeWidgetNode.fromJson(
        const <String, dynamic>{'type': 'text', 'id': 't', 'value': 'こんにちは'},
        '/body');
    expect(node, isA<ForgeTextWidgetNode>(),
        reason: 'switch が先に一致するので獲得側から奪えない');
  });

  test('空の型名は登録できない', () {
    expect(
      () => forgeAcquiredWidgetTypes
          .register(const ForgeAcquiredWidgetSpec(typeName: '')),
      throwsArgumentError,
    );
  });
}
