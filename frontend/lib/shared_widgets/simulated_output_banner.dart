import 'package:flutter/material.dart';

import '../core/theme/forge_theme.dart';

/// FORGE-HANDOFF-LOCAL-AI-UX-004 §9(2026-08-13)新設。
///
/// 指示書:「**Silent Mock fallbackは禁止**」。
///
/// CEO実機確認で、生成されたToolに`mock_result` `plan` `screens`が項目
/// として並び、会話でも「mock resultがあると楽そう」と表示された。
/// このときユーザーには、**それがMockの出力である手がかりが1つも無かった**
/// ——本物として黙って見せていた。Mockの品質自体も直したが
/// (`backend/app/ai/foundation/providers.py`)、品質を上げること自体は
/// この問題の解決ではない。「模擬であることが分かる」ことが解決である。
///
/// Backendの`simulated`フィールド(`ConverseAskResponse`等)が`true`の
/// ときだけ表示する。`false`のときは`SizedBox.shrink()`で、実Provider
/// 利用時の画面には一切影響しない。
class SimulatedOutputBanner extends StatelessWidget {
  /// この結果が模擬出力かどうか。`false`なら何も描画しない。
  final bool simulated;

  const SimulatedOutputBanner({super.key, required this.simulated});

  @override
  Widget build(BuildContext context) {
    if (!simulated) return const SizedBox.shrink();
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
      color: ForgeTheme.consoleInk.withValues(alpha: 0.08),
      child: Row(
        children: [
          Icon(Icons.science_outlined, size: 18, color: ForgeTheme.consoleInk.withValues(alpha: 0.7)),
          const SizedBox(width: 8),
          Expanded(
            child: Text(
              'これはお試し用の疑似データです。AIには接続していません。',
              style: TextStyle(fontSize: 13, color: ForgeTheme.consoleInk.withValues(alpha: 0.7)),
            ),
          ),
        ],
      ),
    );
  }
}
