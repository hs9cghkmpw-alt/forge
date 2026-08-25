/// FORGE v0.2 P0.1・P0.2対応。
///
/// Backend(`backend/app/schemas/ai.py`)の`status`フィールド
/// (`success` / `needs_confirmation` / エラー時は例外)を、
/// Domain層の型として表現したもの。以前は`generate()`が
/// `Map<String, dynamic>`(成功時のdocumentのみ)を返し、確認要求は
/// 一切表現できず、失敗は`AppGenerationException`をthrowするだけだった。
///
/// `sealed class`により、呼び出し側は`switch`で3種類を漏れなく
/// 分岐できる(Dart 3のsealed class網羅性チェックを利用する)。
sealed class GenerationOutcome {
  const GenerationOutcome();
}

/// 生成成功。`forgeDocument`はValidator合格済みのForge Language JSON。
class GenerationSuccess extends GenerationOutcome {
  final Map<String, dynamic> forgeDocument;
  final GenerationDiagnostics diagnostics;
  final GenerationQualitySummary? quality;
  final ArtifactIdentity? artifact;

  const GenerationSuccess({
    required this.forgeDocument,
    required this.diagnostics,
    this.quality,
    this.artifact,
  });
}

/// Ephemeral client capability for feedback/revision. Never dataset lineage.
class ArtifactIdentity {
  final String artifactId;
  final String versionToken;

  const ArtifactIdentity({required this.artifactId, required this.versionToken});
}

/// Backendが`status: "needs_confirmation"`を返した場合。
/// 例外にせず、正式な結果型として扱う(P0.2「途中でthrowして終了は禁止」)。
class GenerationNeedsConfirmation extends GenerationOutcome {
  /// この確認セッションの追跡ID。`/generate/confirm`へそのまま渡す。
  final String requestId;
  final String question;
  final String reason;
  final String reachedStage;
  final List<String> openQuestions;
  final int roundsRemaining;

  const GenerationNeedsConfirmation({
    required this.requestId,
    required this.question,
    required this.reason,
    required this.reachedStage,
    required this.openQuestions,
    required this.roundsRemaining,
  });
}

/// 生成失敗。Backend Error Envelope(`category`/`sub_reason`/`message`/
/// `retryable`/`reached_stage`)をそのまま保持する。
class GenerationFailure extends GenerationOutcome {
  final String category;
  final String? subReason;
  final String message;
  final bool retryable;
  final String? reachedStage;

  const GenerationFailure({
    required this.category,
    required this.message,
    this.subReason,
    this.retryable = false,
    this.reachedStage,
  });
}

/// 診断情報(`diagnostics`)の、Frontendが実際に利用する部分だけを保持する。
/// Backendの全フィールドを機械的に複製するのではなく、UIが必要とする
/// ものだけへ絞っている(完成画面の機能概要表示等で使う、指示書18章)。
class GenerationDiagnostics {
  final String engineUsed;
  final String providerUsed;
  final int repairAttempts;
  final int cognitiveRevisionAttempts;
  final List<String> conversionWarnings;
  final Map<String, dynamic>? domainClassification;
  final List<Map<String, dynamic>> decisionTrace;

  const GenerationDiagnostics({
    required this.engineUsed,
    required this.providerUsed,
    required this.repairAttempts,
    this.cognitiveRevisionAttempts = 0,
    this.conversionWarnings = const [],
    this.domainClassification,
    this.decisionTrace = const [],
  });
}

class GenerationQualitySummary {
  final int score;
  final bool releaseReady;
  final List<String> requiredFixes;

  const GenerationQualitySummary({
    required this.score,
    required this.releaseReady,
    this.requiredFixes = const [],
  });
}
