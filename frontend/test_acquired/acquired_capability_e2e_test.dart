// **獲得した Capability が、Forge のアプリで実際に描かれる**（TD94）。
//
// ---
//
// ## このディレクトリが `test/` の外にある理由
//
// このテストは `scripts/acquired_capability_flutter_e2e.py` が用意した
// 生成物——install された Dart と生成 Document——を要る。
//
// `test/` に置くと、素の checkout で `flutter test` を回した人のところで
// 落ちる。かといって「生成物が無ければ skip」にすると、**skip が PASS と
// して数えられる**（それは何も証明しない）。
//
// そこで別ディレクトリに置き、生成物を用意した後で
// `flutter test test_acquired` として明示的に走らせる。
// 生成物が無ければ **skip ではなく失敗**する。
//
// ## 本番経路を1本で通す
//
// テストは自分では何も登録しない。登録は本番の
// `ensureAcquiredCapabilitiesRegistered()` が、生成された登録表を
// 読んで行う。テスト専用の配線で迂回すると、証明したことにならない。
//
//   生成 Document → ForgeDocument.fromJson（Parser）
//                 → ForgeAcquiredWidgetNode（document model）
//                 → buildDefaultForgeRegistry（Registry）
//                 → ForgeDocumentView（本番 renderer）→ 実 Widget

import 'dart:convert';
import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:forge_app/json_ui/renderer/forge_renderer.dart';
import 'package:forge_app/json_ui/schema/acquired_widget_types.dart';
import 'package:forge_app/json_ui/schema/forge_document.dart';
import 'package:forge_app/json_ui/widget_registry/widget_registry.dart';

/// 獲得した能力が持ち込む widget 型。出荷済みの型では**ない**。
const String acquiredWidgetType = 'calendar_view';

Map<String, dynamic> loadGeneratedDocument() {
  final file = File('test_acquired/generated_document.json');
  if (!file.existsSync()) {
    // skip にしない。用意されていないなら、それは失敗である。
    fail(
      '生成 Document がありません: ${file.path}\n'
      'まず `python3 scripts/acquired_capability_flutter_e2e.py` を実行すること。',
    );
  }
  return jsonDecode(file.readAsStringSync()) as Map<String, dynamic>;
}

List<ForgeWidgetNode> flatten(ForgeWidgetNode node) {
  final found = <ForgeWidgetNode>[node];
  final children = switch (node) {
    ForgeColumnWidgetNode(:final children) => children,
    ForgeRowWidgetNode(:final children) => children,
    ForgeCardWidgetNode(:final children) => children,
    ForgeFormWidgetNode(:final children) => children,
    _ => const <ForgeWidgetNode>[],
  };
  for (final child in children) {
    found.addAll(flatten(child));
  }
  return found;
}

void main() {
  test('1. 生成された Dart が Forge のビルド対象へ入っている', () {
    final installed =
        Directory('lib/json_ui/acquired/view_calendar');
    expect(installed.existsSync(), isTrue,
        reason: '獲得能力が lib/ へ install されていない');
    expect(File('${installed.path}/forge_binding.dart').existsSync(), isTrue);
    expect(File('${installed.path}/capability_impl.dart').existsSync(), isTrue);

    final registrations =
        File('lib/json_ui/acquired/acquired_registrations.g.dart')
            .readAsStringSync();
    expect(registrations, contains('view_calendar/forge_binding.dart'),
        reason: '生成された登録表が獲得能力を参照していない');
  });

  test('2. Parser が獲得 widget 型を認識する', () {
    final document = ForgeDocument.fromJson(loadGeneratedDocument());
    final nodes =
        document.screens.expand((screen) => flatten(screen.body)).toList();
    final acquired = nodes.whereType<ForgeAcquiredWidgetNode>().toList();

    expect(acquired, hasLength(1),
        reason: '生成 Document の獲得 widget が Parser を通っていない');
    expect(acquired.single.rawType, acquiredWidgetType);
    expect(nodes.whereType<ForgeUnknownWidgetNode>(), isEmpty,
        reason: '未知として落ちているものがある');
  });

  test('3. forgeAcquiredWidgetTypes へ本番経路で登録されている', () {
    // 直前の parse を通じて本番の ensure...() が走っている。
    // テストが自分で register していないことが要点である。
    expect(forgeAcquiredWidgetTypes.registeredTypes,
        contains(acquiredWidgetType));
    final spec = forgeAcquiredWidgetTypes.specFor(acquiredWidgetType)!;
    expect(spec.requiredProperties, contains('state_ref'));
    expect(spec.requiredProperties, contains('date_field'));
  });

  test('4. Widget Registry がその型を実 Widget へ解決する', () {
    expect(buildDefaultForgeRegistry().resolve(acquiredWidgetType), isNotNull,
        reason: 'Registry が獲得 widget を解決できない');
  });

  testWidgets('5. 生成 Document からその Widget が実際に描かれる', (tester) async {
    await tester.pumpWidget(MaterialApp(
      home: ForgeDocumentView(rawJson: loadGeneratedDocument()),
    ));
    await tester.pump();

    expect(find.byKey(const ValueKey('acquired_calendar_view')), findsOneWidget,
        reason: '獲得 widget が描かれていない');
    expect(find.byType(ForgeFallbackWidget), findsNothing,
        reason: 'Fallback へ倒れている');
    // 宣言した属性が実際に描画へ届いていること。
    expect(find.text('日付を記録するとカレンダーに表示されます'), findsOneWidget);
  });

  testWidgets('6. 記録を入れると獲得 widget の中身が変わる', (tester) async {
    await tester.pumpWidget(MaterialApp(
      home: ForgeDocumentView(
        rawJson: loadGeneratedDocument(),
        initialRuntimeState: const <String, Map<String, dynamic>>{
          'generated_screen': <String, dynamic>{
            'records': <String, dynamic>{
              'type': 'record_list',
              'schema_ref': 'visit_log',
              'value': <dynamic>[
                <String, dynamic>{
                  'id': 'r1',
                  'fields': <String, dynamic>{'date': '2026-08-03'},
                },
                <String, dynamic>{
                  'id': 'r2',
                  'fields': <String, dynamic>{'date': '2026-07-31'},
                },
              ],
            },
          },
        },
      ),
    ));
    await tester.pump();

    expect(find.text('2026-07: 1件'), findsOneWidget);
    expect(find.text('2026-08: 1件'), findsOneWidget);
    expect(find.text('日付を記録するとカレンダーに表示されます'), findsNothing);
  });
}
