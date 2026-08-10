import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../../core/config/app_config.dart';
import '../../../../core/di/network_providers.dart';
import '../../data/datasources/ai_generation_api.dart';
import '../../data/datasources/mock_generation_datasource.dart';
import '../../data/repositories/api_app_generation_repository.dart';
import '../../data/repositories/mock_app_generation_repository.dart';
import '../../domain/entities/generation_outcome.dart';
import '../../domain/repositories/app_generation_repository.dart';
import '../../domain/usecases/generate_app_usecase.dart';

// riverpod_generator(@riverpod アノテーション)は使わず手書きにしている。
// 理由はDECISIONS.md参照(freezedを見送った理由と同じ: build_runner無しで
// このまま `flutter run` できるようにするため)。

/// FORGE-RUNTIME-001 Task 1/2: `AppConfig.current.mockMode` に応じて
/// `ApiAppGenerationRepository` と `MockAppGenerationRepository` を切り替える。
/// 画面側(GenerationFlowScreen等)はこのProviderの先がどちらかを一切知らない。
final appGenerationRepositoryProvider = Provider<AppGenerationRepository>((ref) {
  if (AppConfig.current.mockMode) {
    return const MockAppGenerationRepository(MockGenerationDataSource());
  }
  final dio = ref.watch(dioClientProvider);
  return ApiAppGenerationRepository(AiGenerationApi(dio));
});

final _generateAppUseCaseProvider = Provider<GenerateAppUseCase>((ref) {
  return GenerateAppUseCase(ref.watch(appGenerationRepositoryProvider));
});

final _confirmGenerationUseCaseProvider = Provider<ConfirmGenerationUseCase>((ref) {
  return ConfirmGenerationUseCase(ref.watch(appGenerationRepositoryProvider));
});

/// FORGE v0.2 P5(9番)対応: 生成リクエストの識別子。
///
/// 以前は`FutureProvider.family<Map<String, dynamic>, String>`のように、
/// 入力テキストそのものをキーにしていたため、Riverpodの標準動作
/// (同じキーへの`watch`は同じFutureを再利用する)により、「もう一度試す」
/// (Retry)や「同じ文章で再生成」が、実際には新しい生成を行わず、以前の
/// 結果(あるいは以前失敗したFuture)をそのまま返してしまうバグがあった。
///
/// `GenerationRequest`は`text`に加えて`nonce`(操作ごとに一意な値)を
/// 持つため、`==`/`hashCode`が同じ文章でも操作ごとに異なる値になり、
/// Riverpodが必ず新しいFutureとして扱う。
class GenerationRequest {
  final String text;
  final int nonce;

  const GenerationRequest({required this.text, required this.nonce});

  @override
  bool operator ==(Object other) =>
      other is GenerationRequest && other.text == text && other.nonce == nonce;

  @override
  int get hashCode => Object.hash(text, nonce);
}

/// 単調増加するnonceを払い出す。生成操作(初回送信・Retry・確認回答の
/// いずれか)のたびに`nextNonce()`を呼び、新しい`GenerationRequest`を作る。
final generationNonceProvider = StateProvider<int>((ref) => 0);

/// 生成結果を保持する。`FutureProvider.autoDispose.family`にすることで、
/// 画面が破棄されたら結果も破棄され、古い結果が別の画面遷移で
/// 意図せず再利用されることも防ぐ。
final appGenerationProvider =
    FutureProvider.autoDispose.family<GenerationOutcome, GenerationRequest>((ref, request) {
  final useCase = ref.watch(_generateAppUseCaseProvider);
  return useCase(request.text);
});

/// FORGE v0.2 P0.2対応: 確認回答送信用のリクエスト識別子(生成側と同じ、
/// nonceによるキャッシュ回避の考え方を踏襲する)。
class ConfirmationAnswerRequest {
  final String requestId;
  final String answer;
  final int nonce;

  const ConfirmationAnswerRequest({required this.requestId, required this.answer, required this.nonce});

  @override
  bool operator ==(Object other) =>
      other is ConfirmationAnswerRequest &&
      other.requestId == requestId &&
      other.answer == answer &&
      other.nonce == nonce;

  @override
  int get hashCode => Object.hash(requestId, answer, nonce);
}

final confirmGenerationProvider =
    FutureProvider.autoDispose.family<GenerationOutcome, ConfirmationAnswerRequest>((ref, request) {
  final useCase = ref.watch(_confirmGenerationUseCaseProvider);
  return useCase(requestId: request.requestId, answer: request.answer);
});
