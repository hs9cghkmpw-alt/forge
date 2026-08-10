# Forge Runtime Contract v1.2 — State / Action / Validation / Navigation

FORGE-MILESTONE-003。Forge Language v1.2で追加したRuntime契約(状態管理・
Action処理・入力検証・画面遷移)の設計をまとめる。`docs/spec/LANGUAGE_SPEC.md`
(Widget定義)・`docs/spec/RUNTIME_SPEC.md`(Renderer API)を補完する位置づけ。

---

## 1. 依存方向

```
Widget Builder (json_ui/widget_registry/)
        ↓ 読み書きは ForgeRuntimeState 経由のみ
ForgeRuntimeState (json_ui/renderer/forge_runtime_state.dart)
        ↓ 実データはStoreへ委譲、Action処理はDispatcherへ委譲
ForgeStateStore / ForgeActionDispatcher / ForgeFormValidator (json_ui/runtime/)
        ↓ 知っているのはForgeStateValue/ForgeActionという型だけ
ForgeDocument Models (json_ui/schema/forge_document.dart)
```

`json_ui/runtime/`配下の3クラスは、特定のWidget名・画面名・生成テンプレートを
一切知らない。`ForgeActionDispatcher`の`screenLookup`は「idからWidgetNodeを
引く関数」という抽象化のみを受け取り、`submit_form`のform_ref解決以外の
用途では使われない。

---

## 2. State設計

### 2.1 型

`string` / `boolean` / `number`(v1.2新規) / `string_list` / `checklist` の5型。
Dartモデルは`ForgeStringState`/`ForgeBooleanState`/`ForgeNumberState`/
`ForgeStringListState`/`ForgeChecklistState`(いずれも`ForgeStateValue`のsealed
subtype)。

### 2.2 単一のState Store

[ForgeStateStore]が実データを保持する唯一の場所。汎用API(`read`/`write`/
`contains`)と、型別の便利メソッド(`toggleBoolean`/`reset`/
`addChecklistItem`等)の両方を提供する。

- `read(key) -> dynamic`: 型を問わない値の取得。
- `write(key, value) -> bool`: 既存の型と矛盾する値は書き込まず`false`を返す
  (型検証をここに集約し、Widget Builder側に個別の型チェックを書かせない)。
- `reset(key) -> bool`: **画面初期化時点**の値へ戻す(直近の値ではない)。
  State全体の一括resetは今回導入していない(指示書Task 3の指示通り、
  個別resetと明確に区別した)。

### 2.3 既存Widget BuilderのAPI互換性

[ForgeRuntimeState](`json_ui/renderer/forge_runtime_state.dart`)が、
FORGE-MERGE-001〜FORGE-MILESTONE-002で確立した既存API
(`getString`/`setString`/`getBoolean`/`getChecklist`等)をシグネチャ・挙動とも
維持したまま、内部実装だけを`ForgeStateStore`への委譲に置き換えた。既存の
Widget Builderコードは1行も変更せずに動作する。

---

## 3. Action設計

### 3.1 種別(9種、v1.0/v1.1の4種 + v1.2新規5種)

| Action | 導入 | 意味 |
|---|---|---|
| `navigate` | v1.0 | 指定screenへ画面遷移する |
| `go_back` | v1.0 | 前の画面へ戻る |
| `set_value` | v1.0 | 指定stateへ値を設定する(v1.0/v1.1互換のため維持) |
| `add_item` | v1.0 | checklistへ新規項目を追加する |
| `set_state` | v1.2 | `set_value`と同じ意味論。v1.2以降の正式名称 |
| `toggle_state` | v1.2 | boolean stateを反転する |
| `reset_state` | v1.2 | 指定stateを画面初期化時点の値へ戻す |
| `submit_form` | v1.2 | form_refが指すformを検証し、合格時のみsuccess_actionを実行する |
| `composite` | v1.2 | 複数Actionを順番に実行する(最大10件、ネスト最大3段) |

`set_value`と`set_state`は同じDartクラス(`SetValueAction`)へ写像している
(意味論が完全に同じ2つのクラスを作らない判断。`docs/DECISIONS.md`参照)。

### 3.2 Action Dispatcher

[ForgeActionDispatcher.execute()]が全Actionの唯一の入口。Widget Builderは
`if (action.type == 'navigate') { ... } else if (...)`のような分岐を一切書かない
(`state.dispatch(action)`または`ForgeActionDispatcher.execute(action)`を呼ぶだけ)。

戻り値は[ActionResult](`success`/`reason`/`validationErrors`)。呼び出し元が
成功・失敗を判定できる。

### 3.3 composite

- 最大10 Action、ネスト最大3段(`maxCompositeDepth`)。schema側でも
  `maxItems: 10`を強制しているが、ネスト段数はJSON Schemaの`$ref`再帰だけでは
  上限を表現できないため、Validator・Runtimeの両方で手続き的に検証している。
- 途中のstepが失敗すると、**それ以降のstepは実行しない**(ロールバックはしない。
  失敗より前のstepの結果はそのまま残る)。

### 3.4 診断ログ

[ForgeDiagnosticSink]経由で、未知Action・不正なstate_ref・型不一致・
存在しないscreen target・Validation定義エラー・composite途中失敗・再帰深度超過・
Fallback発生を記録する。development/testでは`ForgeLogger`(既存、
`core/utils/forge_logger.dart`)経由でconsoleへ出力し、production相当では
出力しない(`kDebugMode`ガード。既存のFallback方針と同じ考え方)。

---

## 4. Validation設計

### 4.1 ルール種別

`required` / `min_length` / `max_length` / `min` / `max` / `pattern` の6種。
`email`/`integer`/`non_empty_list`は「余裕があれば」の対象だったが、今回は
6種の基本ルールに絞った(指示書「必要以上の機能追加は禁止」に従った判断)。

### 4.2 JSON上の位置

`text_field`・`checkbox`へ任意の`validation: { rules: [...] }`プロパティとして
付与する。1ルールにつき`type`・`value`(ルールによっては省略可、例:
`required`)・`message`を持つ。

### 4.3 検証の流れ

1. `form`の送信ボタンは、常に`SubmitFormAction(formRef: 自分自身のid,
   successAction: JSON上のsubmit_action)`をdispatchする(JSON上の
   submit_actionを直接dispatchしない、という変更がMILESTONE-003の核心)。
2. [ForgeActionDispatcher]がform_refからformノードを特定し、子孫の
   text_field/checkboxのうち`validation`を持つものを集める。
3. [ForgeFormValidator.validate()]が各フィールドの現在値をStoreから読み、
   ルールを順に評価する。最初に失敗したルールのmessageを採用する。
4. 1件でも失敗すれば、success_actionは実行されず、エラーが
   `ForgeRuntimeState`(`getValidationError(stateRef)`)経由でWidget Builderへ
   伝わる。text_fieldは`InputDecoration.errorText`、checkboxは
   `CheckboxListTile.subtitle`でエラーメッセージを表示する。

### 4.4 安全性

- 不正なValidation定義(不正な正規表現等)はクラッシュせず、そのルールを
  無視する(Validator側でも事前に正規表現の妥当性を検証しているため、
  基本的にはServer側で弾かれるはずだが、Runtime側でも多重防御している)。
- State型に適用できないルール(例: booleanへの`min_length`)は、Validatorが
  警告(`severity: warning`)として記録し、ブロッキングエラーにはしない。
  Runtime側の[ForgeFormValidator]も、型が合わないルールは黙って合格扱いにする
  (安全側に倒す)。

---

## 5. Navigation設計

- `navigate`/`go_back`は[ForgeActionDispatcher]から`onNavigationAction`
  コールバックへ委譲され、実際の`Navigator.push`/`maybePop`は
  `forge_renderer.dart`の`_ForgeScreenViewState`が担う(Dispatcher自体は
  `BuildContext`を持たない)。
- 存在しないscreen targetへのnavigateは、Validatorが事前に弾くはずだが、
  Runtime側でも`ScaffoldMessenger`のSnackBarで通知し、クラッシュしない。
- **無限遷移防止**: `ForgeScreenView`に`navigationDepth`(現在何画面目か)を持たせ、
  `MAX_SCREENS`(20)を超えて遷移しようとした場合は、それ以上のnavigateを
  拒否しSnackBarで知らせる。JSON Widgetツリー自体はループを構造上作れないが
  (親子関係のみ、循環不可)、composite/navigateの組み合わせで実質的な
  無限遷移が起こりうるケースへの多重防御。

---

## 6. 既存機能との後方互換性

- v1.0/v1.1のみを使う文書は、Validator・Runtimeとも無改変のまま合格・動作する
  (既存135件→167件のPythonテスト、既存95件のDartテストで確認)。
- `form`ウィジェットに`validation`を一切付けない場合、送信は常に成功する
  (検証対象フィールドが0件のため)。既存のMock生成コンテンツ(Checklist/
  Memo)は`form`自体を使わないため無影響。
