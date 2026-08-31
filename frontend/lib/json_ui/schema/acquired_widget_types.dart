// 獲得した Capability の widget 型を、**Parser 側**が受け取れるようにする表。
//
// ## なぜ Registry だけでは足りないのか
//
// `ForgeWidgetNode.fromJson` の `switch` は出荷済み型の閉じた集合である。
// 未知の型はそこで `ForgeUnknownWidgetNode` へ倒れ、`buildForgeWidget` は
// Widget Registry を引く前に短絡する。したがって Registry へ登録しても
// **獲得 widget は描かれない**（TD93）。
//
// ここが Parser 側の受け口である。Self-Extension で獲得した能力の
// 生成コードが、自分で `register` して自分を載せる。
// **capability ごとの `if` 分岐を Forge 本体へ足さない**ための表である。
//
// ## 緩めない向き
//
// * 登録が無い型は従来どおり `ForgeUnknownWidgetNode`（既定は閉じている）
// * 出荷済み型は `switch` が先に一致するので、**この表では乗っ取れない**
// * 必須 property が欠けていれば出荷済み型と同じく **parse で落とす**
//   （黙って空の widget を描かない）

/// 獲得した widget 型の**宣言**。実際の描画は Widget Registry 側が持つ。
class ForgeAcquiredWidgetSpec {
  /// 文書に現れる `"type"`。
  final String typeName;

  /// 欠けていれば parse を失敗させる property 名。
  final List<String> requiredProperties;

  const ForgeAcquiredWidgetSpec({
    required this.typeName,
    this.requiredProperties = const <String>[],
  });
}

/// 獲得 widget 型の process-local な表。
class ForgeAcquiredWidgetTypeRegistry {
  final Map<String, ForgeAcquiredWidgetSpec> _specs = {};

  void register(ForgeAcquiredWidgetSpec spec) {
    if (spec.typeName.isEmpty) {
      throw ArgumentError('acquired widget type name must not be empty');
    }
    _specs[spec.typeName] = spec;
  }

  ForgeAcquiredWidgetSpec? specFor(String typeName) => _specs[typeName];

  Set<String> get registeredTypes => _specs.keys.toSet();

  void clear() => _specs.clear();
}

/// 既定では**空**。何も獲得していなければ何も通らない。
final ForgeAcquiredWidgetTypeRegistry forgeAcquiredWidgetTypes =
    ForgeAcquiredWidgetTypeRegistry();
