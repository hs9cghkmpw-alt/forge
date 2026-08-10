import 'package:flutter/foundation.dart' show kDebugMode, debugPrint;

/// FORGE-RUNTIME-001 Task 9。
///
/// 新規パッケージ依存を追加せず(`logging`パッケージ等)、標準の`debugPrint`を
/// 出力先として使いながら、呼び出し側からは常にこの`ForgeLogger`経由で
/// 呼ぶことで「散らばった生の`debugPrint`呼び出し」を無くす、という方針にした
/// (禁止事項「Dependency更新」に抵触するリスクを避けるため)。
///
/// 最低限、生成フローの4段階(start/request/success/error)を記録する。
enum ForgeLogLevel { start, request, success, error }

class ForgeLogger {
  const ForgeLogger._();

  static void start(String scope, String message) => _log(ForgeLogLevel.start, scope, message);
  static void request(String scope, String message) => _log(ForgeLogLevel.request, scope, message);
  static void success(String scope, String message) => _log(ForgeLogLevel.success, scope, message);
  static void error(String scope, String message, {Object? error}) =>
      _log(ForgeLogLevel.error, scope, message, error: error);

  static void _log(ForgeLogLevel level, String scope, String message, {Object? error}) {
    if (!kDebugMode) return; // production相当では出力しない(方針12章と同じ考え方)
    final tag = switch (level) {
      ForgeLogLevel.start => 'START',
      ForgeLogLevel.request => 'REQUEST',
      ForgeLogLevel.success => 'SUCCESS',
      ForgeLogLevel.error => 'ERROR',
    };
    final suffix = error != null ? ' | $error' : '';
    debugPrint('[Forge][$tag][$scope] $message$suffix');
  }
}
