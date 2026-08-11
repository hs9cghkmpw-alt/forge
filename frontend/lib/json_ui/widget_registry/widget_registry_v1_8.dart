/// v1.8で追加された1種のWidget(`slider`)の構築関数
/// (Widget Vocabulary Expansion第3弾、2026-08-11)。
///
/// CEO「壊れてる?って機能でもどんどん追加してくれ。あとでなおす。」
/// という明示的な指示を受けて着手した(`TECH_DEBT.md` TD38参照)。
/// v1.1・v1.3・v1.5・v1.6・v1.7と同じ理由(`widget_registry_v1_1.dart`
/// 冒頭コメント参照)で、別ファイルへ分離している。
///
/// Flutter標準の`Slider`をそのまま使う(新規パッケージ依存なし)。
/// stateは既存の"number"型(v1.2で導入済み、これまで消費するWidgetが
/// 無かった)をそのまま使い、新しいstate型は追加しない。
library;

import 'package:flutter/material.dart';

import '../renderer/forge_runtime_state.dart';
import '../schema/forge_document.dart';
import 'widget_registry_core.dart';

Widget buildSlider(
  BuildContext context,
  ForgeWidgetNode node,
  ForgeRuntimeState state,
  Widget Function(ForgeWidgetNode) build,
) {
  final n = node as ForgeSliderWidgetNode;
  return AnimatedBuilder(
    animation: state,
    builder: (context, _) {
      final currentValue = state.getNumber(n.stateRef).clamp(n.min, n.max);
      final error = state.getValidationError(n.stateRef);
      return Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Text(n.label, style: Theme.of(context).textTheme.bodyMedium),
              Text(
                _formatSliderValue(currentValue),
                style: Theme.of(context).textTheme.bodyMedium?.copyWith(fontWeight: FontWeight.w700),
              ),
            ],
          ),
          Slider(
            value: currentValue,
            min: n.min,
            max: n.max,
            onChanged: (value) => state.setNumber(n.stateRef, value),
          ),
          if (error != null)
            Padding(
              padding: const EdgeInsets.only(left: 12, bottom: 4),
              child: Text(
                error,
                style: TextStyle(color: Theme.of(context).colorScheme.error, fontSize: 12),
              ),
            ),
        ],
      );
    },
  );
}

/// 整数値は`3`、それ以外は`3.5`のように小数第1位までで表示する
/// (`ForgeRecordValidator`が`.toString()`経由でRecordへ保存する際の
/// 表記([TECH_DEBT.md] TD38参照)とは独立した、ドラッグ中の表示専用の整形)。
String _formatSliderValue(double value) {
  if (value == value.roundToDouble()) return value.round().toString();
  return value.toStringAsFixed(1);
}

/// `buildDefaultForgeRegistry()` から呼ばれる、v1.8 Widget群の一括登録。
void registerV1_8Widgets(ForgeWidgetRegistry registry) {
  registry.register('slider', buildSlider);
}
