# Renderer API Inventory

FORGE-MERGE-002 Task 3。`frontend/lib/json_ui/` の公開API一覧と互換性ポリシー。
実装(`forge_document.dart`・`widget_registry.dart`・`forge_renderer.dart`・
`forge_runtime_state.dart`)を実際に読んで作成した。**Dart SDKが無い環境で作成しているため、
ここに書かれたシグネチャは`flutter analyze`で最終確認されていない**(Test Report参照)。

---

## 0. 依頼された6概念と、実際の実装の対応

依頼書はRegistry / Renderer / RenderContext / RenderNode / Widget Factory / Widget Mapper
の6つを最低対象としていたが、現在の実装はこれをそのまま6クラスとしては実装していない。
対応関係を偽らず、そのまま示す。

| 依頼書の概念 | 現在の実装での対応 | 一致度 |
|---|---|---|
| Registry | `ForgeWidgetRegistry` | 一致 |
| Renderer | `buildForgeWidget()`(関数)+ `ForgeScreenView`(Widget) | 一致(ただし1クラスでなく関数+Widgetの組) |
| RenderNode | `ForgeWidgetNode`(sealed class、7派生型) | 一致(名前はNodeでなくWidgetNode) |
| RenderContext | **存在しない** | 不一致(1章で詳述) |
| Widget Factory | **独立クラスとして存在しない**。`ForgeWidgetRegistry`の`_builders`に登録された関数群が実質的にその役割を担う | 不一致 |
| Widget Mapper | **独立クラスとして存在しない**。`widget_registry.dart`内の`_typeNameOf()`(private関数)が型→文字列の変換を担う | 不一致 |

### 1. RenderContextが存在しない理由と現状

`buildForgeWidget()`は`BuildContext`・`ForgeRuntimeState`・`ForgeWidgetRegistry`・
再帰用コールバックを個別の引数として渡している。これらを1つの`RenderContext`
オブジェクトへまとめていない。

現段階でこれを問題とは判断していない(引数4つは可読性を損なう水準ではない)が、
将来Widgetの種類が増え、渡すべき文脈(例: テーマ上書き・Plugin解決器・
デバッグフラグ)が増えた場合は、`RenderContext`クラスを導入して引数を集約する
ことを推奨する。これは今回の「禁止事項: リファクタリングのみを目的とした
大規模変更」に該当するため、今回は実施しない(6章 Runtime Architecture Review
でも同じ結論)。

### 2. Widget Factory / Widget Mapperが独立クラスでない理由

`ForgeWidgetRegistry`が「type文字列→構築関数」の解決を担い、構築関数自体が
そのままFlutter Widgetを組み立てている。「解決(Mapper/Registry)」と
「組み立て(Factory)」を分離するほどの複雑さが現状の6 Widget種には無い
と判断し、統合したままにしている。将来Widgetごとの構築が複雑化した場合
(例: 非同期初期化を伴うWidget)に分離を検討する。

---

## 3. API一覧

### 3.1 Public(他モジュール・featureから利用される)

| API | 種別 | シグネチャ概要 | 用途 |
|---|---|---|---|
| `ForgeDocument` | class | `fromJson(Map)`, `screenById(String)`, fields: `version`/`appTitle`/`initialScreenId`/`screens` | 文書全体のモデル |
| `ForgeScreen` | class | `fromJson(Map, String)`, fields: `id`/`title`/`state`/`body` | 1画面のモデル |
| `ForgeStateValue` | sealed class | (基底) | State値の型安全な表現 |
| `ForgeStringState`/`ForgeBooleanState`/`ForgeStringListState`/`ForgeChecklistState` | class | `value`フィールドのみ | State値4種の実装 |
| `ForgeChecklistItem` | class | `id`/`text`/`done`, `copyWith()` | チェックリスト項目 |
| `ForgeWidgetNode` | sealed class | `fromJson(Map, String)`(factory) | Widgetノードの基底 |
| `ForgeTextWidgetNode`〜`ForgeUnknownWidgetNode` | class | 型ごとのフィールド | Widget種別7種の実装 |
| `ForgeAction` | sealed class | `fromJson(Map, String)`(factory) | Actionの基底 |
| `NavigateAction`/`GoBackAction`/`SetValueAction`/`AddItemAction` | class | 型ごとのフィールド | Action種別4種の実装 |
| `ForgeParseException` | class(Exception) | `path`/`message` | パース失敗の例外 |
| `ForgeWidgetRegistry` | class | `register()`, `resolve()`, `withBuiltins()`(static) | Widget解決の辞書 |
| `ForgeWidgetBuilder` | typedef | `Widget Function(BuildContext, ForgeWidgetNode, ForgeRuntimeState, Widget Function(ForgeWidgetNode))` | 構築関数の型 |
| `buildForgeWidget()` | top-level function | 上記引数を取りWidgetを返す | Renderer本体の入口 |
| `ForgeFallbackWidget` | class(StatelessWidget) | `reason`必須 | 安全なFallback表示 |
| `ForgeRuntimeState` | class(ChangeNotifier) | 4章参照 | 実行時状態コンテナ |
| `ForgeDocumentView` | class(StatelessWidget) | `rawJson`必須 | Runtimeの最上位エントリポイント |
| `ForgeScreenView` | class(StatefulWidget) | `document`/`screen`必須 | 1画面の描画 |

### 3.2 Internal(`_`接頭辞、モジュール外から参照不可)

`_typeNameOf()` / `_buildText()`〜`_buildChecklist()`(6個の組み込みビルダー) /
`_BoundTextField`・`_BoundTextFieldState` / `_ForgeScreenViewState` /
`_ForgeRenderErrorScreen`

### 3.3 Experimental(Publicだが、形が変わる可能性が高いと明示するもの)

- `ForgeRuntimeState.toggleChecklistItem()` / `.deleteChecklistItem()` / `.addChecklistItem()` —
  現状checklist専用の操作がRuntimeStateに直接生えている。将来checklist以外の
  ステートフルWidget(例: スライダー、日付選択)が増えた場合、同じパターンで
  メソッドを追加し続けるとRuntimeStateが肥大化する。Widget種別ごとの操作を
  切り出す設計(例: 各Widget種別が自分の操作セットを持つ)への移行を検討する
  余地があるとマークしておく。破壊的変更の可能性がある。

---

## 4. Public APIの互換性ポリシー

1. **フィールド追加は互換**。既存Publicクラスへの新規オプショナルフィールド追加は
   互換性を壊さない(sealed classのため、新しい**派生型**の追加は非網羅switchの
   コンパイルエラーを呼び出し側に強制する点に注意。これは意図的な安全装置であり、
   互換性違反ではなく「対応漏れの検出」として扱う)。
2. **メソッドシグネチャの変更・削除は破壊的変更**。`docs/spec/LANGUAGE_FREEZE.md`の
   Breaking Change基準に準じ、Runtime側でも同様に扱う。
3. **`Experimental`マークされたAPIは、いつでも変更されうる**。呼び出し側
   (features/配下)からの利用は許容するが、変更時の事前告知は保証しない。
4. **Internal(`_`接頭辞)APIへの依存は禁止**。`features/`配下は本一覧のPublic APIのみを
   参照すること(現状違反は無い。`app_generation/`は`ForgeDocumentView`のみを利用)。
5. Public API変更はすべて`docs/DECISIONS.md`に記録すること。
