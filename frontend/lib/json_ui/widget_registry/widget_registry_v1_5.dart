/// v1.5で追加された1種のWidget(`section_header`)の構築関数
/// (FORGE v1.0 Product Quality Sprint1、Patch2でTheme経路へ単純化)。
///
/// v1.1・v1.3と同じ理由(`widget_registry_v1_1.dart`冒頭コメント参照)で
/// 別ファイルへ分離している。`section_header`は状態・アクションを
/// 持たない最も単純な部類のWidget(`divider`と同様)であり、見出しの
/// 強調バーには`Theme.of(context).colorScheme.primary`を使う
/// (`_RecordCard`の選択色と同じ経路、`forge_renderer.dart`の
/// `ForgeDocumentView`がdesign_tokensをTheme全体へ適用済みのため、
/// 常にこれだけで足りる)。
library;

import 'package:flutter/material.dart';

import '../renderer/forge_runtime_state.dart';
import '../schema/forge_document.dart';
import 'widget_registry_core.dart';

Widget buildSectionHeader(
  BuildContext context,
  ForgeWidgetNode node,
  ForgeRuntimeState state,
  Widget Function(ForgeWidgetNode) build,
) {
  final n = node as ForgeSectionHeaderWidgetNode;
  // Sprint1 Patch2で単純化: `ForgeDocumentView`が`design_tokens`を
  // `Theme`として既にサブツリー全体へ適用済みのため(`forge_renderer.
  // dart`の`_applyDesignTokens()`参照)、ここでは`state.designTokens`を
  // 個別に参照する必要が無い。`Theme.of(context).colorScheme.primary`
  // だけを見れば、design_tokens.color_scheme.primary(指定が無ければ
  // ネイティブの既定値)が一貫して手に入る——`_RecordCard`
  // (`widget_registry_v1_3.dart`)の選択色と同じ、単一の経路。
  final accentColor = Theme.of(context).colorScheme.primary;

  return Padding(
    padding: const EdgeInsets.only(top: 20, bottom: 8),
    child: Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      mainAxisSize: MainAxisSize.min,
      children: [
        Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            Container(
              width: 4,
              height: 20,
              decoration: BoxDecoration(
                color: accentColor,
                borderRadius: BorderRadius.circular(2),
              ),
            ),
            const SizedBox(width: 8),
            Text(
              n.title,
              style: Theme.of(context).textTheme.titleMedium?.copyWith(fontWeight: FontWeight.w700),
            ),
          ],
        ),
        if (n.subtitle != null) ...[
          const SizedBox(height: 2),
          Padding(
            padding: const EdgeInsets.only(left: 12),
            child: Text(n.subtitle!, style: Theme.of(context).textTheme.bodySmall),
          ),
        ],
      ],
    ),
  );
}

/// `buildDefaultForgeRegistry()` から呼ばれる、v1.5 Widget群の一括登録。
void registerV1_5Widgets(ForgeWidgetRegistry registry) {
  registry.register('section_header', buildSectionHeader);
}
