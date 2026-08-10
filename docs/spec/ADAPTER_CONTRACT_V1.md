# FORGE-MILESTONE-005 — Backend AI Integration: Adapter Contract (ADR)

**Status: ARCHITECTURE DESIGN — 実装未着手**
**Ref:** FORGE-MILESTONE-005(M004↔M005 Adapter Contract)
**日付:** 2026-07-14(v1.1、CEO実コード監査により改訂)
**担当:** Principal Engineer / Architect（Claude）

本ドキュメントは設計のみであり、コードは1行も追加していない。
`forge_ai/`(M004)・`backend/app/ai/runtime/`(M005)・
`backend/app/ai/foundation/`・Flutter・Backend本体のいずれも変更していない。
実装は次マイルストーン(M005 Implementation)で開始する。

## 改訂履歴(v1.0 → v1.1)

CEOがv1.0を実コードと突き合わせて監査した結果、**型境界とパイプライン
責務の2点でFAIL判定**を受けた。以下6点を修正した(詳細は各該当節)。

| # | 指摘 | 判定 | 修正箇所 |
|---|---|---|---|
| 1 | `forge_ai.Compiler.compile()`は`ApplicationPlan`しか受け取れず、`PlanIR`を渡すv1.0の設計は型エラーになる | **FAIL** | 1章・2章・7章: 粗粒度Facade(`run_pipeline()`)方式へ全面変更 |
| 2 | M004(`run_pipeline()`)とM005(`PromptPipeline`)の両方がオーケストレーションを持ち、責務が重複する | **FAIL** | 1章・8章: パイプライン所有者をM004に一本化 |
| 3 | 「dict[str, Any]だから共通形式」は契約として不十分(任意のdictが該当してしまう) | NEEDS CORRECTION | 2.3節: Validator合格を境界条件として明記 |
| 4 | `actions_needed=()`固定で`Intent.required_actions`の情報が失われる | (次点) | 2.2節: 未割当Actionの保持方針を追加 |
| 5 | `key_elements`を無条件で`data_needed`に写すと、UI概念をデータ要件と誤認する | (次点) | 2.2節: 3分類方針を追加 |
| 6a | HTTP `provider: "forge_ai"`はCognitive Engine名とProvider名を混同する | CONDITIONAL | 5章: `engine`/`provider`を分離、既定値を`mock`へ変更 |
| 6b | 400/422の使い分けが不統一 | CONDITIONAL | 3章・5章: 明確な基準へ統一 |

**v1.0で承認された部分(変更していない)**: Validator配置(Repair前後・
Critic直前必須)、Repairリトライ制御のM005一元化、Providerエラー分類、
APIキー非露出方針、HTTP契約とForge Languageバージョンの分離。

---

## 0. 前提とする既存事実(今回の設計の根拠)

以下は今回、実際にソースコードを再確認して得た事実である(推測ではない)。

- M004(`forge_ai/`)は80テスト全合格、Backend/Runtime/実LLMへの依存が無い
  スタンドアロンなCognitive Engine。
- M005(`backend/app/ai/runtime/`)は`backend/app/ai/foundation/`の型
  (`IntentIR`・`PlanIR`・`CriticResult`・`LLMAdapter`等)を再利用しており、
  M004への実際のimportはまだ存在しない(`docs/spec/
  FORGE_AI_ARCHITECTURE_V1.md` 5.3節で確認済み)。
- **(v1.1で追加確認)** `forge_ai.core.compiler.Compiler.compile()`の
  実際のシグネチャは`compile(self, plan: ApplicationPlan) -> ForgeIRDocument`
  であり、`PlanIR`は受け取れない(実際にソースを確認)。
- **(v1.1で追加確認)** `forge_ai.core.pipeline.run_pipeline(user_text: str,
  provider: AIProvider, ...) -> PipelineResult`が既に存在し、
  `PipelineResult`は`domain/world/meaning/intent/plan/ir/quality`という、
  forge_ai/固有の型を**最後まで維持したまま**保持する。これがCEOの
  推奨する「粗粒度Facade」そのものであり、新規実装は不要だった。
- **(v1.1で追加確認)** `backend/app/ai/foundation/interfaces.py`の
  `PlanIR`には現在`screens`・`navigation_edges`・`template_hint`の
  3フィールドのみがあり、「未割当Action」を保持するフィールドが無い
  (2.2節の修正に関連)。
- **(v1.1で追加確認)** `ProviderRouter.default_provider_name()`は
  現在`"forge_ai"`を返しており、CEO指摘通りCognitive Engine名と
  Provider名の混同を招く実装になっている。
- M004とM005は、同じ概念(Intent/Plan/Repair/Quality)に対して
  **異なる形の型を、それぞれ独立に持っている**。今回はこれを統合するか
  Adapterで変換するかを、型ごとに個別に決定する。

---

## 1. Adapter Contract(全体の入出力、v1.1で全面改訂)

### 1.1 M004↔M005の統合粒度(CEO指摘1・2への対応)

**v1.0の誤り**: 「M005がM004のMeaningExtractor・IntentBuilder・
Planner・Compilerを個別に呼び出し、各段階でIntentIR/PlanIRへ変換する」
という設計だった。これは`forge_ai.Compiler.compile()`が`PlanIR`を
受け取れないため、実装すると型エラーで停止する(0章で確認済み)。

**v1.1の方針(粗粒度Facade、CEO推奨案Aを採用)**:

```
M005 は forge_ai.core.pipeline.run_pipeline(natural_language, provider)
を1回だけ呼ぶ。M004内部の個別コンポーネント(MeaningExtractor・
IntentBuilder・Planner・Compiler)をM005から直接呼び出すことはしない。
```

これにより:
- forge_ai/内部では`Intent`・`ApplicationPlan`・`ForgeIRDocument`・
  `QualityScore`という**forge_ai固有の型が最後まで維持される**
  (Compilerに正しい型が渡る)。
- `forge_ai.core.pipeline.run_pipeline()`が「M004パイプラインの
  唯一の所有者」になり、`backend/app/ai/runtime/prompt_pipeline.py`の
  `PromptPipeline`は「M004を1回呼び出した結果を受けて、HTTP・
  Provider選択・Validator・Repair制御・エラー変換・Diagnostics・
  レスポンス整形を行う」という、M004と重複しない責務に限定される。

### 1.2 パイプライン所有者の確定(CEO指摘2への対応)

| コンポーネント | 責務 |
|---|---|
| **M004: `forge_ai.core.pipeline.run_pipeline()`** | Domain→World→Meaning→Intent→ApplicationPlan→ForgeIRDocument→Quality、認知・設計パイプラインの**唯一の所有者** |
| **M005: `backend.app.ai.runtime.prompt_pipeline.PromptPipeline`** | HTTP受付・Provider選択・M004 Facade呼び出し・Validator・Repair制御・エラー変換・Diagnostics・HTTP Response整形 |

M005は今後、M004の個別コンポーネント(`MeaningExtractor`・
`IntentBuilder`・`Planner`・`Compiler`・`QualityEngine`)を直接
importして呼び出してはならない。呼んでよいのは`run_pipeline()`と、
Repair専用に`RepairEngine`(1.3節参照)のみとする。

### 1.3 Repairの扱い(run_pipeline()には含まれないことの確認)

`run_pipeline()`自身のdocstringに「Repair EngineはここではChainして
いない...呼び出し側が明示的に行う設計とした」と明記されている
(0章で確認済み)。これは意図的な設計であり、v1.1でも変更しない。
Repairが必要な場合、M005(Adapter)は`forge_ai.repair.repair_engine.
RepairEngine`を**別途**呼び出す(6章で詳細)。

### 1.4 Input / Output

| フィールド | 型 | 必須 | 説明 |
|---|---|---|---|
| `natural_language` | `str` | ✅ | ユーザーの自然言語入力。`run_pipeline()`の`user_text`引数へそのまま渡す |
| `session_context` | `SessionContext \| None` | — | 直近の会話・生成履歴(4.2節`AIContextBuilder`が既に型を持つ`PromptContext`を利用) |
| `user_metadata` | `UserMetadata \| None` | — | ユーザー設定(方針10章のプライバシー原則により、明示的opt-inが無い限り`None`) |
| `generation_options` | `GenerationOptions \| None` | — | `platform`・`engine`・`provider`・`max_repair_attempts`等(5章HTTP Contractで詳細。engineとproviderの分離はCEO指摘6) |

| フィールド | 型 | 説明 |
|---|---|---|
| `forge_document` | `dict[str, Any]` | **Validator合格済みのdictのみ**(2.3節、CEO指摘3で修正) |
| `diagnostics` | `Diagnostics` | 何回repairしたか、どのProviderを使ったか等(3章・6章で詳細) |
| `quality` | `CriticResult`(foundation既存型) | 2.5節で変換方法を定義(Repairが発生した場合は再評価が必要、2.5節参照) |
| `validation` | `ValidationResult`(schema_validator既存型) | 変換不要、既存のまま使う |

---

## 2. Shared Types(統合 or Adapter変換の決定、v1.1で全面改訂)

CEO指示「統合するかAdapter変換するか比較し、理由付きで決定する」に
従い、5種類の型ペアそれぞれについて決定する。決定の一般原則:
**M004はBackend/HTTP/プロダクション運用の事情を知らないスタンドアロン
ライブラリであり続けるべきであり、M005側がBackend/HTTP固有の事情
(プライバシー・アクセシビリティ・プラットフォーム別出力等)を担う。
この境界を壊す統合は避け、Adapter関数で変換する。**

**v1.1の重要な前提変更**: 1章のFacade方式採用により、2.1
(Intent→IntentIR)・2.2(Plan→PlanIR)の変換は、**M004内部の処理を
駆動するためのものではなくなった**(M004は`run_pipeline()`の中で
`Intent`・`ApplicationPlan`を最後まで自分の型のまま使う)。これらの
変換は、**HTTPレスポンスの`diagnostics`・ログへ記録するための、
事後的・報告用の変換**という位置づけに変わった。これにより、
情報が多少単純化されても機能的な実害は無いが、診断情報としての
正確さは引き続き重要なため、CEO指摘4・5への対応は行う。

### 2.1 Intent — 【決定: Adapter変換、診断用途に限定】

| | forge_ai.Intent | foundation.IntentIR |
|---|---|---|
| フィールド | `goal, required_concepts, required_actions, constraints` | `purpose, target_users, required_features, constraints, open_questions, privacy_notes, accessibility_notes, entities, platform, complexity, category, output_type`(12フィールド) |

**理由**: `IntentIR`は`target_users`・`privacy_notes`・
`accessibility_notes`・`platform`・`complexity`という、実運用
(プライバシー配慮・アクセシビリティ・プラットフォーム別出力)を
前提にしたフィールドを既に持つ。forge_ai.Intentへ統合すると
これらの情報が失われるか、forge_ai/がBackend運用の事情を知る
必要が生じ、M004のスタンドアロン性が壊れる。

**用途(v1.1で明確化)**: この変換結果の`IntentIR`は、`run_pipeline()`
呼び出し**後**に、`PipelineResult.intent`から**診断・ログ目的でのみ**
生成する。M004内部のPlanner/Compilerには一切渡さない
(それらは`PipelineResult.intent`ではなく、`run_pipeline()`内部で
既に`Intent`型のまま処理済み)。

**Adapter関数**: `intent_ir_from_forge_ai_intent(intent, *, platform=Platform.CROSS_PLATFORM, target_users=(), ...) -> IntentIR`
- `goal → purpose`
- `required_concepts → entities`
- `required_actions → required_features`
- `constraints → constraints`(そのまま)
- `target_users`・`open_questions`・`privacy_notes`・
  `accessibility_notes`・`platform`・`complexity`・`category`・
  `output_type`は、forge_ai.Intentには情報が無いため、Adapter呼び出し側
  (HTTPリクエストの`generation_options`)から補う。**この「どこから
  補うか」は未確定(6.1節PROVISIONAL、実装時に決定)。**

### 2.2 Plan / ScreenPlan — 【決定: Adapter変換、診断用途に限定。CEO指摘4・5を反映】

| | forge_ai | foundation |
|---|---|---|
| Plan | `ApplicationPlan(title, screens, data_entities, primary_flow)` | `PlanIR(screens, navigation_edges, template_hint)` |
| ScreenPlan | `ScreenPlan(name, purpose, key_elements)` | `ScreenPlan(screen_id, purpose, data_needed, actions_needed, empty_state_needed, error_state_needed)` |

**理由**: `foundation.ScreenPlan`の`empty_state_needed`・
`error_state_needed`は、Forgeの設計原則(14章UX方針)を型で表現した
production向けの判断を含む。forge_ai.ScreenPlanは意図的にこれを
持たない、より抽象的な型。

**用途(v1.1で明確化)**: 2.1と同様、この変換は`run_pipeline()`が
**既に`ApplicationPlan`を使ってCompileまで完了させた後**の、
診断・ログ目的の変換である。`forge_ai.Compiler`へ`PlanIR`を渡す
ことはしない(1章の修正により、そもそもM005が直接Compilerを
呼ぶことも無い)。

**CEO指摘4の対応(actions_needed=()固定の禁止)**: `Intent.
required_actions`を、`ScreenPlan.actions_needed`まで単純に
「捨てて空にする」設計を撤回する。修正方針:

1. `Intent.required_actions`は、既に2.1節で`IntentIR.
   required_features`へ変換されている。
2. `ApplicationPlan`は現状、どのActionをどの画面に割り当てるかを
   計算していない(forge_ai.Planner既存実装の制約であり、v1.1でも
   これ自体は変更しない、設計のみのため)。
3. **`PlanIR`に、画面へ未割当のActionを保持する新フィールドが
   必要である**: `unassigned_actions: tuple[str, ...] = ()`。
   これは現状の`PlanIR`(0章で確認済み、`screens`・
   `navigation_edges`・`template_hint`の3フィールドのみ)には
   **存在しない**。実装時にこのフィールドを`foundation.PlanIR`へ
   追加することを、次フェーズの前提として明記する
   (今回はコード変更しない、設計上の追加要件として記録するのみ)。
4. Adapter関数は、`ApplicationPlan.primary_flow`(全体の操作の流れ)
   から推測できるActionのうち、個別`ScreenPlan`へ割り当てられない
   ものを`PlanIR.unassigned_actions`へそのまま保持する
   (空にして捨てない)。

**CEO指摘5の対応(key_elementsをdata_neededへ無条件で写さない)**:
`ScreenPlan.key_elements`(forge_ai)は、データ実体・ユーザー操作・
画面表現上の概念が未分類のまま混在した文字列リストである
(forge_ai.Planner自体がこれらを区別していない)。これを無条件で
`data_needed`(データ要件)へ写すと、「検索欄」のような画面表現概念を
データ実体と誤認する。

**修正方針**: Adapterに、以下3分類への振り分けロジックを設ける
(振り分け基準は次フェーズの実装で確定する。今回は分類の存在と
既定の安全側動作のみを設計する)。

| 分類 | 変換先 |
|---|---|
| データ実体(data entity) | `ScreenPlan.data_needed` |
| ユーザー操作(user action) | `ScreenPlan.actions_needed`(4の`unassigned_actions`と合わせて扱う) |
| 画面表現概念(presentation concept) | どちらにも入れず、`ScreenPlan`に新設する`presentation_hints: tuple[str, ...] = ()`(未確定、実装時に`foundation.ScreenPlan`への追加要否を判断) |

**分類できない場合の既定動作**: 誤判定でデータ実体扱いされるより
安全な側として、**分類が不確実な要素は`data_needed`ではなく
`presentation_hints`(または同等の「未分類」置き場)へ入れる**ことを
既定とする(データ要件として過大に扱われるリスクを避ける)。

- `navigation_edges`: forge_ai.Plannerは現状、画面間遷移を明示的な
  データとして持たない。空のままとする(既知のギャップ、6.1節記録)。
- `template_hint`: forge_ai.ApplicationPlanには対応する情報が無い
  (forge_ai.Compilerは常にChecklistテンプレート形状を出力するため、
  現状不要)。

### 2.3 Forge IR — 【決定: 統合不要、ただし境界条件はValidator合格のみ。CEO指摘3を反映】

**v1.0の誤り**: 「forge_ai/とM005が両方とも`dict[str, Any]`を
使っているから、Adapterは不要で互換」と記載していた。CEO指摘の通り、
`dict[str, Any]`という**Pythonのコンテナ型が一致するだけでは、
Forge Language互換であることの根拠にならない**
(`{"hello": "world"}`も`dict[str, Any]`である)。

**v1.1で修正した正確な境界契約**:

```
forge_ai.ForgeIRDocument.to_json_dict()
    ↓
schema_validator.validate_forge_document(dict)
    ↓
ValidationResult.valid == True の場合のみ、
この dict を「Forge Document(境界形式)」として受理する。
valid == False の場合、この dict は境界形式として扱われず、
3章の validation_error として扱われる(Repairを試みた上で、
それでも合格しなければエラー応答とする)。
```

**「dictであること」ではなく「Forge Language Schemaに合格した
dictであること」が境界契約である。** M005はValidatorを通していない
dictを、正常なForge Documentとして下流(Flutter等)へ渡してはならない。

### 2.4 Repair Result — 【決定: Adapter変換、かつ重要な設計上の注意(v1.0で承認済み、Facade方式に合わせて用語のみ整理)】

| | forge_ai.RepairResult | backend.runtime.RepairResult |
|---|---|---|
| フィールド | `ir: ForgeIRDocument, fixed_issues: tuple[RepairIssue], remaining_issues: tuple[RepairIssue], iterations: int` | `document: dict, attempt: int, fixed_issue_count: int, remaining_issue_count: int, success: bool` |

**理由**: forge_ai.RepairResultは実際の問題内容(`RepairIssue`の
リスト)を保持するが、backend.RepairResultは件数のみ(診断用途に
簡略化されている)。

**位置づけ(v1.1で明確化)**: Repairは1.3節の通り`run_pipeline()`には
含まれない。M005(Adapter)が`run_pipeline()`の結果(`PipelineResult.ir`)
に対し、Validator不合格時に**別途**`forge_ai.repair.repair_engine.
RepairEngine`を呼び出す。そのためには、`ValidationResult.errors`を
forge_ai形式の`tuple[RepairIssue, ...]`へ変換する、**新たなAdapter
関数`to_repair_issues(validation: ValidationResult) -> tuple[RepairIssue, ...]`
が必要**(v1.0では未定義だった、今回追加)。

**Adapter関数**: `to_backend_repair_result(r: forge_ai.RepairResult, attempt: int) -> backend.RepairResult`
- `ir.to_json_dict() → document`(2.3節の通り、Validator再検証を経てから境界形式とする)
- `len(fixed_issues) → fixed_issue_count`
- `len(remaining_issues) → remaining_issue_count`
- `len(remaining_issues) == 0 → success`

**⚠️ 重要な設計上の注意(v1.0で発見、CEO承認済み)**: forge_ai.
`RepairEngine.repair()`は**それ自身が`max_iterations`(既定2回)の
内部ループを持つ**。一方M005の`PromptPipeline`も**それ自身が
`MAX_REPAIR_ATTEMPTS`(既定2回)の外側ループを持つ**。もしforge_ai.
RepairEngineをそのままM005の`AIRepair`実装として使うと、
**外側2回 × 内側2回 = 最大4回の実質的な修復試行が発生する
二重ループ問題**が起きる。

**解決方針**: forge_ai.RepairEngineをM005の`AIRepair`として使う場合、
`max_iterations=1`で構築し(内側ループを無効化)、M005の
`PromptPipeline`側の`MAX_REPAIR_ATTEMPTS`だけが実質的なリトライ
回数を制御するようにする。

### 2.5 Quality Result — 【決定: Adapter変換、Repair後の再評価が必要な点を追記】

| | forge_ai.QualityScore | foundation.CriticResult |
|---|---|---|
| フィールド | `correctness, completeness, simplicity, runtime_safety, explainability, maintainability`(各0.0〜1.0) `+ overall` | `score: int(0-100), release_ready: bool, issues: tuple[dict], required_fixes: tuple[str]` |

**理由**: forge_ai.QualityScoreは6軸の詳細スコアを持つが、
foundation.CriticResultは共通指示書6.6節の形式に合わせた、
より粗い集約形式。

**⚠️ v1.1で追加した注意点**: `PipelineResult.quality`は
`run_pipeline()`内部で、**Repair前のオリジナルIR**に対して計算
されている。Repairが発生した場合、この`quality`は古い(修正前の)
評価のままになる。**Repairが発生した場合、Critic呼び出し前に
`forge_ai.quality.quality_engine.QualityEngine().evaluate(repaired_ir,
pipeline_result.plan)`で再評価することを、Adapterの責務として
明記する**(v1.0ではこの再評価の必要性を記載していなかった)。

**Adapter関数**: `to_critic_result(q: forge_ai.QualityScore, threshold: float = 0.8) -> CriticResult`
- `round(q.overall * 100) → score`
- `q.overall >= threshold → release_ready`
- `issues = ()`、`required_fixes = ()`
  **(既知のギャップ、v1.0から継続)**: forge_ai.QualityEngineは
  現状、集約スコアのみを算出し、個別issueを生成しない。今回は
  設計のみのため、この拡張は次フェーズの実装課題として記録するに留める。
- `threshold`(release_ready判定の閾値)の値0.8は暫定、実装時に再検討する。

---

## 3. Error Contract

### 3.1 エラー分類とHTTP対応(v1.1でCEO指摘7を反映し統一)

| 分類 | 意味 | HTTP Status | 発生元 |
|---|---|---|---|
| (Error Contract対象外) | JSON構文自体が壊れている(パース不能) | **400 Bad Request** | HTTPフレームワーク(FastAPI等)の入力層、AI生成ロジックへ到達する前 |
| (Error Contract対象外) | Requestのスキーマ・型が不正(必須フィールド欠如、型不一致等) | **422 Unprocessable Entity** | 同上 |
| (Error Contract対象外) | `natural_language`が空文字列 | **422 Unprocessable Entity** | 同上(値の意味的な妥当性チェックとして422) |
| `planning_error` | 自然言語からIntent/Planを構築できない(Provider応答が無意味・空等) | **422 Unprocessable Entity** | M004(forge_ai/)のMeaning/Intent/Planner段階 |
| `validation_error` | 生成されたForge DocumentがValidatorに合格しない(Repair試行後も) | **422 Unprocessable Entity** | Validator(既存、稼働中) |
| `provider_error` | LLM Provider呼び出し自体が失敗 | **502 / 503 / 504**(3.2節で細分化) | M005 ProviderRouter経由のProvider呼び出し |
| `runtime_error` | 上記以外の、Adapter/M005内部の予期しない実行時エラー | **500 Internal Server Error** | Adapter層・M005内部 |
| `unexpected_error` | 分類不能な例外(キャッチオールの最終防波堤) | **500 Internal Server Error** | 全層共通 |

**統一した基準(v1.0の曖昧さを解消)**:
- **400**: JSON構文そのものが壊れていて、パースすらできない場合のみ。
- **422**: パースは成功したが、スキーマ・型・値が不正、または
  AI処理(Planning/Validation)が意味的に失敗した場合。
  「リクエストの形は理解できたが、要求を満たせなかった」という
  意味で統一する。
- **Request Schema検証・空文字チェックは、AI生成ロジック
  (`planning_error`以降)へ到達する前のHTTP入力層で行う**
  (本Error Contractの5分類には含めないが、HTTP Statusとしては
  上表の通り422で統一する)。

### 3.2 `provider_error`の細分化

| sub_reason | 意味 | HTTP Status |
|---|---|---|
| `timeout` | Provider応答がタイムアウト | 504 Gateway Timeout |
| `rate_limited` | Provider側のレート制限に抵触 | 503 Service Unavailable(`Retry-After`ヘッダ推奨) |
| `invalid_response` | Provider応答が構造化スキーマに従わない、パース不能 | 502 Bad Gateway |
| `auth_failed` | Provider認証エラー(APIキー不正等) | 502 Bad Gateway(詳細をクライアントへ露出しない。共通指示書「APIキーをログ・クライアントへ含めない」に従う) |
| `unavailable` | Provider自体が利用不可(該当Provider未実装Stub含む) | 503 Service Unavailable |

### 3.3 エラーレスポンスの共通形式

```json
{
  "version": "1.0",
  "status": "error",
  "error": {
    "category": "validation_error | planning_error | provider_error | runtime_error | unexpected_error",
    "sub_reason": "timeout | rate_limited | invalid_response | auth_failed | unavailable | null",
    "message": "人間可読な説明(内部のスタックトレース・APIキー等は含まない)",
    "retryable": true
  }
}
```

- `retryable`: クライアント側が同じリクエストを再送してよいか
  (`provider_error`の`timeout`/`rate_limited`/`unavailable`は
  `true`、`validation_error`/`planning_error`は入力を変えない限り
  同じ結果になるため`false`が既定)。
- 開発時(development)は`message`により詳細な情報を含めてよいが、
  本番(production)では技術的な内部情報を露出しない
  (共通指示書12章「development: 問題を見えるようにする、
  production: 安全に失敗する」と同じ原則)。

---

## 4. Provider Contract

### 4.0 Engine と Provider の分離(CEO指摘6への対応、v1.1で新設)

**v1.0の誤り**: HTTP Contractで`"provider": "forge_ai"`を既定値と
していたが、これは「M004(forge_ai/)というCognitive Engine」と
「LLM呼び出しの実装(mock/openai/claude/gemini/oss)」という、
本来別の2つの概念を同じ1つの名前・1つのフィールドで表現してしまい、
混乱を招く(CEO指摘の通り)。

**v1.1での整理**:

| 概念 | 意味 | HTTP Contractでの表現 |
|---|---|---|
| **Engine** | どの認知パイプライン実装を使うか(現状は`forge_ai`のみ、将来他のEngineが追加される可能性はゼロではない) | `generation_options.engine`(既定値`"forge_ai"`) |
| **Provider** | Engineが内部でLLM呼び出しに使う、実際の推論実装(`mock`/`openai`/`claude`/`gemini`/`oss`) | `generation_options.provider`(既定値`"mock"`、5.2節で詳細) |

`forge_ai.AIProvider` Protocol(4.1節)は、あくまで「Engine内部で
使うProvider抽象化」であり、`engine`という名前の選択肢ではない。
`ProviderRouter.default_provider_name()`が現在`"forge_ai"`を
返している実装(0章で確認済み)は、**Engine名をProvider名として
返してしまっている既存のバグ**であり、実装時に既定値を`"mock"`へ
修正する必要がある(現在は無料・未接続段階であり、`"mock"`が
唯一実際に動作するProviderであるため、これが正確な既定値)。

### 4.1 現状の2つのProvider Protocolと、その関係

| | forge_ai.AIProvider | foundation.LLMAdapter(= M005の`AIProvider`) |
|---|---|---|
| メソッド | `complete(prompt: Prompt) -> ProviderResponse` | `complete_structured(prompt: str, response_schema: dict) -> dict` |
| 入力 | 構造化された`Prompt`(stage/system/instruction/context) | フラットな文字列 + JSON Schema |
| 用途 | forge_ai/内部のstage別処理(meaning/intent/planning/compile/repair) | 実際のLLM API(OpenAI等)呼び出しの最小契約 |

**決定: 統合しない。M005の`LLMAdapter`を「実際にLLMを呼び出す際の
唯一の契約」とし、forge_ai.AIProviderは「forge_ai/内部でのみ使う、
より高レベルな抽象化」として残す。**

**理由**: 実際のLLM API(OpenAI Chat Completions・Claude Messages
API等)は、本質的に「文字列プロンプト(+ 構造化出力オプション)」を
受け取る。`LLMAdapter.complete_structured(prompt: str, response_schema)`
はこれに忠実な、最小限の契約であり、どのProvider実装にも要求しやすい。
一方forge_ai.Promptは「system/instruction/contextを分離し、文字列
連結を禁止する」という設計思想(forge_ai/ README参照)を体現するための、
forge_ai/**内部の**抽象化であり、これ自体を全Provider実装に要求する
必要は無い。

### 4.2 Adapter(Provider Bridge)の役割

M004がM005経由で実際のProviderを使う場合、以下のBridgeを設ける
(実装は次フェーズ、契約のみ今回定義)。

```
class ForgeAIProviderBridge:
    """forge_ai.AIProvider Protocolを満たしながら、内部ではM005の
    LLMAdapterへ処理を委譲する。forge_ai/自体はこのBridgeの存在を
    知らない(forge_ai/はMockProviderか、このBridgeか、将来の
    別実装かを区別しない)。"""

    def __init__(self, llm_adapter: LLMAdapter) -> None: ...

    def complete(self, prompt: Prompt) -> ProviderResponse:
        # 1. prompt.system + prompt.instruction + prompt.context を
        #    1本の文字列へ整形する(文字列連結だが、forge_ai/の外側、
        #    Bridge内部でのみ行う。forge_ai/自身は連結しない)。
        # 2. response_schema を prompt.stage に応じて決定する
        #    (meaning/intent/planning/compile/repairそれぞれで
        #    期待するJSON形状が異なる。schemaのカタログ化は実装時)。
        # 3. llm_adapter.complete_structured(flat_prompt, schema) を呼ぶ。
        # 4. 戻り値のdictを ProviderResponse(text=..., structured=...) へ包む。
        ...
```

### 4.3 全Providerが同じInterfaceを実装できることの確認

`LLMAdapter`(`complete_structured(prompt: str, response_schema: dict) -> dict`)
は、Mock・OpenAI・Claude・Gemini・OSS・Forge Nativeいずれについても
実装可能な、最小限の契約である(引数・戻り値が特定ベンダーのSDK型に
依存しない)。既存の`backend/app/ai/foundation/providers.py`の5 Provider
スタブが、全て同じ`LLMAdapter` Protocolを満たす設計になっていることを
再確認済み(以前のセッションで確認済み、今回変更なし)。


---

## 5. HTTP Contract

### 5.1 エンドポイント

```
POST /api/v1/ai/generate
Content-Type: application/json
```

### 5.2 Request(v1.1でengine/provider分離、CEO指摘6・7を反映)

```json
{
  "version": "1.0",
  "input": {
    "natural_language": "買い物リストを作って",
    "session_context": null,
    "user_metadata": null,
    "generation_options": {
      "platform": "cross_platform",
      "engine": "forge_ai",
      "provider": "mock",
      "max_repair_attempts": null
    }
  }
}
```

| フィールド | 型 | 説明 |
|---|---|---|
| `version` | `str` | このHTTP契約自体のバージョン(Forge Language自体のversionとは別)。今回`"1.0"`で開始する |
| `input.natural_language` | `str` | 必須。空文字列は**422**(意味的に不正なリクエスト、3.1節参照。v1.0では誤って400と記載していた) |
| `input.session_context` | `object \| null` | 4.2節`AIContextBuilder`の`PromptContext`に対応。今回のADRでは詳細形式は未確定(6.1節PROVISIONAL) |
| `input.user_metadata` | `object \| null` | 既定`null`(方針10章、明示的opt-inが無い限り送らない) |
| `input.generation_options.platform` | `"mobile"\|"web"\|"desktop"\|"cross_platform"\|null` | `IntentIR.platform`(`Platform` enum)に対応 |
| `input.generation_options.engine` | `str \| null` | **(v1.1で新設、4.0節)** どの認知パイプライン実装を使うか。現状は`"forge_ai"`のみ有効。`null`なら既定`"forge_ai"` |
| `input.generation_options.provider` | `str \| null` | **(v1.1で意味を訂正、4.0節)** Engineが内部で使うLLM実装(`mock`/`openai`/`claude`/`gemini`/`oss`)。`null`なら既定**`"mock"`**(v1.0では誤って`"forge_ai"`と記載していた。現在無料・未接続段階で唯一実際に動作するのは`mock`のため) |
| `input.generation_options.max_repair_attempts` | `int \| null` | `null`なら既定値(2、共通指示書6.5節) |

### 5.3 Response(成功、200 OK)

```json
{
  "version": "1.0",
  "status": "success",
  "result": {
    "forge_document": { "...": "Forge Language JSON(2.3節参照)" },
    "validation": { "valid": true, "errors": [], "warnings": [] },
    "quality": { "score": 82, "release_ready": true, "issues": [], "required_fixes": [] },
    "diagnostics": {
      "engine_used": "forge_ai",
      "provider_used": "mock",
      "repair_attempts": 0,
      "planning_stage_durations_ms": null
    }
  }
}
```

- `validation`: `schema_validator.ValidationResult.to_dict()`をそのまま使う
  (変換不要、2.3節と同じ理由)。
- `quality`: `CriticResult`(2.5節のAdapterで変換したもの)。
- `diagnostics.planning_stage_durations_ms`: 将来のObservability
  拡張点として型だけ用意する(今回`null`固定、6.1節PROVISIONAL)。

### 5.4 Response(エラー、4xx/5xx)

3.3節のエラーレスポンス形式をそのまま使う。

### 5.5 バージョニング方針

このHTTP契約自体の`version`フィールドは、Forge Language(v1.0/v1.1/v1.2)
とは独立してバージョニングする(TD22で指摘した「AI Runtime側の
中間表現にバージョン管理が無い」という技術的負債への、HTTP層での
対応の第一歩)。破壊的変更時は`version`をインクリメントし、
複数バージョンを一定期間並行稼働させる方針を推奨する(具体的な
廃止スケジュール等は実装時に決定、今回は「バージョンフィールドを
持つ」ことだけを契約として固定する)。

---

## 6. Validator Position

### 6.1 呼び出し回数と順序(既存`prompt_pipeline.py`の設計を正式に確定)

`backend/app/ai/runtime/prompt_pipeline.py`の`PromptPipeline.run()`が
**既に実装している**フローを、正式なValidator配置として確定する
(新規設計ではなく、既存の実装済みロジックを追認・文書化する)。

```
1. Draft生成(Planner → LanguageGenerator)
2. Validator呼び出し(1回目)
3. 不合格なら:
   Repair呼び出し → Validator呼び出し(2回目)
   まだ不合格なら:
     Repair呼び出し → Validator呼び出し(3回目)
     (MAX_REPAIR_ATTEMPTS=2回のRepairで、Validatorは最大3回呼ばれる)
4. 最終的に合格していれば: Critic呼び出し
   不合格のままなら: Criticは呼ばない(validation_errorとして返す、3.1節)
```

**Validatorは「Repairの前後で必ず呼ぶ」「Criticより必ず先に呼ぶ」
という順序を固定する。** Criticが不合格な文書を評価する意味は無い
(3.1節のエラー分類にある通り、Validator不合格は`validation_error`
として即座にエラー応答する。Criticまで到達しない)。

### 6.2 Repairとの順序、および2.4節の二重ループ問題との関係

6.1節のフローは、2.4節で指摘した「forge_ai.RepairEngineの内部
ループとM005外側ループの二重化」問題を前提に設計されている。
2.4節の推奨(forge_ai.RepairEngineを`max_iterations=1`で使う)を
採用すれば、6.1節の「最大3回のValidator呼び出し」という回数は
変わらない(M005の外側ループが唯一のリトライ制御になる)。

---

## 7. Sequence Diagrams

`docs/spec/FORGE_AI_ARCHITECTURE_V1.md` 5章(Conceptual Pipeline /
Runtime Call Graph / Source-code Dependency Direction)を土台とし、
今回はAdapter境界を具体化した4種類を示す。

### 7.1 Conceptual Flow(処理段階、呼び出し方向は問わない)

```
Natural Language
    ↓
Domain/World理解 (M004)
    ↓
Meaning抽出 (M004)
    ↓
Intent構築 (M004: Intent → Adapter → IntentIR)
    ↓
Application Plan (M004: ApplicationPlan → Adapter → PlanIR)
    ↓
Forge IR/JSON (M004: ForgeIRDocument.to_json_dict() = そのまま共通形式)
    ↓
Validation (Validator、最大3回)
    ↓
Repair (M004.RepairEngine max_iterations=1、M005外側ループが制御)
    ↓
Quality評価 (M004: QualityScore → Adapter → CriticResult)
    ↓
HTTP Response
```

### 7.2 Runtime Call Sequence(実行時の呼び出し順序、v1.1でFacade方式へ全面修正)

**v1.0の誤り**: PromptPipelineがforge_ai.MeaningExtractor・
IntentBuilder・Planner・Compilerを個別に呼び出し、各段階でIntentIR/
PlanIRへ変換してから次へ渡す設計だった。`forge_ai.Compiler.compile()`
は`ApplicationPlan`しか受け取れないため、`PlanIR`を渡す箇所で
型エラーになる(CEO指摘1)。

```
Flutter --HTTP POST--> M005 HTTP Handler
  M005 HTTP Handler -> ProviderRouter.resolve(engine, provider)  [4.0節]
  M005 HTTP Handler -> PromptPipeline.run(natural_language, resolved_provider, options)

    # ここが v1.0 からの最大の変更点: M004を1回のFacade呼び出しとして扱う。
    # MeaningExtractor・IntentBuilder・Planner・Compilerを
    # PromptPipelineから個別に呼び出すことは、もう行わない。
    PromptPipeline -> forge_ai.core.pipeline.run_pipeline(natural_language, resolved_provider)
      note over run_pipeline: M004内部で完結。
        Domain→World→Meaning→Intent→ApplicationPlan→
        Compiler.compile(ApplicationPlan)→ForgeIRDocument→QualityScore
        という一連の処理を、forge_ai固有の型のまま実行する。
    PromptPipeline <- PipelineResult(domain, world, meaning, intent, plan, ir, quality)

    PromptPipeline -> pipeline_result.ir.to_json_dict()
    PromptPipeline <- draft_dict

    PromptPipeline -> validate_forge_document(draft_dict)  [既存、そのまま]
    PromptPipeline <- ValidationResult

    alt 不合格 かつ 試行回数 < MAX_REPAIR_ATTEMPTS
      PromptPipeline -> Adapter.to_repair_issues(validation_result)  [2.4節、新規Adapter関数]
      Adapter <- tuple[RepairIssue, ...]
      PromptPipeline -> forge_ai.RepairEngine(provider, max_iterations=1).repair(current_ir, issues)  [2.4節]
      PromptPipeline <- forge_ai.RepairResult(ir=repaired_ir, ...)
      PromptPipeline -> repaired_ir.to_json_dict()
      PromptPipeline -> validate_forge_document(repaired_dict)  [再検証]
      note over PromptPipeline: 不合格ならこのブロックを繰り返す(最大MAX_REPAIR_ATTEMPTS回)
    end

    alt 最終的に合格
      alt Repairが発生していた(current_ir が pipeline_result.ir と異なる)
        PromptPipeline -> forge_ai.QualityEngine().evaluate(current_ir, pipeline_result.plan)  [2.5節、再評価]
        PromptPipeline <- QualityScore(再評価後)
      else Repair無し
        PromptPipeline -> pipeline_result.quality をそのまま使う
      end
      PromptPipeline -> Adapter.to_critic_result(quality_score)  [2.5節]
      PromptPipeline <- CriticResult
    else 最終的に不合格
      PromptPipeline -> ErrorResponse(category="validation_error")  [3章]
    end

    PromptPipeline -> Adapter.intent_ir_from_forge_ai_intent(pipeline_result.intent)  [2.1節、診断用途のみ]
    PromptPipeline -> Adapter.plan_ir_from_application_plan(pipeline_result.plan)  [2.2節、診断用途のみ]

  M005 HTTP Handler <- (forge_document, validation, quality, diagnostics)
Flutter <--HTTP Response-- M005 HTTP Handler
```

### 7.3 Dependency Diagram

`FORGE_AI_ARCHITECTURE_V1.md` 5.3節と同一(今回変更なし)。Adapterの
コードは新規に`backend/app/ai/runtime/`配下(例:
`forge_ai_adapter.py`、実装時に命名確定)へ置く想定であり、
`forge_ai/`への実際のimportは、このAdapterファイル1つに限定する
(M005の他のファイルがforge_ai/を直接importしない、という制約を推奨)。
**v1.1の追加制約**: このAdapterファイルがimportしてよいforge_ai/の
公開APIは、`forge_ai.core.pipeline.run_pipeline()`・
`forge_ai.repair.repair_engine.RepairEngine`・
`forge_ai.quality.quality_engine.QualityEngine`・関連する型
(`Intent`・`ApplicationPlan`・`ForgeIRDocument`・`QualityScore`等)に
限定する。`forge_ai.core.meaning_model.MeaningExtractor`・
`forge_ai.core.intent_model.IntentBuilder`・`forge_ai.core.planner.
Planner`・`forge_ai.core.compiler.Compiler`を**Adapterから直接
importしてはならない**(1.2節、これらは`run_pipeline()`内部に
留める)。

### 7.4 Adapter Boundary(境界の可視化、v1.1でFacade方式へ修正)

```
┌───────────────────────────┐        ┌──────────────────────────────┐
│ M004: forge_ai/              │        │ M005: backend/app/ai/runtime/  │
│ (スタンドアロン)              │        │ (Backend統合層)                │
│                             │        │                                │
│ run_pipeline(text, provider) │◀───────│ 1回だけ呼ぶ(Facade)            │
│  内部で完結:                  │───────▶│ PipelineResult を受け取る       │
│  Intent/ApplicationPlan/     │        │                                │
│  ForgeIRDocument/QualityScore │        │ (受け取った後、診断用途のみ:    │
│  は最後まで維持される          │        │  IntentIR/PlanIR/CriticResultへ │
│                             │        │  変換。M004内部処理には無関係)   │
│                             │        │                                │
│ ForgeIRDocument.to_json_dict()│───────▶│ validate_forge_document()      │
│                             │        │ [2.3節、Validator合格が境界条件] │
│                             │        │                                │
│ RepairEngine(provider,       │◀───────│ Validator不合格時、別途呼ぶ      │
│   max_iterations=1)           │───────▶│ RepairResult → backend型へ変換  │
│                             │        │ [2.4節]                        │
│                             │        │                                │
│ AIProvider(Prompt型)         │◀──────▶│ LLMAdapter(文字列) [4.2 Bridge] │
└───────────────────────────┘        └──────────────────────────────┘
        ▲ M004はこの境界の存在を知らない(一方向)
        └ M005は forge_ai/ の公開Facade(run_pipeline・RepairEngine・
          QualityEngine)のみを呼ぶ。個別コンポーネントを直接
          呼び出さない(7.3節の制約)。
```


---

## 8. ADR サマリー(採用理由・却下案・将来拡張)

### 8.1 採用した設計とその理由(まとめ、v1.1で更新)

| 決定 | 採用した設計 | 理由(要約) |
|---|---|---|
| **M004↔M005統合粒度**(v1.1新規) | 粗粒度Facade(`run_pipeline()`)を1回呼ぶ | M004個別コンポーネント呼び出しは`Compiler.compile()`がPlanIRを受け取れず型エラーになる(CEO指摘1で発覚) |
| **パイプライン所有者**(v1.1新規) | M004=認知パイプラインの唯一の所有者、M005=HTTP/Provider/Validator/Repair制御 | 両方がオーケストレーションを持つと責務重複・実装乖離のリスク(CEO指摘2) |
| Intent/Plan | Adapterで変換(診断用途のみ、M004内部処理は駆動しない) | M005側の型は既にproduction向けフィールドを持ち、統合するとM004のスタンドアロン性が壊れる |
| Forge IR | **Validator合格済みdictのみを境界形式とする**(v1.1で訂正) | 単なる`dict[str, Any]`の型一致は互換性の根拠にならない(CEO指摘3) |
| RepairResult | Adapterで変換 + 内部max_iterations=1で二重ループを防止 | 気づかずに実装すると「最大2回」の原則を静かに破る実バグになる箇所だったため、設計段階で明記した |
| QualityScore/CriticResult | Adapterで変換(閾値0.8は暫定、Repair後は再評価) | 6軸スコアと共通指示書形式(score/release_ready)の粒度が異なるため |
| Provider Protocol | M005のLLMAdapter(文字列+schema)を正とし、forge_ai.AIProviderはBridge経由で接続 | 実LLM APIの実態(文字列プロンプト+構造化出力オプション)に忠実な契約を、実装対象を広げる際の摩擦を減らすため優先した |
| **Engine/Provider分離**(v1.1新規) | HTTP Contractで`engine`(forge_ai)と`provider`(mock等)を別フィールドにする | 同じ名前空間に混在させるとCognitive EngineとLLM実装の区別がつかなくなる(CEO指摘6) |
| Validator位置 | Repair前後で必ず呼ぶ、Criticより必ず先 | 既存prompt_pipeline.pyの実装済みロジックを追認。不合格な文書をCriticに渡す意味が無いため |
| **HTTPエラーコード**(v1.1で統一) | 400=JSON構文不正のみ、422=スキーマ/型/意味的な失敗全般 | v1.0で400/422の基準が曖昧だった(CEO指摘7) |

### 8.2 却下した代替案(v1.1で更新)

- **却下1**: forge_ai/の型をforge_ai/foundation/の型に完全一致させる
  (統合)。→ 2.1〜2.2節の理由により却下。M004のスタンドアロン性を
  優先した。
- **却下2**: forge_ai.RepairEngineをM005のAIRepairとしてそのまま
  (max_iterations既定値2のまま)使う。→ 2.4節で指摘した二重ループ
  問題(最大4回修復)により却下。
- **却下3**: forge_ai.AIProvider(Prompt型)を全Provider実装が従うべき
  唯一の契約にする。→ 4.1節の理由(実LLM APIの実態との距離)により却下。
- **却下4**: HTTP ContractにForge Language自体のversionフィールドを
  流用する(専用のHTTP契約versionを持たない)。→ 5.5節の理由
  (TD22で指摘した通り、AI Runtime層とLanguage層は別々にバージョニング
  すべき)により却下。
- **却下5(v1.1新規)**: M005がM004の個別コンポーネント
  (MeaningExtractor/IntentBuilder/Planner/Compiler)を段階ごとに
  呼び出し、各段階でIntentIR/PlanIRへ変換する設計(CEOが示した案B)。
  → `Compiler.compile()`がPlanIRを受け取れないため型エラーになる。
  変換ロジックと情報欠落も増えるため、CEO推奨の粗粒度Facade方式
  (案A)を採用した。
- **却下6(v1.1新規)**: `dict[str, Any]`という型の一致だけを根拠に
  Forge IR境界の互換性を主張する。→ 任意のdictが該当してしまい
  契約として機能しない。Validator合格を必須条件とする形へ訂正した。
- **却下7(v1.1新規)**: `Intent.required_actions`を`ScreenPlan.
  actions_needed=()`として単純に破棄する。→ 画面別の割当が未決定でも、
  Plan全体の`unassigned_actions`として情報を保持する方針へ変更した。

### 8.3 将来の拡張点(今回は設計しない、次フェーズ以降の検討事項)

- **Streaming応答**: 生成の進捗をクライアントへ逐次返す(現状は
  完全な結果を1回のHTTPレスポンスで返すのみ)。
- **Cost/Token計測**: `LLMAdapter`にコスト・トークン数・レイテンシを
  記録するフックが無い(前回のArchitecture Review PHASE11で指摘済み、
  継続課題)。
- **Multi-provider fallback**: 主Providerが失敗した場合に別Providerへ
  自動フォールバックする仕組み(現状ProviderRouterは単一Provider解決のみ)。
- **Caching**: 類似リクエストの再利用。
- **`CriticResult.issues`/`required_fixes`の実質化**: forge_ai.
  QualityEngineが個別issueを報告できるようにする拡張(2.5節)。
- **forge_ai.Plannerのnavigation_edges計算**: 現状Plan段階では
  画面遷移が未計算(2.2節)。

---

## 9. 完了条件チェックリスト(v1.1、CEO監査の6指摘を反映)

| 条件 | 状態 |
|---|---|
| Adapter Contract完成 | ✅ 1章(v1.1でFacade方式へ全面修正、CEO指摘1・2) |
| Shared Types決定(理由付き) | ✅ 2章(5ペア全て決定。actions_needed/data_neededの情報損失を修正、CEO指摘4・5) |
| Error Contract決定 | ✅ 3章(5分類+HTTP対応+sub_reason細分化。400/422を統一、CEO指摘7) |
| Provider Contract決定 | ✅ 4章(Engine/Providerを分離、CEO指摘6) |
| HTTP Contract決定 | ✅ 5章(Request/Response/Error/Version、engine/provider分離を反映) |
| Validator Position確定 | ✅ 6章(既存実装の追認+二重ループ問題との関係を明記。v1.0で承認済み) |
| Sequence Diagram完成 | ✅ 7章(4種類、Facade方式へ全面修正) |
| ADR完成(理由・却下案・将来拡張) | ✅ 8章(却下案5〜7を追加) |
| **CEO監査6指摘への対応** | ✅ 冒頭「改訂履歴」参照。全指摘に対応済み |

**今回発見した、実装前に潰せた設計上のリスク(2件)**:
1. 2.4節の「RepairEngine二重ループ問題」(v1.0で発見、CEO承認済み)。
2. **1.1節の「Compiler型不一致問題」(v1.1でCEO監査により発見)**。
   もしv1.0のまま実装を始めていた場合、`forge_ai.Compiler.compile()`へ
   `PlanIR`を渡そうとして即座に型エラーで停止していた。実コードとの
   突き合わせをCEOに行っていただいたことで、実装着手前に発見できた。

---

## 10. 次のステップ(M005 Implementation、CEO承認後に着手)

1. `foundation.PlanIR`へ`unassigned_actions: tuple[str, ...] = ()`
   フィールドを追加する(2.2節、既存の`IntentIR`拡張と同じ手法で
   後方互換を保つ)。
2. 本ADRのAdapter関数群(2.1・2.2・2.4・2.5節、および新規の
   `to_repair_issues`)を実装する。**`intent_ir_from_forge_ai_intent`・
   `plan_ir_from_application_plan`は診断・ログ用途に限定し、M004内部の
   処理を駆動しないことを実装コメントに明記する(1.1節参照)。**
3. `ForgeAIProviderBridge`(4.2節)を実装する。
4. `ProviderRouter.default_provider_name()`の既定値を`"forge_ai"`から
   `"mock"`へ修正する(4.0節、Engine/Provider分離に伴う修正)。
5. HTTPエンドポイント(5章)を実装する(FastAPI)。`engine`/`provider`
   フィールドを分離し、400/422を3.1節の基準通りに実装する。
6. 7.2節のシーケンスに従い、`PromptPipeline`が`forge_ai.core.pipeline.
   run_pipeline()`を1回呼ぶ形で実装する(個別コンポーネントへの
   直接呼び出しを避ける、7.3節の制約)。
7. Unit Test・Contract Test(Adapter関数の変換ロジック、特に
   Facade呼び出しの型整合性)を追加する。

**今回のセッションでは、上記いずれも実装していない
(実装開始禁止の指示を厳守した)。**
