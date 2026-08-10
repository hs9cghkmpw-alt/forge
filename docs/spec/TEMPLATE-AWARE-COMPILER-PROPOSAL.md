# Template-aware Compiler — Architecture Proposal (Stage 1)

**対象:** `forge_ai/core/compiler.py`のみ(指示書「Compilerのみを責務として改善」に準拠)
**PromptPipeline・DomainClassifier・Planner・Critic等は無変更**

---

## 1. 現状

`Compiler.compile(plan: ApplicationPlan)`は、`TemplateSelection`(既に
`Planner`が計算しているが、Compilerには一度も渡されていない)を無視し、
**常に単一のChecklist画面**を生成する。`ScreenPlan.key_elements`の
各要素を、Checklistの別々の行として並べているだけ(例:
`item/price/quantity/store`が4行になる)。

## 2. 調査で判明したRuntime制約(重要、設計の前提)

実装に入る前に、Flutter Runtimeが実際に対応しているWidget/Action/
State型を`shared/schemas/ui_schema.v1.2.json`と
`frontend/lib/json_ui/`のRenderer実装で確認した。

| 要素 | 対応状況 |
|---|---|
| `form` Widget | ○ 複数の子Widget + submit_action(実装済み、`buildForm`) |
| `list` Widget | ○ `string_list`型のstateを描画(実装済み、`buildList`) |
| `text_field` Widget | ○ `validation`(min/max/pattern等)対応 |
| `add_item` Action | **`checklist`型のstateにのみ対応**(`store.addChecklistItem()`が固定実装)。`string_list`への追加は非対応 |
| `set_value`/`set_state` Action | 値は**静的なJSONリテラルのみ**。他のstateを参照して動的に合成する式・テンプレート機能は無い |
| 「1件の記録が複数フィールドを持つ」ためのstate型 | **存在しない**。`state_checklist`は`{id, text, done}`の3フィールド固定で、`text`は単一の自由記述文字列のみ |

**結論**: 「魚種・サイズ・重量・場所」を1件の記録として個別フィールドで
保持したまま一覧表示する、という指示書の理想形は、**現在のForge
Language Schema/Runtimeでは実現できない**(`add_item`が`checklist`
限定・動的な値合成機能が無いため)。この制約はCompilerの実装方法を
変えても解消しない、Schema/Runtime側の制約である。

**追記(実装中に発見、この提案書を実装完了後に更新)**: 当初この提案書
では「一覧画面」「入力フォーム画面」の2画面構成を想定していたが、
実装後に実際の`schema_validator.py`(Backendの実物)へ通したところ、
`state_reference_exists`エラーで不合格になった。原因を調査したところ、
**Forge Languageのstateは画面ごとにスコープされ、他画面のstateを
参照するActionは存在しない**ことが判明した(2画面設計では、入力
フォーム画面のsubmit_actionが、一覧画面のみに存在する`records`
stateへ`add_item`しようとしており、これがValidatorの検証対象外
だった)。この制約により、以下のStage1設計を**単一画面**へ修正した。

## 3. 提案: 2段階move

### Stage 1(今回実施、Compilerのみ、Schema/Runtime変更なし)

現実的にできる最大限の改善として、以下を提案する。

1. **Domain Data Model定義**を新設(`forge_ai/core/planning/domain_data_models.py`)。
   Domain category(文字列)→フィールド定義のリスト(`field_name`,
   `display_label`, `input_kind`: text/numeric_text)。指示書の3例
   (FishRecord・Transaction・Habit)をこの形で定義する。
2. Compilerを**Data Model定義を持つDomainのみ**、新しい構成
   (入力フォーム+一覧を**同一画面内**に配置)へ切り替える。**Data
   Model未定義のDomain(既存6例: shopping/task_management/diary/
   survey/schedule/inventory)は、従来通りのChecklist単一画面のまま**
   とする(指示書「段階的に移行」に対応、既存の254件のテストへの
   影響ゼロ)。
3. 新しい画面構成の詳細:
   - **同一画面内**に、上から順に「入力フォーム」→区切り線→
     「一覧」を配置する(前述の追記の通り、画面をまたぐstate参照が
     できないため、2画面ではなく1画面にまとめる)。
   - **一覧部分**: 既存の`checklist` Widget(`checklist`型state)を
     そのまま流用する(`list`Widget/`string_list`は`add_item`非対応
     のため使わない)。各行は「主要フィールド」(例: FishRecordなら
     魚種)のみを表示する(2章の制約により、複数フィールドを1行に
     構造化して出せないため)。
   - **入力フォーム部分**: `form` Widget。Data Modelの全フィールド分
     `text_field`を生成する(例: FishRecordなら魚種・サイズ・重量・
     場所の4つ)。数値系フィールド(サイズ・重量・金額等)には
     `pattern`バリデーション(数字のみ)を付与する。
   - **既知の制限(2章の制約により生じる、正直な申告)**: フォームで
     入力した「主要フィールド以外」(サイズ・重量・場所等)は、
     Validation(必須入力チェック)は効くが、**一覧には表示され
     ない**(保存先が無いため)。この制限はREADME・レポートへ明記し、
     Stage 2で解消する。
   - フォーム送信成功時: 主要フィールドの値をchecklistへ追加し、
     全フィールドを初期値へリセットする(`composite`+`reset_state`)。
     同一画面内のため、画面遷移(`navigate`)は不要。

### Stage 2(将来、今回のスコープ外、Schema/Runtime変更が必要)

- 新しいState型(例: `record_list`: 型付きフィールドを持つ複数
  レコードのリスト)をSchemaへ追加。
- 新しいAction型(例: `add_record`: 複数のsource stateを1レコードへ
  合成してrecord_listへ追加)をSchema/Runtimeへ追加。
- 一覧画面のWidgetを、複数フィールドを1行に表示できる形(例:
  `card`ベースの詳細行)へ拡張。
- この工程はCompiler単体では完結せず、Schema変更+Flutter Runtime
  実装+Backendの3者が揃って初めて実現できるため、別フェーズとして
  切り出すことを提案する。

## 4. Stage1のCompiler内部設計

```python
@dataclass(frozen=True)
class DomainField:
    name: str            # 例: "species"
    display_label: str   # 例: "魚種"
    is_numeric: bool = False
    required: bool = True

@dataclass(frozen=True)
class DomainDataModel:
    entity_name: str            # 例: "FishRecord"
    primary_field: str          # 一覧表示に使う代表フィールド名
    fields: tuple[DomainField, ...]

_DOMAIN_DATA_MODELS: dict[str, DomainDataModel] = {
    "fishing_log": DomainDataModel(
        entity_name="FishRecord", primary_field="species",
        fields=(
            DomainField("species", "魚種"),
            DomainField("size", "サイズ", is_numeric=True, required=False),
            DomainField("weight", "重量", is_numeric=True, required=False),
            DomainField("location", "場所", required=False),
        ),
    ),
    "household_budget": DomainDataModel(
        entity_name="Transaction", primary_field="category",
        fields=(
            DomainField("amount", "金額", is_numeric=True),
            DomainField("category", "カテゴリ"),
            DomainField("payment_method", "支払方法", required=False),
        ),
    ),
    "habit_tracking": DomainDataModel(
        entity_name="Habit", primary_field="name",
        fields=(
            DomainField("name", "名称"),
            DomainField("goal", "目標", required=False),
        ),
    ),
}
```

`Compiler.compile()`は、`plan`のDomain(`ApplicationPlan`自体は
Domainを持たないため、Compilerが逆引きするのではなく、呼び出し元
(`forge_ai/core/orchestration/pipeline_orchestrator.py`の
Compiler呼び出し箇所)から`domain_category`を明示的に渡す形にした)
を見て、登録されている場合は新しい(単一画面・フォーム+一覧)ロジック
へ、無ければ既存Checklistロジックへ分岐する。

**「写真」フィールドについて**: 指示書のFishRecord例に「写真」が
含まれるが、Forge Runtimeには画像アップロード用のWidgetが存在しない
(2章)。Stage1では写真フィールドを除外する(過去のセッションで
"photo"概念が原因の別バグを発見・修正した経緯があり、同じ理由で
慎重を期す)。

## 5. 影響範囲

- 主な変更: `forge_ai/core/compiler.py`(実際のテンプレート生成
  ロジックは全てここに閉じている)。
- 最小限の付随変更: `forge_ai/core/orchestration/pipeline_
  orchestrator.py`のCompiler呼び出し箇所(1行、`domain_category`を
  渡すだけ)と、`forge_ai/contracts/interfaces.py`の
  `CompilerProtocol`(型定義の追従)。ロジックの変更は無く、
  Compilerが必要とする追加情報を渡すための配線のみ。
- `PromptPipeline`・`DomainClassifier`・`Planner`・`Critic`・
  `EscalationHandler`自体の判定/生成ロジックは無変更(指示書の制約を
  遵守)。
- 既存6 Domain(shopping等)の出力は完全に不変(`domain_category`が
  未登録の場合は既存Checklistロジックへそのままフォールバックする
  設計、既存254件のテストに影響を与えない)。
