/// 開発者向け表示を出してよいかどうかを、**compile time に**決める。
///
/// ---
///
/// ## なぜ compile time なのか
///
/// Provider 名・Model 名・Runtime・Port は Forge の内部事情である
/// （Universal Quality Invariant §9「内部の Model、Runtime、Port、SDK、
/// 環境変数を通常利用者へ選ばせない」）。開発者はそれを見たいが、
/// **実行時に切り替えられる仕組みにすると、通常の製品ビルドの中に
/// 「内部を見せる経路」が残る**。残っている限り、いつか誰かが辿り着く。
///
/// したがって既定は `false` で、`--dart-define=FORGE_DEVELOPER_MODE=true`
/// を付けたビルドだけが開発者向け UI を持つ。Release の既定ビルドには
/// tree shaking で消える。
///
/// **これは Mock を実 AI として見せるための抜け道ではない。**
/// 開発者ビルドであっても、疑似出力は疑似出力として表示する
/// （`AiModeState.simulated`）。
library;

/// 開発者向け診断 UI（Provider 名・Model 名等）を出すビルドかどうか。
///
/// 既定 `false`。通常の製品ビルドではこの値は変わらない。
const bool kForgeDeveloperMode =
    bool.fromEnvironment('FORGE_DEVELOPER_MODE', defaultValue: false);
