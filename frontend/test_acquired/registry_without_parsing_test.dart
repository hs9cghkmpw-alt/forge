// **parse を経ずに Registry を組んだ場合**でも、獲得能力が入っていること。
//
// ## なぜ別ファイルなのか
//
// 同じファイルの中では、先に走ったテストの parse が
// `ensureAcquiredCapabilitiesRegistered()` を呼んでしまう。すると
// 「Registry 側の呼び出しが要るのかどうか」を確かめられない。
//
// 実際、配線破壊試験でこれが露見した（T2）。`buildDefaultForgeRegistry()`
// から登録呼び出しを外しても、どのテストも落ちなかった——**置物**である。
// Flutter はファイルごとに別 isolate で走るので、ここを独立させることで
// 「Registry を最初に組む」経路を実際に検査できる。
//
// このファイルでは **parse を一切しない。**

import 'package:flutter_test/flutter_test.dart';

import 'package:forge_app/json_ui/widget_registry/widget_registry.dart';

void main() {
  test('parse していなくても Registry は獲得 widget を解決する', () {
    // ここが最初の一手である。ForgeDocument.fromJson は呼ばない。
    final registry = buildDefaultForgeRegistry();
    expect(registry.resolve('calendar_view'), isNotNull,
        reason: 'Registry 側で獲得能力の登録を呼んでいない');
  });
}
