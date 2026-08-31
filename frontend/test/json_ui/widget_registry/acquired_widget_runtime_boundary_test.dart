// 獲得した Capability の widget が「実際に描かれる側（Dart）」に
// 到達しているかどうかの**境界**を固定するテスト（020F）。
//
// Backend の Validator（生成物を検査する仕組み）は 020F で、
// 実ビルド済み（runtime attested）な獲得能力の widget 型を通すように
// なった。しかし Validator を通ることは「描ける」ことではない。
//
// このテストは、今この瞬間の Dart 側の事実を記録して固定する。
//
//   1. 未知の型は例外にならず ForgeUnknownWidgetNode になる
//   2. Renderer は Fallback（代替表示）へ倒す — **描かれない**
//   3. Registry へ後から登録しても**描かれない**
//      （Parser の switch が先に握り潰しているため）
//
// 3 が、獲得能力を Dart まで通すために次に開けるべき穴である。
// Registry だけを拡張点だと思って作業すると必ず外す。

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:forge_app/json_ui/renderer/forge_runtime_state.dart';
import 'package:forge_app/json_ui/schema/forge_document.dart';
import 'package:forge_app/json_ui/widget_registry/widget_registry.dart';

/// 出荷済み Dart binary が知らない、獲得能力の widget 型。
const String acquiredWidgetType = 'acquired_grid_view';

Map<String, dynamic> acquiredWidgetJson() => <String, dynamic>{
      'type': acquiredWidgetType,
      'id': 'acquired_grid',
      'properties': <String, dynamic>{},
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
  test('未知の型は例外ではなく、型名を保ったまま Unknown ノードになる', () {
    final node = ForgeWidgetNode.fromJson(acquiredWidgetJson(), '/body');
    expect(node, isA<ForgeUnknownWidgetNode>());
    expect((node as ForgeUnknownWidgetNode).rawType, acquiredWidgetType);
  });

  test('出荷済み Registry は獲得能力の型を知らない', () {
    expect(buildDefaultForgeRegistry().registeredTypes,
        isNot(contains(acquiredWidgetType)));
  });

  testWidgets('獲得能力の widget は描かれず Fallback へ倒れる', (tester) async {
    final node = ForgeWidgetNode.fromJson(acquiredWidgetJson(), '/body');
    await pumpNode(tester, node, buildDefaultForgeRegistry());
    expect(find.byType(ForgeFallbackWidget), findsOneWidget,
        reason: 'Validator を通っても、Dart 側は描けない');
  });

  testWidgets('Registry へ登録しても描かれない — 拡張点は Parser 側にある',
      (tester) async {
    var builderWasCalled = false;
    final registry = buildDefaultForgeRegistry()
      ..register(acquiredWidgetType, (context, node, state, recurse) {
        builderWasCalled = true;
        return const Text('獲得した widget');
      });

    final node = ForgeWidgetNode.fromJson(acquiredWidgetJson(), '/body');
    await pumpNode(tester, node, registry);

    expect(builderWasCalled, isFalse,
        reason: 'Parser が先に Unknown へ倒すので Registry まで届かない');
    expect(find.text('獲得した widget'), findsNothing);
    expect(find.byType(ForgeFallbackWidget), findsOneWidget);
  });
}
