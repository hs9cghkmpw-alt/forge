import '../entities/conversation_outcome.dart';

/// FORGE-PRODUCT-VISION-002(2026-08-11)。`app_generation_repository.dart`
/// と同じ依存ルール(外部技術への依存を持たない契約)。
abstract class ConversationRepository {
  /// 会話を1ターン進める。`sessionId`は2ターン目以降、直前の
  /// `ConversationAsk.sessionId`をそのまま渡す(1ターン目は`null`)。
  ///
  /// `currentDocument`は、Held画面(既に生成済みのツールを表示中)から
  /// 会話を再開した場合にのみ渡す。渡した場合のみ、結果として
  /// `ConversationUpdated`が返りうる(TD40)。
  Future<ConversationOutcome> converse({
    String? sessionId,
    required String message,
    String? provider,
    Map<String, dynamic>? currentDocument,
  });
}
