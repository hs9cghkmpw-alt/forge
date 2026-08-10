/// FORGE v0.2 P5対応(マイアプリ)。
///
/// 生成に成功し、ユーザーが保存した(「アプリを開く」または
/// 「保存してあとで見る」を選んだ)アプリ1件を表す。
class SavedForgeApp {
  final String id;
  final String title;
  final String originalPrompt;
  final Map<String, dynamic> forgeDocument;
  final DateTime createdAt;
  final DateTime updatedAt;
  final String providerUsed;
  final int? qualityScore;

  const SavedForgeApp({
    required this.id,
    required this.title,
    required this.originalPrompt,
    required this.forgeDocument,
    required this.createdAt,
    required this.updatedAt,
    required this.providerUsed,
    this.qualityScore,
  });

  Map<String, dynamic> toJson() => {
        'id': id,
        'title': title,
        'originalPrompt': originalPrompt,
        'forgeDocument': forgeDocument,
        'createdAt': createdAt.toIso8601String(),
        'updatedAt': updatedAt.toIso8601String(),
        'providerUsed': providerUsed,
        'qualityScore': qualityScore,
      };

  /// 破損したレコード(型が違う・必須フィールド欠如)は`null`を返す。
  /// 呼び出し側はこれを「隔離・無視」し、他のレコードの読み込みを止めない
  /// (指示書16.2節「JSON破損時に全体クラッシュしない」)。
  static SavedForgeApp? tryFromJson(Map<String, dynamic> json) {
    try {
      final id = json['id'] as String;
      final title = json['title'] as String;
      final originalPrompt = json['originalPrompt'] as String;
      final forgeDocument = (json['forgeDocument'] as Map).cast<String, dynamic>();
      final createdAt = DateTime.parse(json['createdAt'] as String);
      final updatedAt = DateTime.parse(json['updatedAt'] as String);
      final providerUsed = json['providerUsed'] as String? ?? 'unknown';
      final qualityScore = json['qualityScore'] as int?;
      return SavedForgeApp(
        id: id,
        title: title,
        originalPrompt: originalPrompt,
        forgeDocument: forgeDocument,
        createdAt: createdAt,
        updatedAt: updatedAt,
        providerUsed: providerUsed,
        qualityScore: qualityScore,
      );
    } catch (_) {
      return null;
    }
  }
}
