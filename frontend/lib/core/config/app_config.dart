/// Forgeアプリ全体の実行時設定。
///
/// **FORGE v0.2 Backend接続対応で全面改訂**: 以前は`FORGE_MOCK_MODE`
/// (既定値`true`、Mockが既定)だったが、指示書の要求により
/// `USE_MOCK_GENERATION`(既定値`false`、**実Backend接続が既定**)へ
/// 変更した。通常の`flutter run`ではAPI(FastAPI経由の`run_cognitive_
/// pipeline()`)を使う。Mockで確認したい場合のみ明示的に
/// `--dart-define=USE_MOCK_GENERATION=true`を付ける。
///
/// **既存テストへの影響(重要)**: この既定値変更により、Provider
/// Override無しでWidget Testを実行すると実ネットワーク接続を試みて
/// しまう。既存の全Widget Test/E2E Testは、`appGenerationRepository
/// Provider`を明示的に`MockAppGenerationRepository`へoverrideする形へ
/// 更新済み(テストは既定値に依存せず、常に確定的であるべきという方針)。
///
/// 使い方:
///   通常の `flutter run -d chrome`                          → API使用(既定)
///   Mock Modeで確認したい場合:
///     flutter run -d chrome --dart-define=USE_MOCK_GENERATION=true
///   Backend接続先を変えたい場合:
///     flutter run -d chrome --dart-define=FORGE_API_BASE_URL=http://127.0.0.1:8000
class AppConfig {
  final bool mockMode;
  final String apiBaseUrl;

  const AppConfig({required this.mockMode, required this.apiBaseUrl});

  /// アプリ全体で参照する唯一のインスタンス。
  /// (Riverpod Providerにしていない理由: 起動前の`main()`や、Provider経由でない
  /// 単純な分岐にも使いたいため、コンパイル時定数として持つ。)
  static const AppConfig current = AppConfig(
    mockMode: bool.fromEnvironment('USE_MOCK_GENERATION', defaultValue: false),
    apiBaseUrl: String.fromEnvironment('FORGE_API_BASE_URL', defaultValue: _defaultApiBaseUrl),
  );

  /// `FORGE_API_BASE_URL`が指定されなかった場合の既定値。
  ///
  /// 検証時の接続先に注意:
  ///   - Chrome (`flutter run -d chrome`)     : そのままで良い
  ///   - iOSシミュレータ                        : そのままで良い
  ///   - Androidエミュレータ                    : `localhost` は使えない。`10.0.2.2` に変更する
  ///   - 実機(Android/iOS)                     : PCと同じWi-Fiに繋ぎ、PCのLAN IPに変更する
  static const String _defaultApiBaseUrl = 'http://127.0.0.1:8000';
}
