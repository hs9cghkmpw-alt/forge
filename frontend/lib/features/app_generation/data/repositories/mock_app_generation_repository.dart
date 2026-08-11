import '../../../../core/utils/forge_logger.dart';
import '../../domain/entities/generation_outcome.dart';
import '../../domain/repositories/app_generation_repository.dart';
import '../datasources/mock_generation_datasource.dart';

/// HTTP通信を一切行わない、Mock Mode用のRepository実装。
/// FORGE-RUNTIME-001 Task 2/3/6。
///
/// 画面側(GenerationFlowScreen等)は`AppGenerationRepository`インターフェースしか
/// 知らないため、`ApiAppGenerationRepository`との差し替えはDI層
/// (presentation/providers/app_generation_provider.dart)だけで完結する。
///
/// FORGE v0.2 P0.1・P0.2対応: `GenerationOutcome`を返すよう変更した。
/// `MockGenerationDataSource`はキーワードマッチングによる決定的な生成のみを
/// 行い、確認要求(needs_confirmation)という概念を持たないため、
/// `generate()`は常に`GenerationSuccess`を返す(正直な制限として記録:
/// Mock ModeではAmbiguity Detection相当の判断は行われない)。
class MockAppGenerationRepository implements AppGenerationRepository {
  final MockGenerationDataSource _dataSource;
  const MockAppGenerationRepository(this._dataSource);

  static const _scope = 'MockAppGenerationRepository';

  /// Task 6: 「ユーザーから見るとAIが生成したように見える」体験のため、
  /// 意図的な遅延を入れる。即座に返すと不自然に速く感じられ、Loading
  /// Indicator(Task 4)がほぼ表示されないまま消えてしまうため。
  static const _artificialDelay = Duration(milliseconds: 650);

  @override
  Future<GenerationOutcome> generate(String text, {String? provider}) async {
    // `provider`はBackendへの接続がある場合のみ意味を持つ(このRepositoryは
    // HTTP通信を一切行わないため、常に無視する。FORGE-AI-CONNECT-001対応で
    // Interfaceへ追加されたが、Mock Mode自体の挙動は変えない)。
    ForgeLogger.start(_scope, 'generate() called (mock, no network)');
    ForgeLogger.request(_scope, 'building mock document for: "$text"');

    // FORGE-MILESTONE-002.1 Task 2: computationコールバックが無いFuture.delayed()は
    // 戻り値の型Tを推論する材料が無く、inference_failure_on_instance_creationになる。
    // 戻り値は使っていない(単なる待機)ため<void>が正しい型。
    await Future<void>.delayed(_artificialDelay);

    final document = _dataSource.generate(text);
    ForgeLogger.success(_scope, 'mock document ready');
    return GenerationSuccess(
      forgeDocument: document,
      diagnostics: const GenerationDiagnostics(
        engineUsed: 'forge_ai',
        providerUsed: 'mock',
        repairAttempts: 0,
      ),
    );
  }

  @override
  Future<GenerationOutcome> confirm({required String requestId, required String answer}) async {
    // Mock Modeでは`generate()`が確認要求を返すことが無いため、この経路は
    // 通常UIから呼ばれない。呼ばれた場合も安全にフォールバックできるよう、
    // 回答をそのまま新しい入力として再生成する(決定的、常に成功する)。
    ForgeLogger.start(_scope, 'confirm() called (mock, treated as a fresh generate)');
    return generate(answer);
  }
}
