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
///
/// ---
///
/// ## TD92 の修正(FORGE-PROVIDER-INDEPENDENT-UI、2026-09-02)
///
/// 以前ここは `!kDebugMode` のとき `SizedBox.shrink()` を返していた。
/// つまり **Release では、描けなかった部分が黙って消えていた**。
/// 利用者から見ると「無い」と「作られなかった」の区別が付かず、
/// 画面は成功したように見える。これは Universal Quality Invariant §3
/// 「未対応Capabilityを黙って削り、生成成功として表示する」の禁止事項
/// そのものであり、§9「Completion summary は、実際に作成・保存・検証した
/// 内容だけを示す」にも反する。
///
/// したがって Release でも**必ず何かを描く**。ただし描くのは
/// 「まだこの部分は出せていない」という**利用者の言葉**であって、
/// Widget type 名や例外文字列（内部語彙）ではない
/// （§9「内部の Model、Runtime、Port、SDK、環境変数を通常利用者へ
/// 見せない」）。技術的な `reason` は debug ビルドでだけ画面に出す。
///
/// **`SizedBox.shrink()` へ戻してはならない。**
/// `test/json_ui/widget_registry/fallback_visibility_test.dart` が
/// Release 相当の描画で本文が存在することを検査する。
class ForgeFallbackWidget extends StatelessWidget {
  final String reason;

  /// 技術的な `reason` を画面に出すかどうか。**テストのための注入口**で
  /// ある。`kDebugMode` は compile time 定数なので、`flutter test`
  /// （常に debug）から Release 相当の描画を確認する手段がこれしか無い。
  ///
  /// 本番の呼び出し側は渡さず、`kDebugMode` がそのまま使われる。
  final bool? showTechnicalReason;

  const ForgeFallbackWidget({
    super.key,
    required this.reason,
    this.showTechnicalReason,
  });

  /// Release で利用者へ見せる文言。**内部語彙を含まない。**
  static const String unavailableMessage = 'この部分はまだ表示できません';

  static const String unavailableDetail =
      'Forgeがこの部分をまだ作れていません。会話で「ここをこうしたい」と伝えると作り直せます。';

  @override
  Widget build(BuildContext context) {
    if (!(showTechnicalReason ?? kDebugMode)) {
      // **黙って消さない。** 消えた部分があることを、利用者が見て
      // 分かる形で残す。
      return Semantics(
        label: unavailableMessage,
        hint: unavailableDetail,
        readOnly: true,
        container: true,
        // 子の `Text` と同じ文字なので、除外しないと二重に読まれる。
        excludeSemantics: true,
        child: Container(
          margin: const EdgeInsets.symmetric(vertical: 4),
          padding: const EdgeInsets.all(12),
          decoration: BoxDecoration(
            color: const Color(0xFFF3F1EC),
            border: Border.all(color: const Color(0xFFBFB8A8)),
            borderRadius: BorderRadius.circular(8),
          ),
          child: const Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Icon(Icons.build_outlined, size: 16, color: Color(0xFF5C5647)),
              SizedBox(width: 8),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      unavailableMessage,
                      style: TextStyle(
                        fontSize: 13,
                        fontWeight: FontWeight.w600,
                        color: Color(0xFF3A3529),
                      ),
                    ),
                    SizedBox(height: 2),
                    Text(
                      unavailableDetail,
                      style: TextStyle(fontSize: 12, color: Color(0xFF5C5647)),
                    ),
                  ],
                ),
              ),
            ],
          ),
        ),
      );
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
