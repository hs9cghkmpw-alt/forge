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
  final semantic = ForgeSemanticColors.of(context);

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
    // 意味の色は**Themeから引く**(v1.12、§7)。それまで固定の
    // `Color(0xFF2E7D32)`等を直接書いていたので、Darkでは背景に
    // 沈んで読めなかった。役割は「意味」であってRGB値ではない。
    case 'state.success':
      return ForgeRoleStyle(textStyle: TextStyle(color: semantic.success));
    case 'state.warning':
      return ForgeRoleStyle(textStyle: TextStyle(color: semantic.warning));
    case 'state.danger':
      return ForgeRoleStyle(textStyle: TextStyle(color: colors.error));
    // finance.* を state.success/danger と**別の色**にしているのは、
    // 意味が違うからである。「支出」は失敗ではない。同じ色にすると、
    // 家計簿を開くたびにエラーのように見える。
    case 'finance.income':
      return ForgeRoleStyle(textStyle: TextStyle(color: semantic.income));
    case 'finance.expense':
      return ForgeRoleStyle(textStyle: TextStyle(color: semantic.expense));

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
      // 操作系は**面を被せない**。ここでContainerを重ねるとボタンの
      // 外側に枠が付いて二重になる。
      //
      // ただし「だから見た目は変わらない」ではない(v1.12で改めた)。
      // 強弱は`ForgeButtonEmphasis`としてbuilderへ渡し、builderが
      // **ボタンの種類そのもの**を変える(filled / outlined)。
      // 意味が見た目に出ないなら、その語彙は記録用の飾りでしかない。
      return null;

    default:
      // Validatorが語彙外を弾いている。ここへ来るのは Validator を
      // 通っていない文書だけなので、**描画を落とさず素通しする**。
      return null;
  }
}

/// 意味の色(FORGE-R1-CLOSURE-015 §7、2026-08-17)。
///
/// ---
///
/// ## なぜThemeExtensionなのか
///
/// それまで`state.success`等は`Color(0xFF2E7D32)`という固定値を
/// `design_language.dart`へ直接書いていた。Lightでは読めるが、Darkでは
/// 背景に沈む。**役割は「意味」であってRGB値ではない**のに、値を
/// 焼き付けていた。
///
/// ThemeExtensionにすると、LightとDarkでそれぞれ適切な色を選べて、
/// しかも**参照側は意味の名前のまま**でよい。
///
/// ## finance と state を混ぜない
///
/// `finance.expense`は`state.danger`ではない。**支出はエラーでは
/// ない**——同じ赤で塗ると、家計簿を開くたびに何か失敗したように
/// 見える。だから別のフィールドとして持つ(Design Language V1が
/// この2つを別の語彙にしているのと同じ判断)。
@immutable
class ForgeSemanticColors extends ThemeExtension<ForgeSemanticColors> {
  /// 良い状態。完了・達成・成功。
  final Color success;

  /// 注意が要る状態。期限が近い・在庫が少ない。
  final Color warning;

  /// **お金が増えた。** 良い状態(success)とは別の意味である。
  final Color income;

  /// **お金が減った。** 失敗(danger)ではない。
  final Color expense;

  const ForgeSemanticColors({
    required this.success,
    required this.warning,
    required this.income,
    required this.expense,
  });

  /// 明るい背景の上で読める組み合わせ。
  static const light = ForgeSemanticColors(
    success: Color(0xFF2E7D32),
    warning: Color(0xFFEF6C00),
    income: Color(0xFF00796B),
    expense: Color(0xFFC2185B),
  );

  /// 暗い背景の上で読める組み合わせ。**明度を上げ、彩度を落とす。**
  /// Lightの色をそのまま置くと沈んで読めない。
  static const dark = ForgeSemanticColors(
    success: Color(0xFF81C784),
    warning: Color(0xFFFFB74D),
    income: Color(0xFF4DB6AC),
    expense: Color(0xFFF06292),
  );

  /// いまのThemeの意味色。**登録されていなくても落ちない**
  /// ——明るさから既定を選ぶ。Runtimeが壊れた文書でも落ちないのと
  /// 同じ方針である。
  static ForgeSemanticColors of(BuildContext context) {
    final theme = Theme.of(context);
    return theme.extension<ForgeSemanticColors>() ??
        (theme.brightness == Brightness.dark ? dark : light);
  }

  @override
  ForgeSemanticColors copyWith({
    Color? success,
    Color? warning,
    Color? income,
    Color? expense,
  }) =>
      ForgeSemanticColors(
        success: success ?? this.success,
        warning: warning ?? this.warning,
        income: income ?? this.income,
        expense: expense ?? this.expense,
      );

  @override
  ForgeSemanticColors lerp(ThemeExtension<ForgeSemanticColors>? other, double t) {
    if (other is! ForgeSemanticColors) return this;
    return ForgeSemanticColors(
      success: Color.lerp(success, other.success, t)!,
      warning: Color.lerp(warning, other.warning, t)!,
      income: Color.lerp(income, other.income, t)!,
      expense: Color.lerp(expense, other.expense, t)!,
    );
  }
}

/// 操作の**強さ**。`button.primary`/`button.secondary`が意味するもの。
///
/// 色コードではなく強弱で持つのは、Material の emphasis 体系
/// (filled > tonal/outlined > text)にそのまま対応させるためである。
/// 生の色を固定すると、Light/Dark やテーマ変更で破綻する。
enum ForgeButtonEmphasis {
  /// その画面の主要操作。**画面に1つ。**
  primary,

  /// 副次的な操作。取り消し・絞り込み・削除。
  secondary,
}

/// role から操作の強さを引く。`null`なら強弱の指定が無い(既定の見た目)。
ForgeButtonEmphasis? buttonEmphasisFor(String? role) => switch (role) {
      'button.primary' => ForgeButtonEmphasis.primary,
      'navigation.primary' => ForgeButtonEmphasis.primary,
      'button.secondary' => ForgeButtonEmphasis.secondary,
      _ => null,
    };

/// いま描いている Widget に付いている role を、builder へ届けるための
/// スコープ。
///
/// **なぜ必要か**: role は `_build()` が1箇所で被せる設計で、builder は
/// role を知らなかった。被せる方式では「文字を大きくする」「面を付ける」
/// はできても、**ボタンの種類を filled から outlined へ変える**ことは
/// できない——builder が既に作り終えた後だからである。
///
/// そこで、builder を呼ぶ**前**に role をスコープへ置く。被せる方式は
/// そのまま残してあるので、role を1つ足すたびに builder を直す必要は
/// 無い(必要な builder だけが読みに来る)。
class ForgeRoleScope extends InheritedWidget {
  final String? role;

  const ForgeRoleScope({super.key, required this.role, required super.child});

  static String? roleOf(BuildContext context) =>
      context.dependOnInheritedWidgetOfExactType<ForgeRoleScope>()?.role;

  @override
  bool updateShouldNotify(ForgeRoleScope oldWidget) => oldWidget.role != role;
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

/// 強弱に応じたボタンを作る。**ここ1箇所**で決める。
///
/// builder ごとに `FilledButton` / `OutlinedButton` を書き分けると、
/// ボタンを描く場所が増えるたびに強弱の扱いがずれる(`CLAUDE.md` §3
/// 「忘れずに呼ばれる保証が無いものは忘れられる」)。
///
/// 強弱の指定が無いときは、これまでどおり `ElevatedButton`。role の
/// 無い既存の生成物の見た目を1ピクセルも変えないためである。
Widget forgeEmphasisButton({
  required ForgeButtonEmphasis? emphasis,
  required VoidCallback? onPressed,
  required Widget child,
}) =>
    switch (emphasis) {
      // 主要操作は塗りつぶし。画面の中で一番強い。
      ForgeButtonEmphasis.primary => FilledButton(onPressed: onPressed, child: child),
      // 副次操作は輪郭だけ。押せることは分かるが、主張しない。
      ForgeButtonEmphasis.secondary => OutlinedButton(onPressed: onPressed, child: child),
      null => ElevatedButton(onPressed: onPressed, child: child),
    };
