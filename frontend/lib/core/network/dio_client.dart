import 'package:dio/dio.dart';

import '../config/app_config.dart';

/// FORGE-RUNTIME-001 Task 1でBase URLを`AppConfig`へ統合した
/// (`core/config`ができるまでの暫定値、という位置づけ自体はAppConfig側の
/// コメントに引き継いでいる。ここに重複して定数を持たない)。
Dio createForgeDioClient() {
  return Dio(
    BaseOptions(
      baseUrl: AppConfig.current.apiBaseUrl,
      connectTimeout: const Duration(seconds: 10),
      receiveTimeout: const Duration(seconds: 10),
      contentType: 'application/json',
    ),
  );
}
