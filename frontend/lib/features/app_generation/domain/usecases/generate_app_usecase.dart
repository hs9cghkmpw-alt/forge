import '../entities/generation_outcome.dart';
import '../repositories/app_generation_repository.dart';

/// 1ユースケース = 1クラス(backend/app/domain/README.md と対称の規約)。
/// 現段階では単純な委譲のみだが、将来ここにログ記録・キャッシュ判断等を足せる。
class GenerateAppUseCase {
  final AppGenerationRepository _repository;
  const GenerateAppUseCase(this._repository);

  Future<GenerationOutcome> call(String text) => _repository.generate(text);
}

/// FORGE v0.2 P0.2対応: `needs_confirmation`への回答送信ユースケース。
class ConfirmGenerationUseCase {
  final AppGenerationRepository _repository;
  const ConfirmGenerationUseCase(this._repository);

  Future<GenerationOutcome> call({required String requestId, required String answer}) =>
      _repository.confirm(requestId: requestId, answer: answer);
}
