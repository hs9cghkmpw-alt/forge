# Forge Runtime Spec

`frontend/lib/json_ui/`配下のRuntime実装(Renderer・Widget Registry・状態管理)の
アーキテクチャをまとめる。FORGE-MILESTONE-002 PHASE2で、
「Widgetを追加する際の開発体験」を改善する再編を行った。

---

## ファイル構成と責務分離

```
json_ui/
├── schema/
│   └── forge_document.dart       # JSON→Dartモデル(sealed class階層、fromJson)
├── widget_registry/
│   ├── widget_registry_core.dart # Registry機構そのもの(type名→Widget解決)
│   ├── widget_registry.dart      # v1.0の6 Widget実装 + buildDefaultForgeRegistry()
│   └── widget_registry_v1_1.dart # v1.1の6 Widget実装 + registerV1_1Widgets()
└── renderer/
    ├── forge_renderer.dart       # 画面描画・画面遷移・エラー境界
    └── forge_runtime_state.dart  # AI生成アプリの動的状態(ChangeNotifier)
```

**PHASE2以前との違い**: 以前は`widget_registry.dart`1ファイルに
「Registry機構」と「Widget実装」が同居していた。Widgetが12種に増えるにあたり、
機構(`widget_registry_core.dart`)と実装(バージョンごとに分割)を分離した。

---

## 新しいWidgetを追加する手順(PHASE2の到達点)

1. `json_ui/schema/forge_document.dart`の`ForgeWidgetNode`(sealed class)へ、
   新しいWidgetノードクラスを追加する(同一ファイル内に置く必要がある。
   Dartのsealed classは同一ライブラリ内での定義を要求するため)。
   `ForgeWidgetNode.fromJson`のswitch文にもパース処理を追加する。
2. `widget_registry_core.dart`の`typeNameOf()`(switch式)へ、新しいノード型の
   ケースを追加する(sealed classの網羅性チェックにより、追加を怠ると
   コンパイルエラーになる想定。今回はDart SDKが無く実機確認できていない
   ため「想定」と明記する)。
3. 新しいWidget用の構築関数を、既存の`widget_registry.dart`/
   `widget_registry_v1_1.dart`とは別の新規ファイル(または既存の
   `widget_registry_v1_1.dart`)に追加する。シグネチャは`ForgeWidgetBuilder`
   ([BuildContext, ForgeWidgetNode, ForgeRuntimeState, 再帰用コールバック] →
   Widget)に従う。
4. その新規ファイルに、`ForgeWidgetRegistry`を受け取って`.register(typeName,
   builder)`を呼ぶ関数を1つ用意する。
5. `widget_registry.dart`の`buildDefaultForgeRegistry()`から、その関数を1行
   呼ぶ。

この手順により、既存Widget(v1.0・v1.1とも)の実装ファイルには一切触れずに
新Widgetを追加できる(「Registryだけ追加で済む」というPHASE2の目標)。

---

## 状態管理: なぜRiverpodではなく`ForgeRuntimeState`か

`docs/DECISIONS.md` D7を参照。要約: Riverpodのproviderはコンパイル時に
型・個数が決まっている前提の設計であり、「AIが実行時に決めたキー・型の集合」を
表現するのには向かない。Studioアプリ自体の状態(認証・生成リクエストの
成功/失敗等)はRiverpodのまま、AI生成アプリの内部状態(チェックリストの中身・
入力値等)は`ForgeRuntimeState`(ChangeNotifier)が担当する、という2層構成を
維持している。

---

## エラー境界の限界(TECH_DEBT.md TD11)

`buildForgeWidget()`のtry/catchは、Widget構築(build呼び出し)中の例外のみを
捕まえる。レイアウト/hit-test時の例外(FORGE-RUNTIME-003で実際に発生した種類)は
現状捕まえられない。個々のWidget実装を、実績のあるMaterial標準Widget
(IconButton・CheckboxListTile等)で組み立てることで間接的にリスクを下げている
(FORGE-RUNTIME-002/003・v1.1 Widget実装で一貫して採用している方針)。
