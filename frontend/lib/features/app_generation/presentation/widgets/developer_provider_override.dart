// 開発者だけが使う、Provider の明示指定。**既定ビルドには存在しない。**
//
// ---
//
// 通常利用者は AI 経路を選ばない（Forge が選ぶ）。しかし開発者は
// 「いま Local を通ったのか、Cloud へ出たのか、疑似出力なのか」を
// 切り分ける必要がある。両立させる置き方は1つしかない——
// **通常ビルドから消し、開発者ビルドにだけ出す。**
//
// `kForgeDeveloperMode` が `false`（既定）のとき、この Widget は
// `SizedBox.shrink()` を返す。押せない飾りを出さないため、
// **開発者ビルドでないときは何も描かない**（Universal Quality §9）。

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../../core/config/developer_mode.dart';
import '../../../../core/theme/forge_theme.dart';
import '../providers/app_generation_provider.dart';

/// 開発者ビルドでだけ出る、Provider 明示指定のプルダウン。
///
/// `null`（既定・「Forgeが選ぶ」）のときは Backend の Provider Router が
/// Local-first / fallback を通常どおり決める。値を選ぶと Router を迂回
/// する（`POST /api/v1/ai/converse` の `provider` フィールド）。
class DeveloperProviderOverride extends ConsumerWidget {
  const DeveloperProviderOverride({super.key});

  /// 開発者ビルドで選べる Provider 名。Backend の Provider Registry の
  /// 識別子であり、**利用者へ見せる名前ではない**。
  static const List<String> developerProviderIds = <String>[
    'mock',
    'gemini',
    'local',
  ];

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    if (!kForgeDeveloperMode) return const SizedBox.shrink();

    final selected = ref.watch(selectedAiProviderProvider);
    return Semantics(
      label: '開発者用: Provider指定',
      child: Tooltip(
        message: '開発者ビルド専用。通常ビルドでは表示されない。',
        child: DropdownButton<String?>(
          value: selected,
          dropdownColor: ForgeTheme.consoleSurface,
          style: const TextStyle(fontSize: 12, color: ForgeTheme.consoleInk),
          underline: const SizedBox.shrink(),
          items: <DropdownMenuItem<String?>>[
            const DropdownMenuItem<String?>(
              value: null,
              child: Text('auto (Forgeが選ぶ)'),
            ),
            for (final id in developerProviderIds)
              DropdownMenuItem<String?>(value: id, child: Text(id)),
          ],
          onChanged: (value) =>
              ref.read(selectedAiProviderProvider.notifier).state = value,
        ),
      ),
    );
  }
}
