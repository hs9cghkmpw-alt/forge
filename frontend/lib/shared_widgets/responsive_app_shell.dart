import 'package:flutter/material.dart';

import '../core/theme/forge_theme.dart';

/// FORGE v0.2 P5対応(Chrome中央最大幅)。
///
/// Chromeでの検証を標準環境とする一方、既存の各画面は`Scaffold`の`body`が
/// ブラウザ幅いっぱいに広がる作りになっており、広いデスクトップ画面では
/// 入力欄・Bottom Sheet等が横に伸びすぎていた。
///
/// この`ResponsiveAppShell`で`Scaffold.body`を包むと、画面本体は
/// モバイルアプリ相当の最大幅(既定480)に制限され、それより広い部分は
/// `ForgeTheme.background`で埋められる。狭い画面(モバイル実機・小さな
/// ブラウザ幅)では、制約が画面幅を超えないため通常通り全幅表示になる。
class ResponsiveAppShell extends StatelessWidget {
  final Widget child;
  final double maxWidth;

  const ResponsiveAppShell({super.key, required this.child, this.maxWidth = 480});

  @override
  Widget build(BuildContext context) {
    return ColoredBox(
      color: ForgeTheme.background,
      child: Center(
        child: ConstrainedBox(
          constraints: BoxConstraints(maxWidth: maxWidth),
          child: child,
        ),
      ),
    );
  }
}
