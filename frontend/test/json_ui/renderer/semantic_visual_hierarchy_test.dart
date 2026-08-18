// Semantic Role が**実際の描画へ効いている**ことの検査
// (FORGE-R1-CLOSURE-015 §6・§7・§8、2026-08-17新設)。
//
// ---
//
// **このファイルが証明すること**
//
// 「style_role を付けた」と「本当に大きく表示された」は別である。
// v1.11 までの実装では、次の2つが実際に起きていた。
//
// 1. `metric_view` の数値 Text が明示的な `style:` を持っており、
//    Renderer が被せる `DefaultTextStyle` は**効いていなかった**
//    ——`metric.primary` を付けても描画は1ピクセルも変わらない。
// 2. `button.primary` と `button.secondary` が同じ `ElevatedButton`
//    で描かれており、**画面上は区別できなかった**。
//
// どちらも「Evidence には残るが見た目は変わらない」状態で、
// 「AIは意味を決める。Forgeは品質を保証する」の後半が成立していない。
//
// ここでは実際に描画して `TextStyle` / Widget 型 / padding を読む。

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:forge_app/core/theme/forge_theme.dart';
import 'package:forge_app/json_ui/renderer/design_language.dart';
import 'package:forge_app/json_ui/renderer/forge_renderer.dart';

Widget _wrap(Map<String, dynamic> doc, {ThemeData? theme}) => MaterialApp(
      theme: theme ?? ForgeTheme.theme,
      home: ForgeDocumentView(rawJson: doc),
    );

Map<String, dynamic> _doc(List<Map<String, dynamic>> children) => {
      'version': '1.12',
      'initial_screen_id': 's1',
      'record_schemas': {
        'expense': {
          'fields': [
            {'name': 'kind', 'type': 'string', 'label': '収支', 'required': true},
            {'name': 'amount', 'type': 'number', 'label': '金額', 'required': true},
          ],
        },
      },
      'screens': [
        {
          'id': 's1',
          'title': '家計簿',
          'state': {
            'records': {
              'type': 'record_list',
              'schema_ref': 'expense',
              'value': [
                {'id': 'r1', 'fields': {'kind': '収入', 'amount': 3000}},
                {'id': 'r2', 'fields': {'kind': '支出', 'amount': 1200}},
              ],
            },
          },
          'body': {'type': 'column', 'id': 'root', 'children': children},
        },
      ],
    };

Map<String, dynamic> _metric(String id, String role, {String aggregate = 'sum'}) => {
      'type': 'metric_view',
      'id': id,
      'state_ref': 'records',
      'value_field': 'amount',
      'aggregate': aggregate,
      'style_role': role,
    };

TextStyle _styleOf(WidgetTester tester, String text) =>
    tester.widget<Text>(find.text(text)).style!;

void main() {
  group('metric.primary が実際に大きくなる (§8.1)', () {
    testWidgets('metric.primary は metric.secondary より大きい', (tester) async {
      await tester.pumpWidget(_wrap(_doc([
        _metric('hero', 'metric.primary'),
        _metric('sub', 'metric.secondary', aggregate: 'max'),
      ])));
      await tester.pumpAndSettle();

      // sum = 4200 / max = 3000。role 以外の条件は同じ。
      final primary = _styleOf(tester, '4,200');
      final secondary = _styleOf(tester, '3,000');

      expect(primary.fontSize, isNotNull);
      expect(secondary.fontSize, isNotNull);
      expect(
        primary.fontSize!, greaterThan(secondary.fontSize!),
        reason: 'metric.primary が metric.secondary より大きくない＝階層が出ていない',
      );
      expect(primary.fontWeight, FontWeight.w700);
    });

    testWidgets('数字は桁がずれない字形で描かれる', (tester) async {
      // 残高が 1,000 → 999 と変わるたびに数字の位置が揺れると安っぽい。
      await tester.pumpWidget(_wrap(_doc([_metric('hero', 'metric.primary')])));
      await tester.pumpAndSettle();
      final style = _styleOf(tester, '4,200');
      expect(
        style.fontFeatures?.any((f) => f.feature == 'tnum'), isTrue,
        reason: 'tabular figures が効いていない',
      );
    });

    testWidgets('role が無ければ従来の見た目のまま', (tester) async {
      // role の無い既存の生成物の見た目を変えない、という約束の側。
      await tester.pumpWidget(_wrap(_doc([
        {
          'type': 'metric_view', 'id': 'plain', 'state_ref': 'records',
          'value_field': 'amount', 'aggregate': 'sum',
        },
      ])));
      await tester.pumpAndSettle();
      expect(find.text('4,200'), findsOneWidget);
      expect(tester.takeException(), isNull);
    });
  });

  group('button の強弱が視覚的に違う (§6.1)', () {
    Map<String, dynamic> button(String id, String? role) => {
          'type': 'button', 'id': id, 'label': id,
          'action': {'type': 'set_value', 'state_ref': 'note', 'value': 'x'},
          if (role != null) 'style_role': role,
        };

    Map<String, dynamic> buttonDoc(List<Map<String, dynamic>> children) {
      final doc = _doc(children);
      ((doc['screens'] as List).first as Map)['state']['note'] =
          {'type': 'string', 'value': ''};
      return doc;
    }

    testWidgets('primary は塗りつぶし / secondary は輪郭', (tester) async {
      await tester.pumpWidget(_wrap(buttonDoc([
        button('save', 'button.primary'),
        button('cancel', 'button.secondary'),
      ])));
      await tester.pumpAndSettle();

      expect(find.widgetWithText(FilledButton, 'save'), findsOneWidget,
          reason: 'button.primary が強調されていない');
      expect(find.widgetWithText(OutlinedButton, 'cancel'), findsOneWidget,
          reason: 'button.secondary が弱められていない');
    });

    testWidgets('role が無ければ従来どおり ElevatedButton', (tester) async {
      await tester.pumpWidget(_wrap(buttonDoc([button('plain', null)])));
      await tester.pumpAndSettle();
      expect(find.widgetWithText(ElevatedButton, 'plain'), findsOneWidget);
    });

    test('emphasis の対応表', () {
      expect(buttonEmphasisFor('button.primary'), ForgeButtonEmphasis.primary);
      expect(buttonEmphasisFor('button.secondary'), ForgeButtonEmphasis.secondary);
      expect(buttonEmphasisFor('navigation.primary'), ForgeButtonEmphasis.primary);
      expect(buttonEmphasisFor('text.body'), isNull);
      expect(buttonEmphasisFor(null), isNull);
    });
  });

  group('density の3段が実際に違う (§8.2)', () {
    testWidgets('compact < normal < relaxed', (tester) async {
      final paddings = <String, double>{};
      for (final role in ['density.compact', 'density.normal', 'density.relaxed']) {
        await tester.pumpWidget(_wrap(_doc([
          {'type': 'text', 'id': 'label', 'value': '本文', 'style_role': role},
        ])));
        await tester.pumpAndSettle();
        // **その Text の祖先**に限定して探す。画面全体から拾うと
        // MaterialApp 内部の Container を拾いうる。
        final container = tester.widget<Container>(
          find
              .ancestor(of: find.text('本文'), matching: find.byType(Container))
              .first,
        );
        paddings[role] = (container.padding! as EdgeInsets).vertical;
      }
      expect(paddings['density.compact']!, lessThan(paddings['density.normal']!));
      expect(paddings['density.normal']!, lessThan(paddings['density.relaxed']!));
    });
  });

  group('surface の違いが実際に出る (§8.3)', () {
    testWidgets('elevated は card より持ち上がり、余白も広い', (tester) async {
      await tester.pumpWidget(_wrap(_doc([
        {'type': 'text', 'id': 't', 'value': 'x', 'style_role': 'surface.card'},
      ])));
      await tester.pumpAndSettle();
      final context = tester.element(find.text('x'));
      final card = resolveForgeRole(context, 'surface.card')!;
      final elevated = resolveForgeRole(context, 'surface.elevated')!;

      expect(elevated.elevation ?? 0, greaterThan(card.elevation ?? 0),
          reason: 'elevated が card より持ち上がっていない');
      // `ForgeRoleStyle.padding` は既に `EdgeInsets?` なのでキャスト不要。
      expect(elevated.padding!.vertical, greaterThan(card.padding!.vertical));
    });

    testWidgets('surface.card は実際に面として描かれる', (tester) async {
      await tester.pumpWidget(_wrap(_doc([
        {'type': 'text', 'id': 't', 'value': 'x', 'style_role': 'surface.card'},
      ])));
      await tester.pumpAndSettle();
      final container = tester.widget<Container>(
        find.ancestor(of: find.text('x'), matching: find.byType(Container)).first,
      );
      final decoration = container.decoration! as BoxDecoration;
      expect(decoration.color, isNotNull, reason: 'surface.card が面として描かれていない');
      expect(decoration.borderRadius, isNotNull);
    });
  });

  group('意味の色が Light/Dark 両方で成立する (§7)', () {
    ThemeData themed(Brightness brightness) => ThemeData(
          useMaterial3: true,
          brightness: brightness,
          colorScheme: ColorScheme.fromSeed(
            seedColor: const Color(0xFF3D5AFE), brightness: brightness,
          ),
          extensions: [
            brightness == Brightness.dark
                ? ForgeSemanticColors.dark
                : ForgeSemanticColors.light,
          ],
        );

    testWidgets('収入の色は Light/Dark で別になる', (tester) async {
      final seen = <Brightness, Color>{};
      for (final brightness in Brightness.values) {
        await tester.pumpWidget(_wrap(
          _doc([_metric('income', 'finance.income')]),
          theme: themed(brightness),
        ));
        await tester.pumpAndSettle();
        seen[brightness] = _styleOf(tester, '4,200').color!;
      }
      expect(seen[Brightness.light], isNot(seen[Brightness.dark]),
          reason: 'Darkで同じ色を使うと背景に沈む');
    });

    testWidgets('支出はエラーの色ではない', (tester) async {
      // **支出は失敗ではない。** 同じ赤にすると、家計簿を開くたびに
      // 何か失敗したように見える。
      await tester.pumpWidget(_wrap(
        _doc([_metric('expense', 'finance.expense')]),
        theme: themed(Brightness.light),
      ));
      await tester.pumpAndSettle();
      final context = tester.element(find.text('4,200'));
      final expense = resolveForgeRole(context, 'finance.expense')!.textStyle!.color;
      final danger = resolveForgeRole(context, 'state.danger')!.textStyle!.color;
      expect(expense, isNot(danger));
    });

    testWidgets('ThemeExtension が無くても落ちない', (tester) async {
      // Runtimeは壊れた文書でも落ちない、という既存方針に合わせる。
      await tester.pumpWidget(_wrap(
        _doc([_metric('income', 'finance.income')]),
        theme: ThemeData(useMaterial3: true),
      ));
      await tester.pumpAndSettle();
      expect(tester.takeException(), isNull);
      expect(find.text('4,200'), findsOneWidget);
    });

    test('Darkの意味色はLightより明るい', () {
      for (final pair in [
        [ForgeSemanticColors.light.success, ForgeSemanticColors.dark.success],
        [ForgeSemanticColors.light.income, ForgeSemanticColors.dark.income],
        [ForgeSemanticColors.light.expense, ForgeSemanticColors.dark.expense],
      ]) {
        expect(pair[1].computeLuminance(), greaterThan(pair[0].computeLuminance()));
      }
    });
  });

  group('お金の出入り (§2.3)', () {
    testWidgets('残高は支出を引いた値になる', (tester) async {
      await tester.pumpWidget(_wrap(_doc([
        {
          'type': 'metric_view', 'id': 'balance', 'state_ref': 'records',
          'value_field': 'amount', 'aggregate': 'sum',
          'sign_field': 'kind', 'negative_when': '支出',
          'style_role': 'metric.primary', 'label': '残高',
        },
      ])));
      await tester.pumpAndSettle();
      // 収入3000 − 支出1200 = 1800。単純合計の4200ではない。
      expect(find.text('1,800'), findsOneWidget);
      expect(find.text('4,200'), findsNothing);
    });

    testWidgets('収入だけ・支出だけを数えられる', (tester) async {
      await tester.pumpWidget(_wrap(_doc([
        {
          'type': 'metric_view', 'id': 'income', 'state_ref': 'records',
          'value_field': 'amount', 'aggregate': 'sum',
          'filter_field': 'kind', 'filter_value': '収入',
          'style_role': 'finance.income',
        },
        {
          'type': 'metric_view', 'id': 'expense', 'state_ref': 'records',
          'value_field': 'amount', 'aggregate': 'sum',
          'filter_field': 'kind', 'filter_value': '支出',
          'style_role': 'finance.expense',
        },
      ])));
      await tester.pumpAndSettle();
      expect(find.text('3,000'), findsOneWidget);
      expect(find.text('1,200'), findsOneWidget);
    });
  });
}
