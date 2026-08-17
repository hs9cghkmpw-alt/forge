// Design Language V1 — Semantic Role を実際の見た目へ変換する
// (FORGE-R1-ENTRY-AND-DESIGN-LANGUAGE-014、2026-08-17)。
//
// ---
//
// ## この層の役割
//
// Product Direction §3 の分担で、**Forge側**を担当する。
//
//     AIは意味を決める      → style_role: "metric.primary"
//     Forgeは品質を保証する  → ここ。何px・何色・どの太さかを決める
//
// AIが `font_size: 36` を直接出す方向へ進めない理由がここにある。
// 値をAIに出させると、
//
//   * 画面ごとに 34 / 36 / 38 と揺れる
//   * 背景色とのコントラストが保証できない
//   * 「重要な数値」という意図が、後から読めない（36pxという事実しか残らない）
//
// role で受け取れば、3つとも Forge 側で担保できる。
//
// ## Theme から引く（固定色を書かない）
//
// 色は `Theme.of(context).colorScheme` から引く。`design_tokens` は
// 既に `ForgeDocumentView` が Theme として適用済みなので
// (`forge_renderer.dart` の `_applyDesignTokens()`)、ここで
// `design_tokens` を個別に読む必要はない。
//
// 固定の `Color(0xFF23D18B)` を書くと、アプリごとの配色を無視して
// しまう。**役割は共通、値はテーマ由来**が原則である。
//
// ## 未知の role は何もしない
//
// Validator が語彙外を弾いているので、ここへ未知の値は届かない。
// それでも `null` を返して素通しにするのは、Validator を通っていない
// 文書（テスト・将来の緩い経路）で**描画そのものが落ちない**ように
// するためである。見た目が付かないことは、画面が出ないことより軽い。

import 'package:flutter/material.dart';

/// 1つの role が決める見た目。
///
/// すべて null 許容なのは、role ごとに「決めること」が違うためである。
/// タイポグラフィの role は色と字形だけを決め、面の role は背景と角丸
/// だけを決める。**関係ない軸まで既定値で埋めない**——埋めると、
/// 別の role と重ねたときにどちらが勝つのか決められなくなる。
@immutable
class ForgeRoleStyle {
  final TextStyle? textStyle;
  final Color? surfaceColor;
  final BorderRadius? borderRadius;
  final EdgeInsets? padding;
  final double? elevation;

  const ForgeRoleStyle({
    this.textStyle,
    this.surfaceColor,
    this.borderRadius,
    this.padding,
    this.elevation,
  });

  bool get isEmpty =>
      textStyle == null &&
      surfaceColor == null &&
      borderRadius == null &&
      padding == null &&
      elevation == null;
}

/// Semantic Role → 見た目。**ここが唯一の変換地点。**
///
/// backend 側の語彙 (`app/ai/runtime/design_language.py`) と綴りが
/// 一致していなければならない。ずれた場合、backend の Validator が
/// `unknown_style_role` で落とすので、**黙って見た目だけ消えることは
/// ない**。
ForgeRoleStyle? resolveForgeRole(BuildContext context, String? role) {
  if (role == null || role.isEmpty) return null;

  final theme = Theme.of(context);
  final colors = theme.colorScheme;
  final text = theme.textTheme;

  switch (role) {
    // --- Typography -------------------------------------------------
    case 'text.display':
      return ForgeRoleStyle(
        textStyle: text.displaySmall?.copyWith(
          fontWeight: FontWeight.w700,
          color: colors.onSurface,
        ),
      );
    case 'text.headline':
      return ForgeRoleStyle(
        textStyle: text.titleLarge?.copyWith(
          fontWeight: FontWeight.w700,
          color: colors.onSurface,
        ),
      );
    case 'text.title':
      return ForgeRoleStyle(
        textStyle: text.titleMedium?.copyWith(
          fontWeight: FontWeight.w600,
          color: colors.onSurface,
        ),
      );
    case 'text.body':
      return ForgeRoleStyle(textStyle: text.bodyMedium?.copyWith(color: colors.onSurface));
    case 'text.label':
      return ForgeRoleStyle(
        textStyle: text.labelLarge?.copyWith(color: colors.onSurfaceVariant),
      );
    case 'text.secondary':
      // **極端に小さくしない。** 補助情報は「読まなくてよい情報」では
      // ないので、弱めるのは色であってサイズではない。
      return ForgeRoleStyle(
        textStyle: text.bodySmall?.copyWith(color: colors.onSurfaceVariant),
      );

    // metric.* は「数値であること」を字形で示す。tabularFigures にする
    // のは、桁が変わっても数字の位置がずれないようにするためである
    // ——残高が 1,000 → 999 と変わるたびに揺れると安っぽく見える。
    case 'metric.primary':
      return ForgeRoleStyle(
        textStyle: text.displaySmall?.copyWith(
          fontWeight: FontWeight.w700,
          color: colors.onSurface,
          fontFeatures: const [FontFeature.tabularFigures()],
        ),
      );
    case 'metric.secondary':
      return ForgeRoleStyle(
        textStyle: text.titleMedium?.copyWith(
          fontWeight: FontWeight.w600,
          color: colors.onSurfaceVariant,
          fontFeatures: const [FontFeature.tabularFigures()],
        ),
      );

    // --- Color semantics ---------------------------------------------
    case 'color.primary':
      return ForgeRoleStyle(textStyle: TextStyle(color: colors.primary));
    case 'color.secondary':
      return ForgeRoleStyle(textStyle: TextStyle(color: colors.secondary));
    case 'text.primary':
      return ForgeRoleStyle(textStyle: TextStyle(color: colors.onSurface));
    case 'state.success':
      return const ForgeRoleStyle(textStyle: TextStyle(color: Color(0xFF2E7D32)));
    case 'state.warning':
      return const ForgeRoleStyle(textStyle: TextStyle(color: Color(0xFFEF6C00)));
    case 'state.danger':
      return ForgeRoleStyle(textStyle: TextStyle(color: colors.error));
    // finance.* を state.success/danger と**別の色**にしているのは、
    // 意味が違うからである。「支出」は失敗ではない。同じ色にすると、
    // 家計簿を開くたびにエラーのように見える。
    case 'finance.income':
      return const ForgeRoleStyle(textStyle: TextStyle(color: Color(0xFF00796B)));
    case 'finance.expense':
      return const ForgeRoleStyle(textStyle: TextStyle(color: Color(0xFFC2185B)));

    // --- Surface -------------------------------------------------------
    case 'surface.background':
      return ForgeRoleStyle(surfaceColor: colors.surface);
    case 'surface.card':
      return ForgeRoleStyle(
        surfaceColor: colors.surfaceContainerHighest,
        borderRadius: BorderRadius.circular(12),
        padding: const EdgeInsets.all(12),
      );
    case 'surface.elevated':
      return ForgeRoleStyle(
        surfaceColor: colors.surfaceContainerHighest,
        borderRadius: BorderRadius.circular(16),
        padding: const EdgeInsets.all(16),
        elevation: 2,
      );
    case 'surface.selected':
      return ForgeRoleStyle(
        surfaceColor: colors.primaryContainer,
        borderRadius: BorderRadius.circular(12),
      );

    // --- Shape ---------------------------------------------------------
    case 'shape.small':
      return ForgeRoleStyle(borderRadius: BorderRadius.circular(6));
    case 'shape.medium':
      return ForgeRoleStyle(borderRadius: BorderRadius.circular(12));
    case 'shape.large':
      return ForgeRoleStyle(borderRadius: BorderRadius.circular(20));
    case 'shape.pill':
      return ForgeRoleStyle(borderRadius: BorderRadius.circular(999));

    // --- Density -------------------------------------------------------
    case 'density.compact':
      return const ForgeRoleStyle(padding: EdgeInsets.symmetric(vertical: 4));
    case 'density.normal':
      return const ForgeRoleStyle(padding: EdgeInsets.symmetric(vertical: 8));
    case 'density.relaxed':
      return const ForgeRoleStyle(padding: EdgeInsets.symmetric(vertical: 16));

    // --- Component intent ------------------------------------------------
    case 'card.metric':
      return ForgeRoleStyle(
        surfaceColor: colors.surfaceContainerHighest,
        borderRadius: BorderRadius.circular(16),
        padding: const EdgeInsets.all(20),
        elevation: 1,
      );
    case 'card.summary':
    case 'card.list':
      return ForgeRoleStyle(
        surfaceColor: colors.surfaceContainerHighest,
        borderRadius: BorderRadius.circular(12),
        padding: const EdgeInsets.all(12),
      );
    case 'button.primary':
    case 'button.secondary':
    case 'navigation.primary':
      // 操作系の見た目は、既に各Widgetのbuilderが決めている。ここで
      // 面を被せると二重に枠が付く。**roleは記録として意味を持つ**が、
      // 描画は変えない——「Evidenceに残す」と「見た目を変える」は
      // 別の目的であり、後者が無いことは欠陥ではない。
      return null;

    default:
      // Validatorが語彙外を弾いている。ここへ来るのは Validator を
      // 通っていない文書だけなので、**描画を落とさず素通しする**。
      return null;
  }
}

/// role の見た目を、その Widget へ被せる。
///
/// `_build()` から**1箇所だけ**呼ばれる。20種の builder それぞれへ
/// 配ると、Widget を1つ足すたびに付け忘れる。
Widget applyForgeRole(BuildContext context, String? role, Widget child) {
  final style = resolveForgeRole(context, role);
  if (style == null || style.isEmpty) return child;

  var result = child;

  if (style.textStyle != null) {
    // `merge` にするのは、builder 側が既に持っている字形を消さない
    // ためである。role が決めるのは差分だけ。
    result = DefaultTextStyle.merge(style: style.textStyle, child: result);
  }

  if (style.surfaceColor != null || style.borderRadius != null || style.padding != null) {
    result = Container(
      padding: style.padding,
      decoration: BoxDecoration(
        color: style.surfaceColor,
        borderRadius: style.borderRadius,
        boxShadow: (style.elevation ?? 0) > 0
            ? [
                BoxShadow(
                  color: Colors.black.withValues(alpha: 0.08),
                  blurRadius: style.elevation! * 4,
                  offset: Offset(0, style.elevation!),
                ),
              ]
            : null,
      ),
      child: result,
    );
  }

  return result;
}
