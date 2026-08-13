import 'package:dio/dio.dart';

import '../../../../core/utils/forge_logger.dart';
import '../../domain/entities/conversation_outcome.dart';
import '../../domain/repositories/app_generation_repository.dart';
import '../../domain/repositories/conversation_repository.dart';
import '../datasources/ai_conversation_api.dart';
import 'generation_result_parsing.dart';

/// `POST /api/v1/ai/converse`へ接続するRepository実装
/// (FORGE-PRODUCT-VISION-002、2026-08-11)。`api_app_generation_
/// repository.dart`と同じ設計方針(NETWORK/INVALID_RESPONSE/BACKEND
/// の区別、エラーを例外にせず正式な値として返す)を踏襲する。
class ApiConversationRepository implements ConversationRepository {
  final AiConversationApi _api;
  const ApiConversationRepository(this._api);

  static const _scope = 'ApiConversationRepository';

  @override
  Future<ConversationOutcome> converse({
    String? sessionId,
    required String message,
    String? provider,
    Map<String, dynamic>? currentDocument,
  }) async {
    ForgeLogger.start(_scope, 'converse()');
    ForgeLogger.request(_scope, 'sessionId=$sessionId message="$message" provider=${provider ?? "(default)"}');
    try {
      final body = await _api.converse(
        sessionId: sessionId, message: message, provider: provider, currentDocument: currentDocument,
      );
      final outcome = _parseOutcome(body);
      _logOutcome(outcome);
      return outcome;
    } on DioException catch (e) {
      return _handleDioException(e);
    }
  }

  void _logOutcome(ConversationOutcome outcome) {
    switch (outcome) {
      case ConversationAsk():
        ForgeLogger.success(_scope, 'ask received');
      case ConversationConfirm():
        ForgeLogger.success(_scope, 'confirm received');
      case ConversationBuilt():
        ForgeLogger.success(_scope, 'build received');
      case ConversationUpdated():
        ForgeLogger.success(_scope, 'update received');
      case ConversationFallbackConfirmation():
        ForgeLogger.success(_scope, 'fallback needs_confirmation received');
      case ConversationFailure(:final failure):
        ForgeLogger.error(_scope, 'server returned error envelope (BACKEND)', error: failure.category);
    }
  }

  ConversationOutcome _handleDioException(DioException e) {
    final responseBody = e.response?.data;

    if (responseBody is Map<String, dynamic> && responseBody['status'] == 'error') {
      ForgeLogger.error(_scope, '[BACKEND] structured error envelope', error: responseBody['error']);
      return _parseOutcome(responseBody);
    }

    if (e.response != null) {
      ForgeLogger.error(_scope, '[INVALID_RESPONSE] unexpected response shape', error: e.response?.data);
      throw const AppGenerationException(
        code: 'INVALID_RESPONSE',
        message: 'サーバーからの応答を解釈できませんでした。',
      );
    }

    ForgeLogger.error(_scope, '[NETWORK] ${e.type.name}', error: e.message);
    throw const AppGenerationException(
      code: 'NETWORK_ERROR',
      message: 'サーバーに接続できませんでした。しばらくしてからもう一度お試しください。',
    );
  }

  ConversationOutcome _parseOutcome(Map<String, dynamic> body) {
    final status = body['status'] as String?;
    switch (status) {
      case 'ask':
        return _parseAsk(body);
      case 'confirm':
        return _parseConfirm(body);
      case 'build':
        return _parseBuild(body);
      case 'update':
        return _parseUpdate(body);
      case 'needs_confirmation':
        return ConversationFallbackConfirmation(parseGenerationNeedsConfirmation(body));
      case 'error':
        return ConversationFailure(parseGenerationFailure(body));
      default:
        ForgeLogger.error(_scope, '[INVALID_RESPONSE] malformed response body', error: 'unknown status: $status');
        throw const AppGenerationException(
          code: 'INVALID_RESPONSE',
          message: 'サーバーからの応答を解釈できませんでした。',
        );
    }
  }

  ConversationAsk _parseAsk(Map<String, dynamic> body) {
    final sessionId = body['session_id'] as String?;
    final question = body['question'] as String?;
    if (sessionId == null || question == null) {
      throw const AppGenerationException(
        code: 'INVALID_RESPONSE',
        message: 'サーバーからの応答を解釈できませんでした。',
      );
    }
    return ConversationAsk(
      sessionId: sessionId,
      question: question,
      needModel: _parseNeedModel(body),
      simulated: _parseSimulated(body),
    );
  }

  /// FORGE-CONVERSATION-READY-001(2026-08-12)。`ask`と同じ形
  /// (session_id + question)に、なぜ確認が要るのかを表す`reason`が
  /// 加わる。
  ConversationConfirm _parseConfirm(Map<String, dynamic> body) {
    final sessionId = body['session_id'] as String?;
    final question = body['question'] as String?;
    if (sessionId == null || question == null) {
      throw const AppGenerationException(
        code: 'INVALID_RESPONSE',
        message: 'サーバーからの応答を解釈できませんでした。',
      );
    }
    return ConversationConfirm(
      sessionId: sessionId,
      question: question,
      reason: body['reason'] as String? ?? '',
      needModel: _parseNeedModel(body),
      simulated: _parseSimulated(body),
    );
  }

  ConversationBuilt _parseBuild(Map<String, dynamic> body) {
    final result = body['result'] as Map<String, dynamic>?;
    if (result == null) {
      throw const AppGenerationException(
        code: 'INVALID_RESPONSE',
        message: 'サーバーからの応答にアプリのデータが含まれていませんでした。',
      );
    }
    return ConversationBuilt(
      buildBrief: body['build_brief'] as String? ?? '',
      result: parseGenerationSuccessResult(result),
      simulated: _parseSimulated(body),
    );
  }

  ConversationUpdated _parseUpdate(Map<String, dynamic> body) {
    final result = body['result'] as Map<String, dynamic>?;
    final document = result?['forge_document'] as Map<String, dynamic>?;
    if (result == null || document == null) {
      throw const AppGenerationException(
        code: 'INVALID_RESPONSE',
        message: 'サーバーからの応答にアプリのデータが含まれていませんでした。',
      );
    }
    final validation = result['validation'] as Map<String, dynamic>?;
    return ConversationUpdated(
      changeRequest: body['change_request'] as String? ?? '',
      forgeDocument: document,
      valid: validation?['valid'] as bool? ?? false,
      attempts: result['attempts'] as int? ?? 1,
      simulated: _parseSimulated(body),
    );
  }

  /// FORGE-HANDOFF-LOCAL-AI-UX-004 §9(2026-08-13)。この応答が模擬出力
  /// かどうか。フィールドが無い古いBackendに対しては`false`
  /// (=本物として扱う)ではなく、**存在しない場合のみ**`false`にする
  /// ——新旧どちらのBackendでもクラッシュしないための後方互換。
  bool _parseSimulated(Map<String, dynamic> body) => body['simulated'] as bool? ?? false;

  NeedModelSummary _parseNeedModel(Map<String, dynamic> body) {
    final needModel = body['need_model'] as Map<String, dynamic>?;
    if (needModel == null) return const NeedModelSummary(problem: '');
    return NeedModelSummary(
      problem: needModel['problem'] as String? ?? '',
      knownFacts: (needModel['known'] as List<dynamic>?)?.cast<String>() ?? const [],
      safeAssumptions: (needModel['safe_assumptions'] as List<dynamic>?)?.cast<String>() ?? const [],
    );
  }
}
