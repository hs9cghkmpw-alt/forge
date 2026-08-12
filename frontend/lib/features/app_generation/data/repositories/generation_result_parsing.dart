import '../../domain/entities/generation_outcome.dart';
import '../../domain/repositories/app_generation_repository.dart';

/// `result`(Backendの`GenerateResultDTO`、`/generate`・`/generate/
/// confirm`・`/converse`のBUILD結果いずれも同じ形)を`GenerationSuccess`
/// へ変換する。
///
/// FORGE-PRODUCT-VISION-002(2026-08-11)新設: 元々`ApiAppGenerationRepository`
/// にprivateメソッドとして存在した解析ロジックを、`ApiConversationRepository`
/// (`/converse`)とも共有できるよう、この共有ファイルへ切り出した
/// (ロジックの実体を2箇所へ重複させない、ADR-014と同じ「既存資産の
/// 再利用」方針)。挙動は切り出し前と完全に同一。
GenerationSuccess parseGenerationSuccessResult(Map<String, dynamic> result) {
  final document = result['forge_document'] as Map<String, dynamic>?;
  if (document == null) {
    throw const AppGenerationException(
      code: 'INVALID_RESPONSE',
      message: 'サーバーからの応答にアプリのデータが含まれていませんでした。',
    );
  }
  return GenerationSuccess(
    forgeDocument: document,
    diagnostics: parseGenerationDiagnostics(result['diagnostics'] as Map<String, dynamic>?),
    quality: parseGenerationQuality(result['quality'] as Map<String, dynamic>?),
  );
}

GenerationNeedsConfirmation parseGenerationNeedsConfirmation(Map<String, dynamic> body) {
  final confirmation = body['confirmation'] as Map<String, dynamic>?;
  if (confirmation == null) {
    throw const AppGenerationException(
      code: 'INVALID_RESPONSE',
      message: 'サーバーからの応答を解釈できませんでした。',
    );
  }
  return GenerationNeedsConfirmation(
    requestId: confirmation['request_id'] as String? ?? '',
    question: confirmation['question'] as String? ?? '確認が必要です。',
    reason: confirmation['reason'] as String? ?? '',
    reachedStage: confirmation['reached_stage'] as String? ?? '',
    openQuestions: (confirmation['open_questions'] as List<dynamic>?)?.cast<String>() ?? const [],
    roundsRemaining: confirmation['rounds_remaining'] as int? ?? 0,
  );
}

GenerationFailure parseGenerationFailure(Map<String, dynamic> body) {
  final error = body['error'] as Map<String, dynamic>?;
  return GenerationFailure(
    category: error?['category'] as String? ?? 'unexpected_error',
    subReason: error?['sub_reason'] as String?,
    message: error?['message'] as String? ?? '処理に失敗しました。',
    retryable: error?['retryable'] as bool? ?? false,
    reachedStage: error?['reached_stage'] as String?,
  );
}

GenerationDiagnostics parseGenerationDiagnostics(Map<String, dynamic>? diagnostics) {
  if (diagnostics == null) {
    return const GenerationDiagnostics(engineUsed: 'forge_ai', providerUsed: 'unknown', repairAttempts: 0);
  }
  return GenerationDiagnostics(
    engineUsed: diagnostics['engine_used'] as String? ?? 'forge_ai',
    providerUsed: diagnostics['provider_used'] as String? ?? 'unknown',
    repairAttempts: diagnostics['repair_attempts'] as int? ?? 0,
    cognitiveRevisionAttempts: diagnostics['cognitive_revision_attempts'] as int? ?? 0,
    conversionWarnings: (diagnostics['conversion_warnings'] as List<dynamic>?)?.cast<String>() ?? const [],
    domainClassification: diagnostics['domain_classification'] as Map<String, dynamic>?,
    decisionTrace: (diagnostics['decision_trace'] as List<dynamic>?)?.cast<Map<String, dynamic>>() ?? const [],
  );
}

GenerationQualitySummary? parseGenerationQuality(Map<String, dynamic>? quality) {
  if (quality == null) return null;
  return GenerationQualitySummary(
    score: quality['score'] as int? ?? 0,
    releaseReady: quality['release_ready'] as bool? ?? false,
    requiredFixes: (quality['required_fixes'] as List<dynamic>?)?.cast<String>() ?? const [],
  );
}
