import 'generation_outcome.dart';

/// FORGE-PRODUCT-VISION-002(2026-08-11)。Backendの`POST /api/v1/ai/
/// converse`(`backend/app/schemas/ai.py`の`ConverseAskResponse`/
/// `ConverseBuildResponse`/`ConverseUpdateResponse`)を、Domain層の型と
/// して表現したもの。`generation_outcome.dart`の設計方針(sealed class、
/// 呼び出し側が`switch`で網羅的に分岐する)をそのまま踏襲する。
///
/// `Built`・`FallbackConfirmation`・`Failure`は、既存の`GenerationOutcome`
/// 系の型を中身として持つ(ADR-014: Conversation EngineはForge Language
/// 知識を一切持たず、既存の`/generate`と同じ結果をそのまま横流しする、
/// というBackendの設計をFrontend側でも踏襲し、型の重複を避ける)。
sealed class ConversationOutcome {
  const ConversationOutcome();
}

/// もう1問だけ聞かれた状態。
class ConversationAsk extends ConversationOutcome {
  final String sessionId;
  final String question;
  final NeedModelSummary needModel;

  const ConversationAsk({required this.sessionId, required this.question, required this.needModel});
}

/// Forgeが実行前に確認を求めている(FORGE-CONVERSATION-READY-001、
/// 2026-08-12、指示書4章)。
///
/// 外部送信・共有・公開・削除・金銭・権限変更など、**Forgeの外へ影響が
/// 及ぶ、または元に戻せない**操作を含む依頼に対してのみ返る。専用の
/// 確認画面へ遷移するのではなく、ASKと同じく会話の1ターンとして扱う
/// (指示書4章「Confirm Screenを復活させるのではなく、必要な時だけ
/// 会話の中で確認する」)。
class ConversationConfirm extends ConversationOutcome {
  final String sessionId;
  final String question;

  /// なぜ確認が必要なのか(「外部へ影響が及ぶため」等)。
  final String reason;

  final NeedModelSummary needModel;

  const ConversationConfirm({
    required this.sessionId,
    required this.question,
    required this.reason,
    required this.needModel,
  });
}

/// 新しいツールが生成された(Space/Formingの終着点、「はい、どうぞ」)。
class ConversationBuilt extends ConversationOutcome {
  final String buildBrief;
  final GenerationSuccess result;

  const ConversationBuilt({required this.buildBrief, required this.result});
}

/// 既存ツールが更新された(Held→Forming→Held、TD40)。
class ConversationUpdated extends ConversationOutcome {
  final String changeRequest;
  final Map<String, dynamic> forgeDocument;
  final bool valid;
  final int attempts;

  const ConversationUpdated({
    required this.changeRequest,
    required this.forgeDocument,
    required this.valid,
    required this.attempts,
  });
}

/// Conversation Engine自身は`build`と判定したが、その先の既存Cognitive
/// Pipeline側がさらに`needs_confirmation`を返した場合(実機確認済み、
/// TECH_DEBT.md TD参照)。既存の確認UI・`/generate/confirm`フローへ
/// そのまま委ねる。
class ConversationFallbackConfirmation extends ConversationOutcome {
  final GenerationNeedsConfirmation confirmation;
  const ConversationFallbackConfirmation(this.confirmation);
}

class ConversationFailure extends ConversationOutcome {
  final GenerationFailure failure;
  const ConversationFailure(this.failure);
}

/// `NeedModel`(Backend)のFrontend表現。会話の途中経過をUIへうっすら
/// 見せる用途のみ(指示書14章「内部処理はユーザーへ見せない」を踏まえ、
/// UIでは`problem`程度の要約以外は積極的に表示しない設計を想定)。
class NeedModelSummary {
  final String problem;
  final List<String> knownFacts;
  final List<String> safeAssumptions;

  const NeedModelSummary({required this.problem, this.knownFacts = const [], this.safeAssumptions = const []});
}
