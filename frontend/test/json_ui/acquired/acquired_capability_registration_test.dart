// 獲得能力の**登録**そのものの不変条件（TD94）。
//
// 実際に Forge のアプリへ載って描かれるところは
// `test_acquired/acquired_capability_e2e_test.dart` が見る。
// ここが見るのは登録の門である。

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:forge_app/json_ui/acquired/acquired_capability.dart';
import 'package:forge_app/json_ui/acquired/acquired_capabilities.dart';
import 'package:forge_app/json_ui/renderer/forge_runtime_state.dart';
import 'package:forge_app/json_ui/schema/acquired_widget_types.dart';
import 'package:forge_app/json_ui/schema/forge_document.dart';
import 'package:forge_app/json_ui/widget_registry/widget_registry.dart';

Widget _build(
  BuildContext context,
  ForgeWidgetNode node,
  ForgeRuntimeState state,
  Widget Function(ForgeWidgetNode child) recurse,
) =>
    const Text('描いた');

ForgeAcquiredCapability _capability({
  String capabilityId = 'view.demo',
  String typeName = 'demo_view',
}) =>
    ForgeAcquiredCapability(
      capabilityId: capabilityId,
      spec: ForgeAcquiredWidgetSpec(typeName: typeName),
      build: _build,
    );

void main() {
  tearDown(resetAcquiredCapabilityRegistrationForTest);

  test('登録すると Parser 側と描き方の両方が入る', () {
    registerAcquiredCapability(_capability());
    expect(forgeAcquiredWidgetTypes.specFor('demo_view'), isNotNull);
    expect(forgeAcquiredWidgetBuilders['demo_view'], isNotNull);
  });

  test('別の能力が同じ widget 型を奪えない', () {
    // 静かに差し替わるのは事故である。落とす。
    registerAcquiredCapability(_capability(capabilityId: 'view.demo'));
    expect(
      () => registerAcquiredCapability(_capability(capabilityId: 'view.other')),
      throwsStateError,
    );
  });

  test('同じ能力の再登録は通る（二重呼び出しで壊れない）', () {
    registerAcquiredCapability(_capability());
    expect(() => registerAcquiredCapability(_capability()), returnsNormally);
  });

  test('Registry を組むと獲得した描き方が入る', () {
    registerAcquiredCapability(_capability());
    expect(buildDefaultForgeRegistry().resolve('demo_view'), isNotNull);
  });

  test('登録していない型は Registry が解決しない', () {
    expect(buildDefaultForgeRegistry().resolve('never_acquired_view'), isNull);
  });
}
