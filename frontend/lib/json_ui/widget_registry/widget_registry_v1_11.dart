/// v1.11で追加された1種のWidget(`metric_view` = Hero KPI)の構築関数
/// (FORGE-R1-ENTRY-AND-DESIGN-LANGUAGE-014、TD69、2026-08-17)。
///
/// ---
///
/// ## なぜWidgetを増やしたのか
///
/// v1.10でDesign Language(意味的役割)を入れたとき、**Widgetを1つも
/// 増やさなかった**のは意図した判断だった。しかしそのとき語彙へ入れた
/// `metric.primary`——「画面で最も重要な単一のKPI」——には、
/// **出力先のWidgetが1つも無かった**。
///
/// 既存19種で数値を出せるのは`text`(Stateの文字列を出すだけ、集計
/// できない)と`bar_chart`(複数の値を並べる)だけで、「今月の残高を、
/// 画面で一番大きく1つだけ見せる」が表現できなかった。語彙に
/// **言えるのに作れない言葉**が入っている状態である。
///
/// ## 集計を所有しない
///
/// 合計・平均・件数の計算は`runtime/forge_aggregate.dart`の純粋関数
/// (`aggregateAll`)が行う。このWidgetは**2番目の利用者**にすぎない
/// (最初は`bar_chart`)。TRANSFORMはVIEWとは別の層である、という
/// 設計を名ばかりにしないため。
///
/// ## 見た目の値を持たない
///
/// フォントサイズも色もここには書かない。`style_role: metric.primary`
/// をDocumentが持ち、`renderer/design_language.dart`が何pxで何色かを
/// 保証する(`forge_renderer.dart`が全Widget共通で適用する)。
/// **AIは意味を決める。Forgeは品質を保証する。**
library;

import 'package:flutter/material.dart';

import '../renderer/design_language.dart';
import '../renderer/forge_runtime_state.dart';
import '../runtime/forge_aggregate.dart';
import '../schema/forge_document.dart';
import 'widget_registry_core.dart';

Widget buildMetricView(
  BuildContext context,
  ForgeWidgetNode node,
  ForgeRuntimeState state,
  Widget Function(ForgeWidgetNode) build,
) {
  final n = node as ForgeMetricViewWidgetNode;
  return AnimatedBuilder(
    animation: state,
    builder: (context, _) {
      final records = state.getRecordList(n.stateRef);
      final value = aggregateAll(
        records,
        op: n.effectiveAggregate,
        valueField: n.valueField.isEmpty ? null : n.valueField,
        // v1.12。収入だけ/支出だけを数える、支出を負として足す
        // (`forge_aggregate.dart`参照)。集計そのものはここでは行わない。
        filterField: n.filterField,
        filterValue: n.filterValue,
        signField: n.signField,
        negativeWhen: n.negativeWhen,
      );

      final theme = Theme.of(context);
      // **v1.12(§8)で直した実バグ。**
      //
      // ここは以前 `style: valueStyle` を明示していた。`style_role`は
      // Renderer側が`DefaultTextStyle.merge`で被せる設計なのだが、
      // **Textが明示的なstyleを持つとDefaultTextStyleは効かない**。
      // つまり`metric.primary`を付けても、実際の描画は何も変わって
      // いなかった——「roleは付いている」のに「大きくなっていない」。
      //
      // roleをここで解決して**明示的に混ぜる**。roleが無ければ土台の
      // まま(roleの無い文書の見た目は変わらない)。
      final roleStyle = resolveForgeRole(context, ForgeRoleScope.roleOf(context))?.textStyle;
      final baseStyle = theme.textTheme.headlineMedium?.copyWith(
        fontWeight: FontWeight.w700,
        color: theme.colorScheme.onSurface,
      );
      final valueStyle = roleStyle == null ? baseStyle : baseStyle?.merge(roleStyle);
      final labelStyle = theme.textTheme.labelLarge?.copyWith(
        color: theme.colorScheme.onSurfaceVariant,
      );

      return Padding(
        padding: const EdgeInsets.symmetric(vertical: 8),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          mainAxisSize: MainAxisSize.min,
          children: [
            if (n.label != null && n.label!.isNotEmpty) ...[
              Text(n.label!, style: labelStyle),
              const SizedBox(height: 4),
            ],
            if (value == null)
              // **「0」と書かない。** 記録が無いことと、合計が0である
              // ことは違う(`aggregateAll`のコメント参照)。0と出すと
              // 「今月は0円使った」という、事実でない読み取りを招く。
              Text(
                n.emptyText?.isNotEmpty == true ? n.emptyText! : '—',
                style: labelStyle,
              )
            else
              Row(
                crossAxisAlignment: CrossAxisAlignment.baseline,
                textBaseline: TextBaseline.alphabetic,
                mainAxisSize: MainAxisSize.min,
                children: [
                  Text(formatMetricValue(value), style: valueStyle),
                  if (n.unit != null && n.unit!.isNotEmpty) ...[
                    const SizedBox(width: 4),
                    Text(n.unit!, style: labelStyle),
                  ],
                ],
              ),
          ],
        ),
      );
    },
  );
}

/// 整数は小数点なし、小数は第1位まで。桁区切りを入れるのは、
/// **主KPIは桁を読み違えると意味が反転する**からである
/// (12000 と 120000 が一目で違って見える必要がある)。
///
/// `intl`パッケージへ依存しない——新規パッケージ依存を増やさない方針
/// (v1.6〜v1.8のWidget追加と同じ)。
String formatMetricValue(double value) {
  final negative = value < 0;
  final absolute = value.abs();
  final String rendered;
  if (absolute == absolute.roundToDouble()) {
    rendered = _withThousandsSeparator(absolute.toInt().toString());
  } else {
    final parts = absolute.toStringAsFixed(1).split('.');
    rendered = '${_withThousandsSeparator(parts[0])}.${parts[1]}';
  }
  return negative ? '-$rendered' : rendered;
}

String _withThousandsSeparator(String digits) {
  final buffer = StringBuffer();
  for (var i = 0; i < digits.length; i++) {
    if (i > 0 && (digits.length - i) % 3 == 0) buffer.write(',');
    buffer.write(digits[i]);
  }
  return buffer.toString();
}

/// `buildDefaultForgeRegistry()` から呼ばれる、v1.11 Widgetの登録。
void registerV1_11Widgets(ForgeWidgetRegistry registry) {
  registry.register('metric_view', buildMetricView);
}
