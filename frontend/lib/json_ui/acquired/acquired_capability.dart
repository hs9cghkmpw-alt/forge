// 獲得した Capability が、**Forge 本体の Flutter アプリへ載る**ための口（TD94）。
//
// ## 生成コードへ ForgeRuntimeState を直接渡さない
//
// BUILD_TIME の生成 binding は信用境界の外側にある。以前は
// `ForgeWidgetBuilder` をそのまま公開していたため、表示専用 Capability にも
// `ForgeRuntimeState`（write/dispatch/export 等を持つ内部状態）を丸ごと渡していた。
// Sandbox の import allow-list を厳しくしても、引数として実体を渡せば dynamic
// 経由で内部 API を呼べる。そこで獲得 Capability 専用の**読取専用 Adapter**を
// このファイルで定義し、Registry との境界で内部 State を包む。
//
// 生成 binding が触れてよい Host API は、このファイルと
// `acquired_widget_types.dart` に明示されたものだけである。書き込みや Action が
// 必要な Capability は、将来 Permission Manifest（権限宣言）付きの別 API として
// 追加する。表示 Capability に権限を先渡ししない。

import 'package:flutter/widgets.dart';

import '../renderer/forge_runtime_state.dart';
import '../schema/acquired_widget_types.dart';
import '../schema/forge_document.dart';
import '../widget_registry/widget_registry_core.dart';

/// 生成 binding が使う Widget node の公開名。
///
/// underlying type を直接 import させず、Host API の入口をこの library に固定する。
typedef ForgeAcquiredNode = ForgeAcquiredWidgetNode;

/// 子 Widget を Forge 本体の Renderer へ戻すための関数。
typedef ForgeAcquiredChildBuilder = Widget Function(ForgeWidgetNode child);

/// 生成 Capability に渡す Record の read-only view。
///
/// `fields` はコピーして unmodifiable にする。生成 Widget が受け取った Map を
/// 書き換えて Runtime State へ副作用を起こす経路を残さない。
class ForgeAcquiredRecordView {
  final String id;
  final Map<String, dynamic> fields;

  ForgeAcquiredRecordView._(ForgeRecordItem record)
      : id = record.id,
        fields = Map<String, dynamic>.unmodifiable(record.fields);
}

/// BUILD_TIME で獲得した**表示 Capability**へ渡す最小の状態 API。
///
/// 書き込み、Action dispatch、永続化 export、内部 Store への参照は公開しない。
/// 読取 API を増やすときは「生成表示 Capability に本当に必要か」を個別に判断する。
class ForgeAcquiredRuntimeReader {
  final ForgeRuntimeState _state;

  ForgeAcquiredRuntimeReader._(this._state);

  String getString(String key) => _state.getString(key);

  bool getBoolean(String key) => _state.getBoolean(key);

  double getNumber(String key) => _state.getNumber(key);

  List<String> getStringList(String key) =>
      List<String>.unmodifiable(_state.getStringList(key));

  List<ForgeAcquiredRecordView> getRecordList(String key) =>
      List<ForgeAcquiredRecordView>.unmodifiable(
        _state.getRecordList(key).map(ForgeAcquiredRecordView._),
      );

  bool contains(String key) => _state.contains(key);
}

/// 獲得した表示 Capability の Builder。
///
/// 通常の `ForgeWidgetBuilder` と違い、第三引数は read-only Adapter である。
typedef ForgeAcquiredWidgetBuilder = Widget Function(
  BuildContext context,
  ForgeAcquiredNode node,
  ForgeAcquiredRuntimeReader state,
  ForgeAcquiredChildBuilder build,
);

/// 獲得した Capability 1つ分。**宣言と描き方は分けて持てない。**
class ForgeAcquiredCapability {
  /// どの能力か（`view.calendar` のような Canonical Catalog の id）。
  final String capabilityId;

  /// Parser 側の宣言（widget 型と必須 property）。
  final ForgeAcquiredWidgetSpec spec;

  /// 実際の描き方。生成コードへ内部 Runtime State は渡さない。
  final ForgeAcquiredWidgetBuilder build;

  const ForgeAcquiredCapability({
    required this.capabilityId,
    required this.spec,
    required this.build,
  });
}

/// 型名 → 描き方。`buildDefaultForgeRegistry()` がここから移す。
///
/// Registry 自身は既存の `ForgeWidgetBuilder` を保持するが、登録時に Host 側で
/// read-only Adapter を挟む。生成コードへ `ForgeRuntimeState` を直接渡さない。
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
  forgeAcquiredWidgetBuilders[typeName] = (
    BuildContext context,
    ForgeWidgetNode node,
    ForgeRuntimeState state,
    Widget Function(ForgeWidgetNode child) recurse,
  ) {
    if (node is! ForgeAcquiredWidgetNode) {
      throw StateError(
        "acquired widget '$typeName' received a non-acquired node: ${node.runtimeType}",
      );
    }
    return capability.build(
      context,
      node,
      ForgeAcquiredRuntimeReader._(state),
      recurse,
    );
  };
  forgeAcquiredWidgetOwners[typeName] = capability.capabilityId;
}

/// テスト用の巻き戻し。**本番経路は使わない。**
void clearAcquiredCapabilities() {
  forgeAcquiredWidgetTypes.clear();
  forgeAcquiredWidgetBuilders.clear();
  forgeAcquiredWidgetOwners.clear();
}
