// 獲得した Capability が、**Forge 本体の Flutter アプリへ載る**ための口（TD94）。
//
// ## 何が足りなかったか
//
// 020F で Parser 側の受け口（`forgeAcquiredWidgetTypes`）と
// Widget Registry の解決は開いた。しかし**生成された Dart が
// Forge アプリのビルド対象へ入る経路**が無かったので、
// 獲得能力は隔離 workspace の中で終わっていた。
//
// ここがその着地点である。生成された binding は
// `ForgeAcquiredCapability` を1つ公開し、生成された登録表
// （`acquired_registrations.g.dart`）がそれを登録する。
//
// ## 緩めない向き
//
// * 既定は**空**。何も獲得していなければ何も登録されない
// * 1つの Capability は Parser 側の宣言と描き方を**両方**持つ。
//   片方だけの `ForgeAcquiredCapability` は型として作れない
// * 出荷済み widget 型は乗っ取れない（Parser の `switch` が先に一致する）
// * `capabilityId` が違う同じ widget 型を後から上書きできない——
//   静かに別物へ差し替わるのを防ぐ

import '../schema/acquired_widget_types.dart';
import '../widget_registry/widget_registry_core.dart';

/// 獲得した Capability 1つ分。**宣言と描き方は分けて持てない。**
class ForgeAcquiredCapability {
  /// どの能力か（`view.calendar` のような Canonical Catalog の id）。
  final String capabilityId;

  /// Parser 側の宣言（widget 型と必須 property）。
  final ForgeAcquiredWidgetSpec spec;

  /// 実際の描き方。
  final ForgeWidgetBuilder build;

  const ForgeAcquiredCapability({
    required this.capabilityId,
    required this.spec,
    required this.build,
  });
}

/// 型名 → 描き方。`buildDefaultForgeRegistry()` がここから移す。
///
/// Registry は呼ぶたびに作り直されるので、獲得能力は**表**に載せて
/// おき、Registry を組むときに毎回入れ直す。
final Map<String, ForgeWidgetBuilder> forgeAcquiredWidgetBuilders =
    <String, ForgeWidgetBuilder>{};

/// 型名 → その型を持ち込んだ能力の id。取り違えを検出するためだけに持つ。
final Map<String, String> forgeAcquiredWidgetOwners = <String, String>{};

/// 獲得能力を1つ登録する。生成された登録表から呼ばれる。
void registerAcquiredCapability(ForgeAcquiredCapability capability) {
  final typeName = capability.spec.typeName;
  final owner = forgeAcquiredWidgetOwners[typeName];
  if (owner != null && owner != capability.capabilityId) {
    // **静かに差し替えない。** 同じ widget 型を別の能力が奪うのは事故である。
    throw StateError(
      "widget type '$typeName' is already provided by '$owner';"
      " '${capability.capabilityId}' cannot take it over",
    );
  }
  forgeAcquiredWidgetTypes.register(capability.spec);
  forgeAcquiredWidgetBuilders[typeName] = capability.build;
  forgeAcquiredWidgetOwners[typeName] = capability.capabilityId;
}

/// テスト用の巻き戻し。**本番経路は使わない。**
void clearAcquiredCapabilities() {
  forgeAcquiredWidgetTypes.clear();
  forgeAcquiredWidgetBuilders.clear();
  forgeAcquiredWidgetOwners.clear();
}
