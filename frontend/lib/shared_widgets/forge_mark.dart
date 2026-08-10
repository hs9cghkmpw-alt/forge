import 'package:flutter/material.dart';

/// Forgeの"F"マーク(ネイビーのF+オレンジのドット)。
///
/// `assets/images/forge_f_mark.png`(CEO提供のロゴから、ワードマーク・
/// タグラインを除いた「Fマーク+ドット」部分だけを切り出したもの)を表示する。
/// ホーム画面のヘッダー・中央アイコン、生成中画面、完成画面など、
/// 複数箇所で使い回すための共有Widget。
class ForgeMark extends StatelessWidget {
  final double size;

  const ForgeMark({super.key, this.size = 96});

  @override
  Widget build(BuildContext context) {
    return Image.asset(
      'assets/images/forge_f_mark.png',
      width: size,
      height: size,
      fit: BoxFit.contain,
    );
  }
}
