import 'package:flutter/material.dart';

import '../../json_ui/renderer/design_language.dart';

/// Prototype v0.1.3 (lib/core/theme.dart) から移植。
/// Forge の見た目の方針:
/// - 静か / 軽い / 余白 / 未来感
/// - ChatGPT風・管理画面風・ボタンだらけを避ける
/// - 情報量を絞り、中央に大きな余白を作る
///
/// FORGE-MERGE-001 5.2節「残すもの」の「テーマの方向性」に基づき、
/// 値はPrototypeから変更していない。
///
/// 2026-07-16: Forgeロゴ(ネイビーの"F"+オレンジのドット、暖色系の
/// クリーム背景)に合わせて配色を更新した(CEO提示のUIモックアップに
/// 準拠)。`accent`をオレンジへ、`background`を暖色系のクリームへ変更。
/// 主要ボタンの既定色も`ink`から`accent`へ変更し、ホーム画面・生成フロー・
/// (Rendererが描画する)生成後アプリの両方で一貫したブランド色になるようにした。
class ForgeTheme {
  static const Color background = Color(0xFFF7F4EF);
  static const Color surface = Color(0xFFFFFFFF);
  static const Color ink = Color(0xFF1C1C24);
  // FORGE v0.2 P5対応: 旧#8A8A8E は背景(#F7F4EF)とのコントラスト比が
  // 約3.13:1でWCAG AA通常文字基準(4.5:1)を満たさなかった。#6B6B70へ
  // 一段濃くし、背景で4.83:1・白背景で5.30:1を確保した(実測値、
  // このファイル冒頭のコメントの色相・トーンは維持しつつ濃度のみ調整)。
  static const Color inkSoft = Color(0xFF6B6B70);
  static const Color accent = Color(0xFFE0A45C);
  static const Color accentSoft = Color(0xFFF7E9D7);

  // FORGE-UI-REFRESH(2026-08-10): CEO提示の新UIモックアップに基づく
  // 「AIが考えている最中」向けダークパレット。ホーム画面・生成中画面だけで
  // 使う専用トークンであり、`MaterialApp.darkTheme`(システム全体の
  // ダークモード切り替え)ではない。完成画面・Rendererが描画する生成後
  // アプリは、既存のlightな`background`/`ink`のまま据え置く
  // (CEO提示モックアップ自体、画面ごとに意図的に配色を切り替えている。
  // システム全体トグルではなく、「思考中は暗く・完成後は明るく」という
  // 画面単位の演出)。
  //
  // 実測コントラスト比(WCAG、黒背景#0B0F1F・カード#161B2Eに対して):
  // consoleInk 17.28:1 / 15.48:1、consoleInkSoft 8.47:1 / 7.59:1
  // (いずれもAA本文基準4.5:1を大きく上回る)。
  static const Color consoleBackground = Color(0xFF0B0F1F);
  static const Color consoleSurface = Color(0xFF161B2E);
  static const Color consoleInk = Color(0xFFF4F3FA);
  static const Color consoleInkSoft = Color(0xFFA7ACC4);
  static const Color consoleBorder = Color(0xFF262C46);

  // FORGE-UI-REFRESH(2026-08-10): 「Forge AI」を表す紫→青のブランド
  // グラデーション(モックアップのSparkleロゴ・生成中オーブ・主要CTAで使用)。
  // 白文字を乗せる用途があるため、単なる見た目ではなく実測コントラスト比で
  // 選定した: 白文字/gradientStart 6.67:1、白文字/gradientEnd 5.80:1
  // (いずれもWCAG AA本文基準4.5:1を満たす。既存`accent`のオレンジは
  // カード内の小さなアイコン用途に残し、置き換えない)。
  static const Color gradientStart = Color(0xFF5A3FD9);
  static const Color gradientEnd = Color(0xFF2E5CD6);
  static const LinearGradient brandGradient = LinearGradient(
    colors: [gradientStart, gradientEnd],
    begin: Alignment.topLeft,
    end: Alignment.bottomRight,
  );

  static ThemeData get theme {
    return ThemeData(
      useMaterial3: true,
      // Design Languageの**意味の色**(FORGE-R1-CLOSURE-015 §7)。
      // 「成功」「支出」が何色になるかはここで決まり、参照側
      // (`design_language.dart`)は意味の名前だけを言う。
      extensions: const [ForgeSemanticColors.light],
      scaffoldBackgroundColor: background,
      colorScheme: ColorScheme.fromSeed(
        seedColor: accent,
        brightness: Brightness.light,
        surface: surface,
      ),
      fontFamily: 'Helvetica',
      textTheme: const TextTheme(
        headlineMedium: TextStyle(
          fontSize: 26,
          fontWeight: FontWeight.w600,
          color: ink,
          letterSpacing: -0.5,
        ),
        bodyLarge: TextStyle(
          fontSize: 16,
          color: ink,
          height: 1.4,
        ),
        bodyMedium: TextStyle(
          fontSize: 14,
          color: inkSoft,
          height: 1.4,
        ),
      ),
      appBarTheme: const AppBarTheme(
        backgroundColor: background,
        elevation: 0,
        surfaceTintColor: Colors.transparent,
        foregroundColor: ink,
        centerTitle: true,
      ),
      elevatedButtonTheme: ElevatedButtonThemeData(
        style: ElevatedButton.styleFrom(
          backgroundColor: accent,
          // FORGE v0.2 P5対応: 白文字(#FFFFFF)とaccent(#E0A45C)の
          // コントラスト比は約2.18:1で、WCAG AA(通常文字4.5:1・大きな
          // 文字3:1)を満たさない。ink(ネイビー系、#1C1C24)へ変更する
          // (accent自体の色相は変更しない、指示書の選択肢1を採用)。
          foregroundColor: ink,
          // FORGE-RUNTIME-003 Task 1(根本原因の修正): `Size.fromHeight(56)` は
          // 実際には `Size(double.infinity, 56)` を返す(Flutter公式実装:
          // `Size.fromHeight(height) : this(double.infinity, height)`)。
          // これがColumn(cross-axis、bounded)の中では制約に収まってしまい
          // 「全幅ボタン」に見えていたが、Row(main-axis、非flex子には
          // unboundedな制約が渡る)の中では
          // 「BoxConstraints forces an infinite width」で描画自体が失敗していた
          // (FORGE-RUNTIME-003-report.md 参照)。Buttonはこのテーマを
          // アプリ全体(ネイティブ画面・Runtime生成画面の両方)で共有しているため、
          // ここを直接infinite widthにしないことがRow/Column両方で安全な唯一の方法。
          // 全幅にしたい場所は、呼び出し側で明示的に`SizedBox(width: double.infinity)`
          // または`crossAxisAlignment: stretch`を使う(Task 2の方針)。
          minimumSize: const Size(0, 56),
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(20),
          ),
          elevation: 0,
          textStyle: const TextStyle(
            fontSize: 16,
            fontWeight: FontWeight.w600,
          ),
        ),
      ),
      inputDecorationTheme: InputDecorationTheme(
        filled: true,
        fillColor: surface,
        contentPadding: const EdgeInsets.symmetric(horizontal: 20, vertical: 18),
        border: OutlineInputBorder(
          borderRadius: BorderRadius.circular(20),
          borderSide: const BorderSide(color: Color(0xFFE8E8E6)),
        ),
        enabledBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(20),
          borderSide: const BorderSide(color: Color(0xFFE8E8E6)),
        ),
        focusedBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(20),
          borderSide: const BorderSide(color: accent, width: 1.5),
        ),
        hintStyle: const TextStyle(color: inkSoft),
      ),
    );
  }
}
