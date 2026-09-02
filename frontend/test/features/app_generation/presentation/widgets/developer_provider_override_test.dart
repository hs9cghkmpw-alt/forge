// 開発者向け UI は、**既定ビルドに存在しない**。
//
// ---
//
// 通常利用者へ Provider を選ばせないための削除は、開発者から
// 切り分け手段を奪ってよいという意味ではない。両立させる置き方は
// 「既定では消え、開発者ビルドにだけ出る」である。
//
// `kForgeDeveloperMode` は compile time 定数なので、既定ビルドで実行される
// このテストが確認できるのは**消えていること**である。開発者ビルドでの表示は
// `flutter test --dart-define=FORGE_DEVELOPER_MODE=true` で確認する
// （同じテストが、そのときは「出ていて、実際に操作できること」を確認する）。

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:forge_app/core/config/developer_mode.dart';
import 'package:forge_app/features/app_generation/presentation/widgets/developer_provider_override.dart';

void main() {
  testWidgets('既定ビルドでは何も描かず、開発者ビルドでだけ実際に操作できる', (tester) async {
    await tester.pumpWidget(const ProviderScope(
      child: MaterialApp(home: Scaffold(body: DeveloperProviderOverride())),
    ));
    await tester.pump();

    if (kForgeDeveloperMode) {
      // 押せるのに何も起きない飾りにしない。
      expect(find.byType(DropdownButton<String?>), findsOneWidget);
      return;
    }
    expect(find.byType(DropdownButton<String?>), findsNothing);
  });
}
