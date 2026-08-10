# FORGE-MILESTONE-007 PREPARATION 実施レポート — Implementation Blueprint v1.3

**Ref:** FORGE-MILESTONE-007 PREPARATION　**担当:** Principal Engineer / Architect（Claude）
**日付:** 2026-07-15(CEO実物監査4回を経て最終化)

新規コードは0行。既存コード(`forge_ai/`・`backend/app/ai/`・Flutter
Runtime・`backend/app/ai/native/`)は一切変更していない。

---

## 1. 現在の設計(最終状態)

### 1.1 成果物

| ファイル | 内容 |
|---|---|
| `docs/spec/FORGE_M007_IMPLEMENTATION_BLUEPRINT.md` | 本体(v1.3、全面書き直し) |
| `docs/diagrams/10_m007_dependency_graph.md` | 依存図 |
| `docs/spec/FORGE_COGNITIVE_ARCHITECTURE_V2.md` | M006本体(段階数表記を更新) |
| `docs/diagrams/01_cognitive_pipeline.md`・`07_template_selection_flow.md` | M006の関連図(更新) |
| `docs/adr/ADR-008`・`ADR-009` | 関連ADR(更新) |

### 1.2 設計の要点

- **既存ファイルは一切移動しない**。M006の新規認知能力は、
  `forge_ai/core/`配下の新設6サブディレクトリ
  (input_processing/understanding/planning/critic/confirmation/
  orchestration)へ追加する。
- **Legacy/Cognitive Protocol分離**。既存Protocol(`IntentBuilderProtocol`
  等)は既存`run_pipeline()`専用として無変更で維持し、M006用には
  別シグネチャの`CognitiveIntentRecognizerProtocol`等を新設する。
  これにより、M006が指定する認知順序(Intentが最初)を、既存Protocolの
  都合で変更する必要が無い。
- **Facade分離によるMigration**。`run_pipeline()`(既存、無変更)とは
  別に`run_cognitive_pipeline() -> CognitivePipelineOutcome`という
  新Facadeを設け、Boolean Feature Flagは使わない。M005が実際にこちらを
  呼ぶかどうかの切り替えは、CEO承認を得た別Task(import文の切り替え)
  として扱う。
- **`CognitivePipelineOutcome`は3つの独立したdataclass
  (`CognitivePipelineSuccess`/`NeedsConfirmation`/`Failed`)のUnion**。
  Union型エイリアスへメソッド呼び出しはしない(型として成立しないため)。
  `Success`は`context`・`ir`・`initial_quality`の3フィールドのみを持ち、
  `CognitiveContext`が既に持つ情報を重複保持しない。
- **`CognitiveDependencies`という専用dataclassで依存注入**。
  `**`展開は行わず、`CognitiveOrchestrator`は`dependencies`を単一の
  引数として受け取る。
- **段階数は「14 Transformation Stage + 1 Terminal Outcome(M004側)+
  3 M005 Post-processing Stage」に確定**。「16段階」という表記は撤回
  した。Preliminary Pattern CandidatesはApplication Planning内部へ
  隠さず、独立した可視のTransformation Stageとして扱う。
- **DomainClassificationは実際の複数候補スコアリング**。全Domainの
  スコアが0の場合は`primary_domain=Generic`・`confidence=0.0`・
  `score_margin=0.0`を明示的に強制する。confidenceは「Intentの情報を
  どれだけ説明できたか」を測る式を採用した(単純な相対比較は過大評価
  リスクがあるため却下)。
- **World ModelはDomainとIntentの両方から構築**。Legacy
  `WorldModelBuilderProtocol.build(domain)`はCognitive経路で使用しない。
- **Preliminary/Final不一致時の再計画は、Cognitive Revisionへ一本化**。
  同じ入力でPlannerを再実行するのではなく、不一致を合成Critic Issueと
  して構築し`revision_engine.revise()`へ渡す。カウンタは共有する。
- **Provider障害とCognitive Errorの分離**。`NotImplementedError`は
  Orchestrator内で捕捉せず、`run_cognitive_pipeline()`の外側まで
  伝播させる(将来M005が`provider_error`として分類できるようにするため)。
  `AmbiguityError`/`ConfirmationRequired`は`NeedsConfirmation`へ、
  `PlanningError`/`CriticFailure`等は`Failed`へ変換する。

---

## 2. 検証(実行結果、事実)

```
$ python -m unittest discover -s backend/tests -p "test_*.py"
Ran 265 tests in 0.030s
OK (skipped=17)

$ python -m unittest discover -s forge_ai/tests -p "test_*.py"
Ran 80 tests in 0.013s
OK
```

`backend/app/ai/native/`・Flutterの無変更を確認した。

---

## 3. 事実・推測・提案の分離

- **事実**: 既存forge_ai/のファイル構成・Legacy Protocol一覧・
  `run_pipeline()`シグネチャ・既存テスト件数(80件)・M005の
  `pipeline_errors.py`の例外捕捉順序は、いずれも実際に確認した事実。
- **提案**: ディレクトリ構成・Cognitive Protocol設計・
  `CognitiveDependencies`/`CognitivePipelineOutcome`の型設計・依存規則・
  Error階層・段階数の分類(Transformation/Control-flow/Terminal/
  Post-processing)は、M006本体・既存コードから直接導出した、確度の
  高い設計判断。
- **より不確かな推測**: Task7のテスト件数概算(約189〜221件)・
  DomainClassificationのスコアリング重み付け係数は、実装時に調整
  しうる暫定値。

---

## 4. 完了条件

`docs/spec/FORGE_M007_IMPLEMENTATION_BLUEPRINT.md` 10章の完了条件
チェックリスト、12章のCEO確認事項(7点)を参照。

---

## 5. CEOへの確認事項(抜粋)

1. Task9.1のFacade分離方式の採用可否、および「M005側のimport切り替えを
   いつ・どのTaskで行うか」。
2. `CognitivePipelineFailed`をM005側で`planning_error`へ変換する処理
   (M005側の変更を伴うため今回のスコープ外とした)を、いつ・どのTask
   で扱うか。
3. Task4.3の`DomainClassification`スコアリング重み付けは暫定値であり、
   実装時に実データでの検証・調整が必要。
4. 段階数の最終確定(「14 Transformation Stage + 1 Terminal Outcome +
   3 M005 Post-processing Stage」)を、M006本体・関連図・ADR-008へ
   反映済み。この反映内容に問題がないか。

---

## 6. 監査の変遷(要約)

本Taskは、4回のCEO実物監査を経て段階的に精緻化された。詳細な経緯・
却下した設計・その理由は、`docs/spec/FORGE_M007_IMPLEMENTATION_BLUEPRINT.md`
14章(設計の変遷、Superseded Design History)に集約した。要約:

1. **1回目**: 9タスクの基本設計(ディレクトリ・Context・Orchestrator・
   Protocol・依存規則・Error Model・テスト戦略・実装順序・Migration Plan)。
2. **2回目**: Boolean Feature FlagをFacade分離へ置換。Protocol呼び出し
   規約の型不整合を修正。Quality責務(M004=Initial/M005=Final)を確定。
   Error mapping精度を修正。
3. **3回目**: Legacy/Cognitive Protocolを完全分離。M006の認知順序
   (Intentが最初)を維持。RequirementsをPlannerへ必須で渡す契約に。
   Preliminary Pattern Candidatesを独立ノード化。DomainClassification
   を実スコアリングへ(初版)。World BuilderをIntentも使う契約に。
4. **4回目(本版)**: Outcome構築APIの型不整合(Union aliasへの
   メソッド呼び出し)を修正。Successのフィールド重複を解消。
   Dependenciesの`**`展開という型不整合を修正。段階数を
   「14+1+3」へ最終確定(「16段階」表記を撤回)。DomainClassificationの
   安全性条件(全0→Generic、同点→margin0)を追加、confidence定義を
   比較の上で再決定。Preliminary/Final不一致時の再計画をCognitive
   Revisionへ一本化。NotImplementedErrorの非捕捉を明記。文書全体の
   旧記述を、現行本文から分離しSuperseded Design Historyへ集約。
