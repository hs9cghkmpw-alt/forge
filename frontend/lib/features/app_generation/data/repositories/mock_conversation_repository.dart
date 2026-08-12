import '../../../../core/utils/forge_logger.dart';
import '../../domain/entities/conversation_outcome.dart';
import '../../domain/entities/generation_outcome.dart';
import '../../domain/repositories/conversation_repository.dart';
import '../datasources/mock_generation_datasource.dart';

/// HTTP通信を一切行わない、Mock Mode用のConversation Repository実装
/// (`mock_app_generation_repository.dart`と同じ設計方針)。
///
/// **正直な制限**: `MockGenerationDataSource`はキーワードマッチングに
/// よる決定的な生成のみを行い、複数ターンの会話・ASK判断・UPDATE
/// (TD40)という概念を一切持たない。そのため、このRepositoryは常に
/// 即座に`ConversationBuilt`を返す(1ターン目の入力だけで生成する、
/// 既存の`MockAppGenerationRepository.generate()`と同じ挙動)。
/// `currentDocument`が渡されていても無視する(Mock ModeではUPDATEに
/// 対応しない、`mock_app_generation_repository.dart`の`confirm()`と
/// 同じ「正直な制限として記録する」方針)。
class MockConversationRepository implements ConversationRepository {
  final MockGenerationDataSource _dataSource;
  const MockConversationRepository(this._dataSource);

  static const _scope = 'MockConversationRepository';
  static const _artificialDelay = Duration(milliseconds: 650);

  @override
  Future<ConversationOutcome> converse({
    String? sessionId,
    required String message,
    String? provider,
    Map<String, dynamic>? currentDocument,
  }) async {
    ForgeLogger.start(_scope, 'converse() called (mock, no network, always builds immediately)');
    ForgeLogger.request(_scope, 'building mock document for: "$message"');
    await Future<void>.delayed(_artificialDelay);

    final document = _dataSource.generate(message);
    ForgeLogger.success(_scope, 'mock document ready');
    return ConversationBuilt(
      buildBrief: message,
      result: GenerationSuccess(
        forgeDocument: document,
        diagnostics: const GenerationDiagnostics(engineUsed: 'forge_ai', providerUsed: 'mock', repairAttempts: 0),
      ),
    );
  }
}
