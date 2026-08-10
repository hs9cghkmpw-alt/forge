/// FORGE v1.0(Workstream E: Validation Architecture)。
///
/// `schema_ref`から実際の[ForgeRecordSchema]を引く、小さな解決ロジック
/// (指示書の例に挙がった`ForgeRecordSchemaResolver`)。[ForgeStateStore]
/// (add/update/select)からも、Widget側の表示ロジックからも同じ経路で
/// 解決できるよう、1箇所へ集約した(重複防止)。
///
/// **現状規模に対して過剰な抽象化をしない**という指示書の方針に従い、
/// このクラスは1つの静的な解決メソッドのみを持つ(状態を持たない)。
library;

import '../schema/forge_document.dart';

class ForgeRecordSchemaResolver {
  const ForgeRecordSchemaResolver();

  /// `schemaRef`が`null`、または`recordSchemas`内に見つからない場合は
  /// `null`を返す(呼び出し側はLegacy挙動——schema無し、string中心——
  /// へフォールバックする、指示書Workstream C.5)。
  ForgeRecordSchema? resolve(Map<String, ForgeRecordSchema> recordSchemas, String? schemaRef) {
    if (schemaRef == null) return null;
    return recordSchemas[schemaRef];
  }
}
