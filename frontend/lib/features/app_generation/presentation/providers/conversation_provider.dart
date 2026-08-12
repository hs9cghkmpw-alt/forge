import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../../core/config/app_config.dart';
import '../../../../core/di/network_providers.dart';
import '../../data/datasources/ai_conversation_api.dart';
import '../../data/datasources/mock_generation_datasource.dart';
import '../../data/repositories/api_conversation_repository.dart';
import '../../data/repositories/mock_conversation_repository.dart';
import '../../domain/entities/conversation_outcome.dart';
import '../../domain/repositories/conversation_repository.dart';

/// FORGE-PRODUCT-VISION-002(2026-08-11)。`app_generation_provider.dart`
/// と同じ設計方針(手書きProvider、`AppConfig.current.mockMode`に応じて
/// Api/Mockを切り替え)。
final conversationRepositoryProvider = Provider<ConversationRepository>((ref) {
  if (AppConfig.current.mockMode) {
    return const MockConversationRepository(MockGenerationDataSource());
  }
  final dio = ref.watch(dioClientProvider);
  return ApiConversationRepository(AiConversationApi(dio));
});

/// 会話1ターン分のリクエスト識別子。`app_generation_provider.dart`の
/// `GenerationRequest`と同じ理由(`nonce`によるRiverpodキャッシュ回避)。
class ConversationTurnRequest {
  final String? sessionId;
  final String message;
  final String? provider;
  final Map<String, dynamic>? currentDocument;
  final int nonce;

  const ConversationTurnRequest({
    this.sessionId,
    required this.message,
    this.provider,
    this.currentDocument,
    required this.nonce,
  });

  @override
  bool operator ==(Object other) =>
      other is ConversationTurnRequest &&
      other.sessionId == sessionId &&
      other.message == message &&
      other.provider == provider &&
      other.nonce == nonce;

  @override
  int get hashCode => Object.hash(sessionId, message, provider, nonce);
}

final conversationTurnProvider =
    FutureProvider.autoDispose.family<ConversationOutcome, ConversationTurnRequest>((ref, request) {
  final repository = ref.watch(conversationRepositoryProvider);
  return repository.converse(
    sessionId: request.sessionId,
    message: request.message,
    provider: request.provider,
    currentDocument: request.currentDocument,
  );
});
