import 'dart:math';

import 'package:flutter/material.dart';

import '../core/theme/forge_theme.dart';

/// Forgeの新ロゴ("✦"のSparkleマーク)。
///
/// FORGE-UI-REFRESH(2026-08-10): CEO提示のUIモックアップは、既存の
/// `ForgeMark`(`assets/images/forge_f_mark.png`、ネイビーのF+オレンジの
/// ドット)ではなく、"✦ Forge"というSparkleアイコン+ワードマークを使って
/// いる。実際のロゴ画像アセットは提供されていないため、`CustomPainter`で
/// 四方向Sparkle形状をベクター描画する(新規アセットファイル追加なし、
/// 新規パッケージ依存なし)。`ForgeTheme.brandGradient`で塗る。
///
/// 旧`ForgeMark`(PNGアセット)は削除していない。本Widgetへの置き換えは
/// `home_screen.dart`・`generation_flow_screen.dart`の4箇所のみで、
/// それ以外に`ForgeMark`の参照は無いことを確認済み。
class ForgeSparkleMark extends StatelessWidget {
  final double size;
  final Gradient? gradient;

  const ForgeSparkleMark({super.key, this.size = 96, this.gradient});

  @override
  Widget build(BuildContext context) {
    return CustomPaint(
      size: Size(size, size),
      painter: _SparklePainter(gradient: gradient ?? ForgeTheme.brandGradient),
    );
  }
}

class _SparklePainter extends CustomPainter {
  final Gradient gradient;

  const _SparklePainter({required this.gradient});

  @override
  void paint(Canvas canvas, Size size) {
    final rect = Offset.zero & size;
    final paint = Paint()..shader = gradient.createShader(rect);
    canvas.drawPath(_sparklePath(size), paint);
  }

  /// 4方向のSparkle形状(外側4点+内側4点の8角形の星)を、中心から
  /// 交互に外側/内側半径で結んで作る。実測に基づかない見た目の値だが、
  /// 決定的な幾何計算であり、実行時に崩れる余地は無い。
  Path _sparklePath(Size size) {
    final center = Offset(size.width / 2, size.height / 2);
    final outerRadius = size.shortestSide / 2;
    final innerRadius = outerRadius * 0.34;
    const points = 4;
    final path = Path();
    for (var i = 0; i < points * 2; i++) {
      final angle = (pi / points) * i - pi / 2;
      final radius = i.isEven ? outerRadius : innerRadius;
      final offset = Offset(
        center.dx + radius * cos(angle),
        center.dy + radius * sin(angle),
      );
      if (i == 0) {
        path.moveTo(offset.dx, offset.dy);
      } else {
        path.lineTo(offset.dx, offset.dy);
      }
    }
    path.close();
    return path;
  }

  @override
  bool shouldRepaint(covariant _SparklePainter oldDelegate) => oldDelegate.gradient != gradient;
}
