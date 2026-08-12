import 'package:dio/dio.dart';

import '../../../../core/utils/forge_logger.dart';
import '../../domain/entities/generation_outcome.dart';
import '../../domain/repositories/app_generation_repository.dart';
import '../datasources/ai_generation_api.dart';
import 'generation_result_parsing.dart';

/// FastAPI Backend(`run_cognitive_pipeline()`経由の実生成)へ接続する
/// Repository実装。
///
/// 経路: Flutter -> FastAPI(`POST /api/v1/ai/generate`) -> `PromptPipeline`
/// -> `run_cognitive_pipeline()` -> ルールベースforge_ai -> Forge
/// Document JSON -> Flutter ForgeRenderer。
///
/// FORGE v0.2 P0.1対応(以前の`HttpAppGenerationRepository`から継承):
/// Backend(`backend/app/schemas/ai.py`)が実際に返す`{version, status:
/// "success"|"needs_confirmation", result|confirmation, diagnostics}`
/// 形式(エラー時は`{version, status: "error", error: {...}}`)をここで
/// 解釈し、Domain層には`GenerationOutcome`(3種類)だけを見せる。
///
/// dioは既定で2xx以外のステータスコードを`DioException`として投げる
/// (`response`には解析済みのError Envelopeボディが入っている)。この
/// Repositoryは、以下の3種類を明確に区別してログ・例外を分ける
/// (「Backend接続」指示書の要求: NETWORK/INVALID_RESPONSE/BACKEND)。
///
/// * `NETWORK`   : 通信自体が失敗した(サーバー未起動・タイムアウト・
///                 接続不可)。`e.response`が無い、またはDioの接続系
///                 例外種別に該当する場合。
/// * `INVALID_RESPONSE`: サーバーには到達したが、応答が期待する
///                 Envelope形式(JSON)になっていない(`forge_document`
///                 欠落・JSON構文不正・想定外のstatus値等)。
/// * `BACKEND`   : サーバーが構造化されたError Envelope(`status:
///                 "error"`)を実際に返した場合。これは例外にせず、
///                 `GenerationFailure`という正式な値として返す
///                 (P0.1の設計、UIが「本当に再実行できる」Retryを
///                 実装できるようにするため)。
class ApiAppGenerationRepository implements AppGenerationRepository {
  final AiGenerationApi _api;
  const ApiAppGenerationRepository(this._api);

  static const _scope = 'ApiAppGenerationRepository';

  @override
  Future<GenerationOutcome> generate(String text, {String? provider}) async {
    ForgeLogger.start(_scope, 'generate()');
    // ログへ入力文をそのまま出すが、kDebugMode時のみの出力
    // (`ForgeLogger`実装参照)であり、本番ビルドでは出力されない。
    ForgeLogger.request(_scope, 'prompt="$text" provider=${provider ?? "(default)"}');
    try {
      final body = await _api.generate(text, provider: provider);
      final outcome = _parseOutcome(body);
      _logOutcome(outcome);
      return outcome;
    } on DioException catch (e) {
      return _handleDioException(e);
    }
  }

  @override
  Future<GenerationOutcome> confirm({required String requestId, required String answer}) async {
    ForgeLogger.start(_scope, 'confirm()');
    ForgeLogger.request(_scope, 'requestId="$requestId" answer="$answer"');
    try {
      final body = await _api.confirm(requestId: requestId, answer: answer);
      final outcome = _parseOutcome(body);
      _logOutcome(outcome);
      return outcome;
    } on DioException catch (e) {
      return _handleDioException(e);
    }
  }

  void _logOutcome(GenerationOutcome outcome) {
    switch (outcome) {
      case GenerationSuccess():
        ForgeLogger.success(_scope, 'ForgeDocument received');
      case GenerationNeedsConfirmation():
        ForgeLogger.success(_scope, 'needs_confirmation received');
      case GenerationFailure(:final category):
        ForgeLogger.error(_scope, 'server returned error envelope (BACKEND)', error: category);
    }
  }

  GenerationOutcome _handleDioException(DioException e) {
    final responseBody = e.response?.data;

    // BACKEND: サーバーが構造化されたError Envelopeを返した場合。
    // 例外として上位へ伝播させず、正式なGenerationFailure値として返す
    // (P0.1の設計、UIが実際に再試行できるようにするため)。
    if (responseBody is Map<String, dynamic> && responseBody['status'] == 'error') {
      ForgeLogger.error(_scope, '[BACKEND] structured error envelope', error: responseBody['error']);
      return _parseOutcome(responseBody);
    }

    // サーバーには到達したが、応答が期待する形式になっていない
    // (FastAPI自体がJSON以外を返した、想定外のボディ構造等)。
    if (e.response != null) {
      ForgeLogger.error(_scope, '[INVALID_RESPONSE] unexpected response shape', error: e.response?.data);
      throw const AppGenerationException(
        code: 'INVALID_RESPONSE',
        message: 'サーバーからの応答を解釈できませんでした。',
      );
    }

    // 通信自体が失敗した(サーバー未起動・タイムアウト・接続不可)。
    ForgeLogger.error(_scope, '[NETWORK] ${e.type.name}', error: e.message);
    throw const AppGenerationException(
      code: 'NETWORK_ERROR',
      message: 'サーバーに接続できませんでした。しばらくしてからもう一度お試しください。',
    );
  }

  GenerationOutcome _parseOutcome(Map<String, dynamic> body) {
    final status = body['status'] as String?;
    switch (status) {
      case 'success':
        return _parseSuccess(body);
      case 'needs_confirmation':
        return _parseNeedsConfirmation(body);
      case 'error':
        return _parseFailure(body);
      default:
        ForgeLogger.error(_scope, '[INVALID_RESPONSE] malformed response body', error: 'unknown status: $status');
        throw const AppGenerationException(
          code: 'INVALID_RESPONSE',
          message: 'サーバーからの応答を解釈できませんでした。',
        );
    }
  }

  GenerationSuccess _parseSuccess(Map<String, dynamic> body) {
    final result = body['result'] as Map<String, dynamic>?;
    if (result == null) {
      ForgeLogger.error(_scope, '[INVALID_RESPONSE] result missing from success response');
      throw const AppGenerationException(
        code: 'INVALID_RESPONSE',
        message: 'サーバーからの応答にアプリのデータが含まれていませんでした。',
      );
    }
    return parseGenerationSuccessResult(result);
  }

  GenerationNeedsConfirmation _parseNeedsConfirmation(Map<String, dynamic> body) =>
      parseGenerationNeedsConfirmation(body);

  GenerationFailure _parseFailure(Map<String, dynamic> body) => parseGenerationFailure(body);
}
