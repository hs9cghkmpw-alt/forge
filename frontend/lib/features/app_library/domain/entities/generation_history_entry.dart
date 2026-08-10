/// FORGE v0.2 P5対応(履歴)。
///
/// 生成操作1回分の記録(成功・確認中断・失敗のいずれか)。
enum GenerationHistoryStatus { success, needsConfirmation, failure }

class GenerationHistoryEntry {
  final String id;
  final String prompt;
  final GenerationHistoryStatus status;
  final DateTime createdAt;
  final String? appId; // status == success の場合、対応するSavedForgeApp.id
  final String? errorCategory; // status == failure の場合

  const GenerationHistoryEntry({
    required this.id,
    required this.prompt,
    required this.status,
    required this.createdAt,
    this.appId,
    this.errorCategory,
  });

  Map<String, dynamic> toJson() => {
        'id': id,
        'prompt': prompt,
        'status': status.name,
        'createdAt': createdAt.toIso8601String(),
        'appId': appId,
        'errorCategory': errorCategory,
      };

  /// `SavedForgeApp.tryFromJson`と同じ方針: 破損レコードは`null`を返す。
  static GenerationHistoryEntry? tryFromJson(Map<String, dynamic> json) {
    try {
      final id = json['id'] as String;
      final prompt = json['prompt'] as String;
      final statusName = json['status'] as String;
      final status = GenerationHistoryStatus.values.firstWhere(
        (s) => s.name == statusName,
        orElse: () => GenerationHistoryStatus.failure,
      );
      final createdAt = DateTime.parse(json['createdAt'] as String);
      return GenerationHistoryEntry(
        id: id,
        prompt: prompt,
        status: status,
        createdAt: createdAt,
        appId: json['appId'] as String?,
        errorCategory: json['errorCategory'] as String?,
      );
    } catch (_) {
      return null;
    }
  }
}
