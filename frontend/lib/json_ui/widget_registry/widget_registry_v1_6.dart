/// v1.6で追加された2種のWidget(`choice_field`・`bar_chart`)の構築関数
/// (Widget Vocabulary Expansion、2026-08-11)。
///
/// **経緯**: `docs/spec/LANGUAGE_FREEZE.md`は「Widgetを追加しない」運用
/// 方針だったが、実際には一度も正式に凍結宣言されていなかった
/// (2章のFreeze条件が未達成のまま、同ドキュメント1章に明記済み)。
/// CEOへ「現在のWidget語彙(14種)ではテキスト入力とチェックボックス相当の
/// 表現力しか無く、household_budgetの既存の例文『収支をグラフで見たい』
/// 自体が実現不可能な約束になっている」ことを報告し、Widget追加の凍結
/// 解除の承認を得た上で着手した(`TECH_DEBT.md` TD34参照)。
///
/// v1.1・v1.3・v1.5と同じ理由(`widget_registry_v1_1.dart`冒頭コメント
/// 参照)で、別ファイルへ分離している。
///
/// **`bar_chart`の実装方針**: `ForgeSparkleMark`のような`CustomPainter`
/// ではなく、既存の大半のWidget(`record_list_view`等)と同じ、素の
/// Flutter Layout Widget(`Row`/`FractionallySizedBox`)で組み立てる。
/// Flutter SDKがこのサンドボックスに存在せず`flutter analyze`/実機確認が
/// できないため(TECH_DEBT.md既存の既知の制限)、複雑な描画コードより
/// 実績のある標準Widgetの組み合わせの方が、レビュー時に正しさを検証
/// しやすいという判断。
library;

import 'package:flutter/material.dart';

import '../renderer/forge_runtime_state.dart';
import '../runtime/forge_aggregate.dart';
import '../schema/forge_document.dart';
import 'widget_registry_core.dart';

Widget buildChoiceField(
  BuildContext context,
  ForgeWidgetNode node,
  ForgeRuntimeState state,
  Widget Function(ForgeWidgetNode) build,
) {
  final n = node as ForgeChoiceFieldWidgetNode;
  return AnimatedBuilder(
    animation: state,
    builder: (context, _) {
      final currentValue = state.getString(n.stateRef);
      final error = state.getValidationError(n.stateRef);
      // `options`に含まれない値(初期値の空文字列を含む)をDropdownButton
      // FormFieldへそのまま`value`に渡すと、Flutterが
      // 「一致するitemが無い」というAssertion Errorを投げる
      // (Dropdownの既知の制約)。未選択状態は`null`(プレースホルダ表示)
      // として扱う。
      final resolvedValue = n.options.contains(currentValue) ? currentValue : null;
      return DropdownButtonFormField<String>(
        // `initialValue`はFlutter 3.32以降の追加パラメータ名(`value`の
        // 非推奨化に伴う改名)。このプロジェクトが要求するDart SDK下限
        // (pubspec.yaml: '>=3.3.0')はそれより古いため、より広い
        // Flutterバージョンで動く`value`を使う(`flutter analyze`を
        // このサンドボックスで実行できないため、確実に存在する方の
        // パラメータ名を選ぶ安全側の判断)。
        initialValue: resolvedValue,
        decoration: InputDecoration(
          labelText: n.label,
          hintText: n.placeholder,
          errorText: error,
        ),
        items: [
          for (final option in n.options) DropdownMenuItem(value: option, child: Text(option)),
        ],
        // choice_fieldはtext_fieldと異なり、選択と同時に確定する離散値
        // 入力であるため(タイプ中の中間状態が無い)、`notify: true`
        // (既定値)のまま呼ぶ。これによりRuntimeState変更を購読している
        // 自動保存機構(`ForgeScreenView`)が、選択直後に確実に状態を
        // 保存できる(text_fieldが`notify: false`で1文字ごとの保存を
        // 意図的に避けているのとは違い、choice_fieldは1回の選択=1回の
        // 確定操作のため、この違いが問題にならない)。
        onChanged: (value) {
          if (value != null) {
            state.setString(n.stateRef, value);
          }
        },
      );
    },
  );
}

Widget buildBarChart(
  BuildContext context,
  ForgeWidgetNode node,
  ForgeRuntimeState state,
  Widget Function(ForgeWidgetNode) build,
) {
  final n = node as ForgeBarChartWidgetNode;
  return AnimatedBuilder(
    animation: state,
    builder: (context, _) {
      final records = state.getRecordList(n.stateRef);
      final bars = <_BarChartEntry>[];
      if (n.isAggregating) {
        // v1.9(2026-08-13)。グループごとに1本。集計そのものは
        // `runtime/forge_aggregate.dart`が行う——このWidgetは集計を
        // **所有しない**。他のViewからも同じ関数を呼べるようにするため。
        for (final group in aggregateRecords(
          records,
          groupBy: n.groupBy!,
          op: n.effectiveAggregate,
          valueField: n.valueField.isEmpty ? null : n.valueField,
        )) {
          bars.add(_BarChartEntry(label: group.label, value: group.value));
        }
      } else {
        for (final record in records) {
          final rawValue = record.fields[n.valueField];
          if (rawValue is! num) {
            // 非必須Fieldが未入力、またはSchema不整合(Validatorが通常は
            // 弾くはずだが、多重防御として静かにスキップする——他の
            // Widget(例: `_RecordCard._buildSchemaDrivenRows`)と同じ
            // 「無ければ表示しない」方針)。
            continue;
          }
          final rawLabel = record.fields[n.labelField];
          bars.add(_BarChartEntry(label: rawLabel?.toString() ?? '', value: rawValue.toDouble()));
        }
      }

      if (bars.isEmpty) {
        // **何も描かないと、代わりに空の箱が残る**
        // (Quality Gate v2 Round 5 で実際に見えた)。
        //
        // `style_role: card.summary` は `applyForgeRole()` が外側から
        // 被せるので、ここで `SizedBox.shrink()` を返しても
        // **card の padding だけが残った灰色の箱**が描かれる。
        // 利用者から見ると「何かが壊れている」箱である。
        //
        // 被せる側はここが空だと知らない(状態を読むのはこの中だけ)ので、
        // **中から名乗る。** 見出しと、なぜ空なのかを1行書く。
        return Padding(
          padding: const EdgeInsets.symmetric(vertical: 8),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            mainAxisSize: MainAxisSize.min,
            children: [
              if (n.title != null) ...[
                Text(n.title!, style: Theme.of(context).textTheme.titleSmall),
                const SizedBox(height: 4),
              ],
              Text(
                'グラフに出せる記録がまだありません',
                style: Theme.of(context).textTheme.bodySmall?.copyWith(
                      color: Theme.of(context).colorScheme.onSurface.withValues(alpha: 0.6),
                    ),
              ),
            ],
          ),
        );
      }

      final maxValue = bars.map((b) => b.value.abs()).reduce((a, b) => a > b ? a : b);
      final barColor = Theme.of(context).colorScheme.primary;

      return Padding(
        padding: const EdgeInsets.symmetric(vertical: 8),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          mainAxisSize: MainAxisSize.min,
          children: [
            if (n.title != null) ...[
              Text(n.title!, style: Theme.of(context).textTheme.titleSmall),
              const SizedBox(height: 8),
            ],
            for (final bar in bars)
              Padding(
                padding: const EdgeInsets.symmetric(vertical: 3),
                child: Row(
                  children: [
                    SizedBox(
                      width: 96,
                      child: Text(bar.label, overflow: TextOverflow.ellipsis, maxLines: 1),
                    ),
                    Expanded(
                      child: Stack(
                        children: [
                          Container(
                            height: 16,
                            decoration: BoxDecoration(
                              color: barColor.withValues(alpha: 0.12),
                              borderRadius: BorderRadius.circular(4),
                            ),
                          ),
                          FractionallySizedBox(
                            // maxValueが0(全Record値が0)の場合、0除算を
                            // 避けて幅0で描画する(バーが無いだけで
                            // クラッシュはしない)。
                            widthFactor: maxValue > 0 ? (bar.value.abs() / maxValue).clamp(0.0, 1.0) : 0.0,
                            child: Container(
                              height: 16,
                              decoration: BoxDecoration(color: barColor, borderRadius: BorderRadius.circular(4)),
                            ),
                          ),
                        ],
                      ),
                    ),
                    const SizedBox(width: 8),
                    SizedBox(
                      width: 56,
                      child: Text(
                        _formatBarValue(bar.value),
                        textAlign: TextAlign.right,
                        style: Theme.of(context).textTheme.bodySmall,
                      ),
                    ),
                  ],
                ),
              ),
          ],
        ),
      );
    },
  );
}

class _BarChartEntry {
  final String label;
  final double value;
  const _BarChartEntry({required this.label, required this.value});
}

/// 整数値は小数点無しで、小数値のみ小数第1位まで表示する
/// (`forge_field_value_parser.dart`の`_parseNumber`が整数入力を`int`と
/// して保存する方針と対称)。
String _formatBarValue(double value) {
  if (value == value.roundToDouble()) {
    return value.toInt().toString();
  }
  return value.toStringAsFixed(1);
}

/// `buildDefaultForgeRegistry()` から呼ばれる、v1.6 Widget群の一括登録。
void registerV1_6Widgets(ForgeWidgetRegistry registry) {
  registry.register('choice_field', buildChoiceField);
  registry.register('bar_chart', buildBarChart);
}
