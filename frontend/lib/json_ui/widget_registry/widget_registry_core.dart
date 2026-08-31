/// Widget Registryの中核機構(FORGE-MILESTONE-002 PHASE2で分離)。
///
/// 以前は`widget_registry.dart`1ファイルに「Registry機構」と「v1.0の6 Widget
/// 実装」が同居していた。v1.1で6 Widgetを追加するにあたり、「Registry機構」
/// (このファイル)と「個々のWidget実装」(widget_registry.dart=v1.0分、
/// widget_registry_v1_1.dart=v1.1分)を分離した。新しいWidgetを追加する際は、
/// このファイルを変更する必要はなく、実装ファイルを1つ追加して
/// [ForgeWidgetRegistry.register] を呼ぶだけでよい。
library;

import 'package:flutter/foundation.dart' show kDebugMode;
import 'package:flutter/material.dart';

import '../renderer/forge_runtime_state.dart';
import '../schema/forge_document.dart';

/// Widgetノード1件をFlutter Widgetへ変換する関数の型。
typedef ForgeWidgetBuilder = Widget Function(
  BuildContext context,
  ForgeWidgetNode node,
  ForgeRuntimeState state,
  Widget Function(ForgeWidgetNode child) build,
);

/// `"type": "button"` のような文字列 → Flutter Widgetビルダー の辞書。
class ForgeWidgetRegistry {
  final Map<String, ForgeWidgetBuilder> _builders = {};

  void register(String typeName, ForgeWidgetBuilder builder) {
    _builders[typeName] = builder;
  }

  ForgeWidgetBuilder? resolve(String typeName) => _builders[typeName];

  /// 登録済みtype一覧(テスト・監査用)。
  Set<String> get registeredTypes => _builders.keys.toSet();
}

String typeNameOf(ForgeWidgetNode node) => switch (node) {
      ForgeTextWidgetNode() => 'text',
      ForgeTextFieldWidgetNode() => 'text_field',
      ForgeButtonWidgetNode() => 'button',
      ForgeColumnWidgetNode() => 'column',
      ForgeRowWidgetNode() => 'row',
      ForgeChecklistWidgetNode() => 'checklist',
      ForgeHeadingWidgetNode() => 'heading',
      ForgeCheckboxWidgetNode() => 'checkbox',
      ForgeCardWidgetNode() => 'card',
      ForgeListWidgetNode() => 'list',
      ForgeRecordListViewWidgetNode() => 'record_list_view',
      ForgeSectionHeaderWidgetNode() => 'section_header',
      ForgeDividerWidgetNode() => 'divider',
      ForgeFormWidgetNode() => 'form',
      ForgeChoiceFieldWidgetNode() => 'choice_field',
      ForgeBarChartWidgetNode() => 'bar_chart',
      ForgeDateFieldWidgetNode() => 'date_field',
      ForgeTabViewWidgetNode() => 'tab_view',
      ForgeSliderWidgetNode() => 'slider',
      ForgeMetricViewWidgetNode() => 'metric_view',
      ForgeSimulationProgressWidgetNode() => 'simulation_progress',
      ForgeAudioMixerWidgetNode() => 'audio_mixer',
      ForgeSimulationLoopWidgetNode() => 'simulation_loop',
      ForgeMapViewWidgetNode() => 'map_view',
      ForgeAcquiredWidgetNode(:final rawType) => rawType,
      ForgeUnknownWidgetNode() => 'unknown',
    };

/// Rendererの入口。Registryで解決できたWidgetはそれを使い、
/// 解決できない場合(未知Widget・型不一致)は必ずFallbackへ倒す。
Widget buildForgeWidget(
  BuildContext context,
  ForgeWidgetNode node,
  ForgeRuntimeState state,
  ForgeWidgetRegistry registry,
  Widget Function(ForgeWidgetNode child) recurse,
) {
  if (node is ForgeUnknownWidgetNode) {
    return ForgeFallbackWidget(reason: '未知のWidget type: ${node.rawType}');
  }
  final builder = registry.resolve(typeNameOf(node));
  if (builder == null) {
    return ForgeFallbackWidget(reason: 'Registry未登録のtype: ${typeNameOf(node)}');
  }
  try {
    return builder(context, node, state, recurse);
  } catch (e) {
    return ForgeFallbackWidget(reason: 'Widget構築中の例外: $e');
  }
}

/// 未知Widget・構築失敗時の安全なFallback。
/// development: 理由を可視化する。production: 静かに空スペースへ倒す(方針12章)。
class ForgeFallbackWidget extends StatelessWidget {
  final String reason;
  const ForgeFallbackWidget({super.key, required this.reason});

  @override
  Widget build(BuildContext context) {
    if (!kDebugMode) {
      return const SizedBox.shrink();
    }
    return Container(
      margin: const EdgeInsets.symmetric(vertical: 4),
      padding: const EdgeInsets.all(8),
      decoration: BoxDecoration(
        border: Border.all(color: Colors.orange),
        borderRadius: BorderRadius.circular(8),
      ),
      child: Row(
        children: [
          const Icon(Icons.warning_amber_rounded, color: Colors.orange, size: 16),
          const SizedBox(width: 6),
          Expanded(child: Text(reason, style: const TextStyle(fontSize: 12, color: Colors.orange))),
        ],
      ),
    );
  }
}
