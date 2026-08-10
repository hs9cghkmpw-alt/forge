import '../entities/generation_outcome.dart';

/// Backend呼び出し・JSON解析等、外部技術への依存を一切持たない契約(interface)。
/// 実装は data/repositories/ に置く
/// (frontend/lib/core/README.md・_template_feature/README.md の依存ルールに従う)。
///
/// FORGE v0.2 P0.1・P0.2対応: 以前は`Future<Map<String, dynamic>>`
/// (成功時のdocumentのみ)を返し、確認要求(needs_confirmation)を
/// 一切表現できなかった。`GenerationOutcome`(Success/NeedsConfirmation/
/// Failure)を返す形へ変更し、`confirm()`を新設した。
abstract class AppGenerationRepository {
  /// ユーザーの自然言語入力から、生成結果を1件取得する。
  /// パース(`ForgeDocument.fromJson`)はこの層の責務ではない
  /// (json_ui/ 側、実際に描画する直前で行う)。
  Future<GenerationOutcome> generate(String text);

  /// `GenerationNeedsConfirmation.requestId`と、ユーザーの回答を渡し、
  /// 確認を経て生成を再実行する。
  Future<GenerationOutcome> confirm({required String requestId, required String answer});
}

/// 生成失敗(通信エラー等、Backendが応答すら返せなかった場合)を表す。
///
/// FORGE v0.2対応: Backendが実際に応答したエラー(Validator不合格・
/// Provider障害等)は`GenerationFailure`(`GenerationOutcome`の一種)で
/// 表現するようになった。この例外は、通信自体が失敗した場合
/// (サーバーに到達できない、レスポンスが壊れている等)専用に残す。
class AppGenerationException implements Exception {
  final String code;
  final String message;
  const AppGenerationException({required this.code, required this.message});

  @override
  String toString() => 'AppGenerationException($code): $message';
}
