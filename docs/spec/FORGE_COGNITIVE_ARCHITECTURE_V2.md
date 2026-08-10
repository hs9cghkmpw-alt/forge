# Forge Cognitive Architecture v2.0

**Status: ARCHITECTURE DESIGN ONLY — 実装コード0行**
**Ref:** FORGE-MILESTONE-006　**日付:** 2026-07-15
**担当:** Principal Engineer / Architect（Claude）

本ドキュメントは設計のみである。新規Python/Dartコードは1行も追加していない。
既存コード(`forge_ai/`・`backend/app/ai/`・Flutter Runtime)も一切変更していない。
実装は次マイルストーン(M007以降)で、本設計に対するCEO承認を得てから開始する。

---

## 0. 本ドキュメントの構成

本体はここ(`FORGE_COGNITIVE_ARCHITECTURE_V2.md`)に置き、以下は個別ファイルへ分離した。

| 内容 | 場所 |
|---|---|
| ADR(8件) | `docs/adr/ADR-001`〜`ADR-008` |
| 図(9種) | `docs/diagrams/*.md`(Mermaid) |
| 完全トレース例(6件) | `docs/examples/*.md` |
| 本Task記録 | `docs/tasks/task030.md` |
| 実施レポート | `FORGE-MILESTONE-006-report.md` |

---

## 1. 目的

Forge AIを、自然言語→JSON変換器ではなく、**自然言語から対象領域・意味・
意図・アプリ構造を推論し、説明可能な設計を生成するCognitive Engine**
として定義する。M005までに完成している経路:

```
HTTP → Backend AI Integration(M005) → Forge AI Core(M004) → Validator
→ Repair → Quality → HTTP Response
```

M006が再設計するのは、この中の**Forge AI Core内部の認知・設計能力**
(Natural Language → Intent → Domain → World → Meaning → Planning →
Template Selection → Design Critic → Forge IR)である。

---

## 2. 最重要設計原則

### 2.1 Cognitive First
LLMへ直接JSONを作らせない。理解→設計→生成の順を守る。forge_ai/の
既存パイプライン(`domain_model → world_model → meaning_model →
intent_model → planner → compiler`)は既にこの順序を採用しており、
本設計はこれを強化・具体化する形を取る(ゼロから作り直さない)。

### 2.2 Rule Before Prompt
決定的なルール・Domain Knowledge・Validatorで判断できることは、LLMへ
委譲しない。LLMは曖昧さの解消・候補生成・補助推論に限定する。

### 2.3 Meaning Before UI
画面構成を考える前に、対象世界・利用者・目的・データ・行動を整理する。
World Model・Meaning Modelは、Widget/画面という概念を一切知らない
(forge_ai/の既存原則「PlannerはRuntimeを知らない」の延長)。

### 2.4 Explainability
すべての重要な設計判断について理由を追跡できる(18章 Decision Trace)。

### 2.5 Provider Independence
OpenAI/Claude/Gemini/OSS/Mockのどれでも、Forgeの基本設計品質が大きく
変わらない構造にする(16章 LLM使用方針)。

### 2.6 Human Override
Forgeの判断は提案であり、最終決定は利用者にある。曖昧な情報を勝手に
確定しない(6章 Ambiguity Detection)。

### 2.7 Progressive Refinement
最初の出力を完成品とみなさない。Draft→Critic→Revision→Validation→
Qualityによる段階的改善を前提にする(15章 Self-Revision Loop)。

---

## 3. Cognitive Pipeline(14 Transformation Stage + 1 Terminal Outcome + 3 M005 Post-processing Stage、CEO監査(4回目)により「16段階」表記を撤回・再定義)

**修正内容**: 「全16段階」という表記は、性質の異なる要素
(実際にデータを変換する段階・分岐にすぎない制御ノード・Pipeline実行が
そこで終わる終端・M005が別途実行する後処理)を区別せずに数えた結果
であり、不正確だった。以下4分類で正確に数え直す。

| 分類 | 意味 | 該当するもの | 個数 |
|---|---|---|---|
| **Transformation Stage** | Contextへ新しいデータを追加する、実際の変換処理 | Input Normalization・Ambiguity Detection・Cognitive Intent Recognition・Domain Classification・World Model Construction・Meaning Model・Requirement Extraction・Preliminary Pattern Candidates・Application Planning・Final Template Selection・Design Critic・Cognitive Revision・Forge IR Compilation・Initial Quality Evaluation | **14** |
| **Control-flow Node** | データを変換せず、次にどこへ進むかを決めるだけの分岐 | Priority1/Priority2判定・`differs_from_preliminary`判定・`release_ready`判定 | (独立した段階として数えない) |
| **Terminal Outcome** | Pipelineの実行がそこで終わる、分岐の着地点 | Human Confirmation / Escalation | **1** |
| **M005 Post-processing Stage** | `run_cognitive_pipeline()`の外側、M005が別途実行する処理 | Validation・Repair・Final Quality Evaluation | **3** |

Cognitive Pipeline(M004側、`run_cognitive_pipeline()`の内部)は、
**14 Transformation Stage + 1 Terminal Outcome**から成る。M005側の
3 Post-processing Stageは、別の関数呼び出しであり、Cognitive Pipeline
自体の段階数には含めない。「全16段階」という表記は撤回する
(旧「14→16」への修正自体も、4分類を区別しない数え方に基づく暫定的な
訂正であり、正式なものではなかった。`docs/spec/
FORGE_M007_IMPLEMENTATION_BLUEPRINT.md` Task3.3で最終確定した)。

Preliminary Pattern Candidates(8段階目)は、Application Planningの
内部へ隠さず、Orchestratorが明示的に呼び出す独立したTransformation
Stageとして扱う(以前は「トップレベルの段階数を増やさないため」
Application Planning内部へ隠していたが、これは責務の実態を数合わせの
ために歪めるものだったため撤回した。ADR-008参照)。8番目
(Preliminary Pattern Candidates)と9番目(Application Planning)の間、
Application PlanningがDomain Registryの`recommended_patterns`という
Templateヒントを使う設計と、Final Template Selectionが後から独立して
行われる設計の関係は、3.8節・3.9節・ADR-008で詳細を扱う。

```
User Input
  → Input Normalization                          [1]
  → Ambiguity Detection                          [2]
  → Intent Recognition                           [3]
  → Domain Classification                        [4]
  → World Model Construction                     [5]
  → Meaning Model                                [6]
  → Requirement Extraction                       [7]
  → Application Planning                         [8]
      (内部: Preliminary Pattern Candidates → Screen/State/Action設計)
  → Template Selection(= Final Template Selection) [9]
  → Design Critic                                [10]
  → Cognitive Revision ─┐                        [11]
       ↑                │(release_ready=false)
       └────────────────┘
  → Human Confirmation / Escalation(必要な場合のみ経由) [12]
  → Forge IR Compilation                         [13]
  → Validation                                   [14]
  → Repair                                        [15]
  → Quality Evaluation                            [16]
```

**Human Confirmation/Escalationの位置づけ**: 上図では9〜12番目の直後に
1回だけ描いているが、実際には**Ambiguity Detection[2]・Domain
Classification[4]・Design Critic[10]のいずれからも到達しうる**
(4.3節・14.2節・11章)。8番目より前で確認要求が発生した場合、
Application Planning以降には進まず、この[12]の段階へ直接ジャンプする
(`docs/diagrams/01_cognitive_pipeline.md`で全経路を図示する)。

図は`docs/diagrams/01_cognitive_pipeline.md`参照。以下、各段階を
「入力・出力・責務・非責務・使用するルール・LLM使用条件・失敗時の扱い・
次段階への契約・説明可能性の記録方法」の9項目で定義する。

### 3.1 Input Normalization

| 項目 | 内容 |
|---|---|
| 入力 | ユーザーの生の自然言語文字列(`raw_input: str`) |
| 出力 | `NormalizedInput { raw_input, normalized_text, detected_language, warnings }` |
| 責務 | 前後空白除去、全角/半角統一、口語・省略の軽微な補完(意味を変えない範囲)、極端な長さの検出 |
| 非責務 | 意味解釈・意図推定・Domain判定(次段階以降の責務)。**ユーザーの意味を変更すること** |
| 使用するルール | 決定的な文字列処理(trim・unicode正規化)。5章で詳細 |
| LLM使用条件 | 原則不要(Deterministic)。ただし「口語・誤字が著しく、決定的ルールでは正規化できない」と判定された場合のみHybrid(5章) |
| 失敗時の扱い | 正規化に失敗しても`raw_input`をそのまま次段階へ渡す(クラッシュさせない。正規化は最適化であり必須ではない) |
| 次段階への契約 | `raw_input`と`normalized_text`の両方を、パイプライン終端まで保持し続ける(Decision Traceが常に元の入力を参照できるようにする) |
| 説明可能性 | どの正規化ルールが適用されたかを`applied_rules: tuple[str, ...]`として記録 |

### 3.2 Ambiguity Detection

| 項目 | 内容 |
|---|---|
| 入力 | `NormalizedInput` |
| 出力 | `AmbiguityReport { ambiguities: tuple[Ambiguity, ...], overall_severity }` |
| 責務 | 6章の8分類に基づき、欠落・矛盾・複数解釈の可能性を検出する |
| 非責務 | 曖昧さの解消そのもの(Intent Recognition以降が、検出結果を踏まえて推定・確認要求を行う) |
| 使用するルール | パターンマッチ(欠落チェック: 主語・目的語・行為動詞の有無)。6章で詳細 |
| LLM使用条件 | Hybrid。決定的パターンで検出できる欠落(例: 動詞が無い)はRuleで、
  「複数の可能なTemplateにまたがる曖昧さ」等の意味的判断はLLM補助 |
| 失敗時の扱い | 検出処理自体が失敗した場合、`ambiguities=()`かつ`detection_status="failed"`・`overall_severity="unknown"`という明示的な状態を返す(以前の「曖昧さ無しとして楽観的に継続」という扱いはCEO監査により廃止した)。低リスク・単純Domainのみ`warning`付きで限定継続し、Privacy/Health/Welfare/Reservation/Permission関連の可能性がある場合はHuman Confirmation/Escalation(3.12節)へ進むか安全停止する(4.4節で詳細) |
| 次段階への契約 | `AmbiguityReport`をIntent Recognition以降が読み、HIGH判定があれば確認要求フローへ分岐できるようにする |
| 説明可能性 | 各`Ambiguity`が`category`・`evidence`(該当箇所)・`severity`を持つ |

### 3.3 Intent Recognition

| 項目 | 内容 |
|---|---|
| 入力 | `NormalizedInput`、`AmbiguityReport` |
| 出力 | `Intent`(7章の構造、`primary_goal`〜`evidence`の11フィールド) |
| 責務 | 主目的・副次目的・関係者・必要操作・必要データ・制約・成功条件・禁止事項・未解決点の抽出 |
| 非責務 | Domain確定(次段階)、UI構造の決定(Plannerの責務) |
| 使用するルール | Domain Knowledge(8章)のcommon_actions/entitiesとの照合による候補抽出 |
| LLM使用条件 | Hybrid。候補抽出はRule、複数候補からの選択・自由記述の要約はLLM補助 |
| 失敗時の扱い | 抽出できたフィールドのみ埋め、それ以外は空・既定値とする。`confidence`を低く設定し、後続段階が慎重に扱えるようにする(クラッシュ・停止はしない) |
| 次段階への契約 | `Intent`はDomain Classification・World Model Construction両方から参照される(読み取り専用) |
| 説明可能性 | `evidence`(入力文中のどの部分から各フィールドを抽出したか)、`confidence` |

### 3.4 Domain Classification

| 項目 | 内容 |
|---|---|
| 入力 | `Intent` |
| 出力 | `DomainClassification { primary_domain, candidate_domains, confidence, rationale }` |
| 責務 | 8章のDomain Registryと`Intent`を照合し、最も適合するDomainを選ぶ |
| 非責務 | World Model構築(次段階)。Domain定義自体の作成(事前に8章で定義済みのものを使う) |
| 使用するルール | Domain Registryの`common_actions`・`entities`との一致度スコアリング(決定的) |
| LLM使用条件 | Rule + LLM fallback。スコアリングで一意に決まらない場合(僅差・複数該当)のみLLMで補助判断 |
| 失敗時の扱い | 一致するDomainが無い場合`generic`Domainへフォールバック(既存forge_ai/の`DomainCategory.GENERIC`と同じ設計思想) |
| 次段階への契約 | `primary_domain`がWorld Model Constructionの入力になる。`candidate_domains`(次点)はDecision Traceに残し、後で「なぜこのDomainを選ばなかったか」を説明できるようにする |
| 説明可能性 | `rationale`(一致した`common_actions`/`entities`の一覧) |

### 3.5 World Model Construction

| 項目 | 内容 |
|---|---|
| 入力 | `DomainClassification`、`Intent` |
| 出力 | `World { actors, entities, relationships, rules, events, states, permissions, constraints }`(9章) |
| 責務 | Domain定義とIntentから、具体的なActor/Entity/Relationship/Rule等を組み立てる |
| 非責務 | **UIを一切知らない**(Widget・画面・ボタンという概念を含めない)。意味抽出(Meaning Modelの責務) |
| 使用するルール | Domain Registryのテンプレート的なActor/Entity定義を土台に、Intentの`actors`/`required_data`で補強する決定的な組み立てロジック |
| LLM使用条件 | 原則Deterministic。Domain定義がカバーしない特殊なActor/Entityが明示的に要求された場合のみLLM補助で追加候補を生成(採否はRuleで検証) |
| 失敗時の扱い | Domain定義の最小限(actorsに`user`のみ等)にフォールバックする。World Model自体が空になることは無い(最低限`user`という1 Actorは常に存在する) |
| 次段階への契約 | `World`はMeaning Model・Requirement Extraction・Plannerから参照される(読み取り専用) |
| 説明可能性 | どのDomain定義項目から各Actor/Entityが生成されたかを`derived_from`として記録 |

### 3.6 Meaning Model

| 項目 | 内容 |
|---|---|
| 入力 | `NormalizedInput`、`World` |
| 出力 | `Meaning`(10章の9フィールド) |
| 責務 | 入力文章とWorld Modelの間をつなぐ。文中のどの語がWorld Modelのどの
  Entity/Actor/Ruleに対応するかを対応付ける |
| 非責務 | World自体の変更(Worldは読み取り専用として扱う)。要件への分解(次段階) |
| 使用するルール | Worldの`entities`/`actors`名との文字列マッチ・同義語辞書(Domain Registry内、8章) |
| LLM使用条件 | Hybrid。直接一致はRule、比喩・言い換え表現の解決はLLM補助 |
| 失敗時の扱い | 対応付けできない語は`semantic_units`に残すが`referenced_entities`には含めない(無理に紐付けない。6.3の「Human Override」原則) |
| 次段階への契約 | `Meaning`はRequirement Extractionの主要な入力になる |
| 説明可能性 | `evidence_spans`(入力文中の該当箇所)を各semantic_unitへ付与 |

### 3.7 Requirement Extraction

| 項目 | 内容 |
|---|---|
| 入力 | `Meaning`、`World`、`Intent` |
| 出力 | `RequirementSet`(11章の8分類×各Requirement) |
| 責務 | Functional/Non-Functional/Data/Interaction/Validation/Privacy/
  Accessibility要件、およびOpen Questionsへの分離 |
| 非責務 | 画面構造への割当(Plannerの責務) |
| 使用するルール | Domain Registryの`rules`/`constraints`をNon-Functional/Validation要件の土台にする(決定的変換) |
| LLM使用条件 | Hybrid。Domain定義から機械的に導出できる要件はRule、Intentの
  自由記述部分からの要件抽出はLLM補助 |
| 失敗時の扱い | 抽出不能な部分は`Open Questions`へ積む(勝手に確定しない、Human Override原則) |
| 次段階への契約 | `RequirementSet`はPlannerの主要な入力になる |
| 説明可能性 | 各`Requirement`が`requirement_id`・`source`(どのMeaning/Intent項目由来か)・`rationale`を持つ |

### 3.8 Preliminary Pattern Candidates(独立したTransformation Stage)

以前は「Domain Registryの`recommended_patterns`」をApplication
Planningが直接参照しながら、Template Selectionが独立した後続段階として
定義されており、Plannerが実質的にTemplateを先取りしているという循環
依存が暗黙のままだった。この段階を、Application Planning内部へ隠さず、
**独立したTransformation Stage**として明示する
(`FORGE_M007_IMPLEMENTATION_BLUEPRINT.md` Task3.3・ADR-008参照。
以前は「トップレベルの段階数を増やさない」という理由で内部へ隠して
いたが、責務の実態を数合わせのために歪めるべきではないと判断し撤回した)。

| 項目 | 内容 |
|---|---|
| 入力 | `Domain`(primary_domain)、`Intent`、`RequirementSet` |
| 出力 | `preliminary_candidates: tuple[str, ...]`(Template Family名の暫定候補) |
| 責務 | Domain・Intent・RequirementSetのみから、`recommended_patterns`
  (5.1節)を参照してTemplate Family候補を**大まかに**絞り込む(まだ
  画面数・遷移等は評価しない、暫定候補に過ぎない) |
| 非責務 | Templateの最終決定(3.9節Final Template Selectionの責務)、
  画面構成の決定(3.8b節Application Planningの責務) |
| 使用するルール | Domain Registryの`recommended_patterns`との一致に
  よる絞り込み(決定的) |
| LLM使用条件 | Deterministic(Rule-basedのみ) |
| 失敗時の扱い | 一致する`recommended_patterns`が無い場合、`generic`を
  候補に含める(空にしない) |
| 次段階への契約 | `preliminary_candidates`は、3.8b節Application
  Planning・3.9節Final Template Selectionの両方の入力になる |
| 説明可能性 | どのDomainの`recommended_patterns`から絞り込んだかを
  Decision Traceへ記録する |

### 3.8b Application Planning

| 項目 | 内容 |
|---|---|
| 入力 | `Intent`、`World`、`RequirementSet`、`preliminary_candidates`(3.8節の出力) |
| 出力 | `ApplicationPlan`(9章の13フィールド) |
| 責務 | Preliminary候補をヒントとしつつ、画面構成・画面責務・遷移・
  State要求・Action要求・検証要求・空/エラー状態要求を決定する |
| 非責務 | Widgetの細部・**Templateの最終決定**(3.9節Final Template
  Selectionの責務)。Forge IR生成(Compilerの責務) |
| 使用するルール | 要件の`mandatory`フラグに基づく画面分割の決定的ロジック |
| LLM使用条件 | Hybrid。画面をどう統合/分割するかの判断はLLM補助
  (Design Criticで後検証) |
| 失敗時の扱い | 割当不能な要件は`unassigned_requirements`へ保持
  (情報を失わない。forge_ai/M005 Adapterの`unassigned_actions`と
  同じ設計思想) |
| 次段階への契約 | `ApplicationPlan`は、3.9節Final Template
  Selection・3.10節Design Criticの入力になる |
| 説明可能性 | `design_rationale`(なぜこの画面構成にしたか) |

### 3.9 Final Template Selection

| 項目 | 内容 |
|---|---|
| 入力 | `ApplicationPlan`(3.8b節の出力) |
| 出力 | `TemplateSelection { selected_template, candidates, scores, rationale, differs_from_preliminary: bool }` |
| 責務 | 10章の11 Template Familyから、**実際に確定したApplicationPlanの
  画面数・編集要否・履歴要否・集計要否・遷移要否・検証要否等**
  (10.2節の9評価基準)を使い、画面ごとに最終決定する。Preliminary
  候補(3.8節)はヒントに過ぎず、最終決定を拘束しない |
| 非責務 | 実際のWidget配置(Compilerの責務) |
| 使用するルール | 10章の評価基準(Dominant user action等9項目)による決定的スコアリング |
| LLM使用条件 | Rule-based scoring + LLM tie-break(僅差の場合のみ) |
| 失敗時の扱い | スコアが決定的に決まらない場合は`generic`Templateへ
  (17章)。**Final選択がPreliminary候補と著しく異なる場合
  (`differs_from_preliminary=true`)、Application Planningを同じ入力で
  再実行することはしない(決定的な実装であれば同じPlanが再生成される
  だけで無意味なため)。代わりに、この不一致を「合成Critic Issue」
  として構築し、Cognitive Revision(3.11節)へ一本化する。
  `revision_engine.revise()`が不一致の内容(どのTemplateが実際に
  選ばれたか)を新しい情報として受け取り、Planを更新する。これは
  Cognitive Revisionと同じカウンタ・上限を共有し、独立した新しい
  ループを作らない(12.4節「二重ループ防止」の対象を、Cognitive
  Revision⇔Schema Repairの2つから、Preliminary/Final不一致による
  再計画を含む3つ目の潜在ループへ拡張する。詳細はADR-008)** |
| 次段階への契約 | `TemplateSelection`はDesign Criticが妥当性を検証し、Compilerが実際のForge IRへ変換する際の指示になる |
| 説明可能性 | `candidates`(却下したTemplateとその理由)、`differs_from_preliminary`とその理由 |

### 3.10 Design Critic

| 項目 | 内容 |
|---|---|
| 入力 | `ApplicationPlan`、`TemplateSelection`、`RequirementSet` |
| 出力 | `CriticReport`(14章の6フィールド×各issue) |
| 責務 | 14章の14評価軸で設計品質を評価する(Validatorとは別、「仕様上正しいか」ではなく「設計として良いか」) |
| 非責務 | JSON構文・Schema検証(Validatorの責務)。自動修正の実行(Self-Revision Loopが担う) |
| 使用するルール | 決定的チェック(例: 全画面にEmpty State要求があるか)。14章 |
| LLM使用条件 | Deterministic checks + LLM semantic review(意味的な一貫性はLLM) |
| 失敗時の扱い | Critic自体が失敗した場合、`issues=()`とし、`release_ready=false`(安全側、無条件で合格にしない) |
| 次段階への契約 | `CriticReport`はCognitive Revision(3.11節)の入力。`release_ready`が真ならForge IR Compilation(3.13節)へ進む |
| 説明可能性 | 各issueが`evidence`・`recommended_fix`・`affected_component` |

### 3.11 Cognitive Revision(新設、CEO監査により独立段階化)

**修正内容**: 以前は12章(Self-Revision Loop)の説明の中に暗黙に
含まれていたが、パイプラインの独立した1段階として明示する。

| 項目 | 内容 |
|---|---|
| 入力 | `CriticReport`、`ApplicationPlan`、`TemplateSelection` |
| 出力 | 修正済み`ApplicationPlan`(Template Selectionへ差し戻し、3.9節を再実行)、または`revision_exhausted: true`(上限到達) |
| 責務 | Criticが指摘した`issues`のうち`auto_fixable=true`のものを機械的に修正し、それ以外はLLM補助で修正案を生成する(12章の詳細) |
| 非責務 | JSON構文修正(Schema Repair、3.15節の責務)。Critic自体の再評価(この段階の直後、3.10節へ戻って再評価する) |
| 使用するルール | 12.2節の停止条件(最大2回・スコア改善なし・再発検出) |
| LLM使用条件 | Hybrid。修正方針の生成はLLM、適用可否の判定はRule(Criticの再評価) |
| 失敗時の扱い | 上限到達・改善無し・再発検出のいずれかに該当した場合、Human Confirmation/Escalation(3.12節)へ進む(クラッシュさせず、必ずどこかへ遷移する) |
| 次段階への契約 | 修正版`ApplicationPlan`は3.9節(Template Selection)・3.10節(Design Critic)を再実行する。**このカウンタは3.9節の「Preliminary/Final差異による再計画」とも共有する(12.4節、二重ループ防止をPlanning⇔Template Selectionへも拡張)** |
| 説明可能性 | 各Revision試行が`attempt`番号・修正前後のCriticスコア差分を記録する |

### 3.12 Human Confirmation / Escalation(新設、CEO監査により独立段階化)

**修正内容**: 以前は4.3節(HIGH判定)・14章(低Confidence)それぞれの
説明に埋め込まれていたが、複数の前段階(Ambiguity Detection・Domain
Classification・Cognitive Revision)のいずれからも到達しうる、独立した
受け皿として明示する。

| 項目 | 内容 |
|---|---|
| 入力 | 到達元段階・到達理由(`escalation_reason`)・その時点までの部分的な結果(Intent/World/ApplicationPlan等、到達した段階まで) |
| 出力 | ユーザーへの確認質問(`ConfirmationRequest { questions, partial_result, resumable_from }`)。**Forge IR・HTTPレスポンス上は、通常の成功/失敗とは別の`status="needs_confirmation"`として扱う(3章・M005 Adapter Contractとの接続は次フェーズで設計、Non-Goal)** |
| 責務 | 4章・2.6節(Human Override)の原則が要求する「推定せず確認する」を、実際にパイプラインを停止させて実現する |
| 非責務 | 確認結果を受けての再開処理そのもの(ユーザー入力を受け取った後、`resumable_from`の段階から再開するという再開処理のトリガーは、本パイプラインの範囲だが、UI側の確認画面はNon-Goal) |
| 使用するルール | 2章「優先順位の統一」(本改訂の第2の修正点、4.3節・14.2節参照) |
| LLM使用条件 | Deterministic(どの段階から来たかに応じて、テンプレート化された確認質問を組み立てる。質問文言の自然さのみLLM補助) |
| 失敗時の扱い | 該当なし(この段階自体が「失敗時の受け皿」であるため、これ以上のフォールバック先は無い。安全に停止し、ユーザー入力を待つ) |
| 次段階への契約 | ユーザーからの追加情報を受けて、`resumable_from`が示す段階から再開する(実装はNon-Goal、今回は契約の形のみ定義) |
| 説明可能性 | `escalation_reason`(なぜ確認が必要になったか)、到達元段階 |

### 3.13 Forge IR Compilation

| 項目 | 内容 |
|---|---|
| 入力 | `ApplicationPlan`、`TemplateSelection`(Critic合格後) |
| 出力 | Forge Language JSON(`dict[str, Any]`、既存`forge_ai.core.compiler.
  ForgeIRDocument.to_json_dict()`と同じ最終形式) |
| 責務 | 既存の`forge_ai/core/compiler.py`の責務のまま(変更しない、19章参照) |
| 非責務 | Validation(次段階) |
| 使用するルール | 既存Compilerの決定的変換ロジック |
| LLM使用条件 | 既存通りDeterministic(タイトル決定のみProviderへ委譲、既存のforge_ai/ D2決定を維持) |
| 失敗時の扱い | 既存の安全側フォールバック(空要素なら"item"を補う等)を維持 |
| 次段階への契約 | 既存M005 Adapter Contractのまま(2.3節「dictはValidator合格して初めてForge Document」) |
| 説明可能性 | 既存の設計判断(forge_ai/ D1〜D7)を継承 |

### 3.14〜3.16 Validation / Repair / Quality Evaluation

既存(M004/M005で確定済み、`docs/spec/ADAPTER_CONTRACT_V1.md`)のまま
変更しない。M006はここに手を入れない(18章「M004/M005との責務境界」)。
Design Critic(3.10)とSchema Repair(3.15、旧番号3.13から本改訂で
再修正)を混同しないことが重要(12.3節「Cognitive RevisionとSchema
Repairの違い」)。


---

## 4. Ambiguity Detection(詳細)

### 4.1 分類(8種)

`missing_actor` / `missing_goal` / `missing_domain` / `missing_data` /
`missing_action` / `conflicting_requirements` / `multiple_possible_templates` /
`unsafe_assumption`。

### 4.2 3段階の重大度と扱い

| 重大度 | 意味 | 扱い |
|---|---|---|
| **LOW** | 安全な既定値で継続可能(例: Actorが明示されていないが「利用者本人」と仮定して問題ない) | 既定値を採用し、Decision Traceに「仮定した」ことを記録して続行する |
| **MEDIUM** | 複数の解釈がありうるが、いずれも致命的な誤りにはならない(例: 「買い物リスト」がShopping DomainかInventory Domainか) | 複数案を保持したまま仮設計(Application Planを複数候補生成)し、Design Criticの評価スコアで絞り込む。それでも決着しない場合はHIGHへ格上げする |
| **HIGH** | 致命的な誤りにつながりうる、またはプライバシー・安全に関わる(例: 「福祉支援記録」で対象者の個人情報範囲が不明) | **ユーザーへの確認を要求する**。Forgeは推定して進めない(2.6 Human Override原則) |

### 4.3 確認要求 vs 推定継続の判断基準(CEO監査により優先順位を統一)

**修正内容**: 以前は本節の「Domain分類のconfidenceが0.5未満ならHIGH」と、
14.2節の「confidence 0.3〜0.5未満はGenericへフォールバック」が、
0.3〜0.5の範囲で矛盾していた(どちらが優先されるか未定義だった)。
以下の**3段階の優先順位**として統一する(14.2節も本節を参照する形へ
修正した)。

#### 優先順位(上から順に評価し、最初に該当した規則を適用する)

1. **Privacy/Safety/Permissionに関係するHIGH ambiguity → confidenceの
   値に関係なく必ず確認する。** Domain分類のconfidenceがどれだけ高くても、
   このカテゴリに該当する曖昧さがあれば確認要求(Human Confirmation/
   Escalation、3.12節)を優先する。該当カテゴリ:
   - Non-Functional Requirements(8章)の`privacy`・`accessibility`分類に
     影響する曖昧さ。
   - welfare_support・health_tracking・reservationのように、対象が
     人物の機微情報・予約権限に関わるDomainでの`missing_data`・
     `unsafe_assumption`。
   - Domain定義の`forbidden_assumptions`(5.1節)に抵触しうる曖昧さ。
2. **Domain分類の`confidence`が閾値(暫定0.5)を下回る場合 →
   原則として確認する。** 上記1に該当しない場合の既定動作。
3. **低リスクかつ後から安全に変更可能な用途のみ → Genericで仮設計
   してよい。** 「低リスク」とは、上記1のいずれにも該当せず、かつ
   誤って進めても(a)個人・機微情報の露出が起きない、(b)後から
   Widget/State構造を壊さずにDomain/Templateを訂正できる、の両方を
   満たす場合を指す(例: task_management/genericのような、汎用的な
   記録・管理アプリ)。

複数のTemplate Familyで根本的にデータモデルが変わる場合(例: 「記録」が
単発Entryか継続的な状態管理かでState構造そのものが変わる)も、上記
優先順位の1(致命的誤りにつながりうる曖昧さ)に該当するものとして扱う。

以下はLOW(既定値で継続)としてよい(優先順位のいずれにも先立って
判定される、最も軽微なケース)。

- Actorが単数か複数か不明だが、単数と仮定しても後から拡張可能な設計
  (Widget/State構造を壊さずに複数Actor対応へ拡張できる)。
- 画面名・ラベルの表現揺れ(意味に影響しない)。

### 4.4 Ambiguity Detection自体が失敗した場合の扱い(CEO監査により新設)

**修正内容**: 以前は「検出処理自体が失敗した場合、`ambiguities=()`
(曖昧さ無しとして楽観的に継続)」としていたが、これは2.6節(Human
Override)に反する(検出できなかったことを、検出の結果「問題無し」と
静かに読み替えてしまうため)。以下へ置き換える。

#### 検出失敗時の状態

検出処理自体が例外・タイムアウト等で失敗した場合、`ambiguities=()`
とはせず、明示的に以下を返す。

```
AmbiguityReport {
  ambiguities: (),
  detection_status: "failed",      # 通常は "completed"
  overall_severity: "unknown",     # LOW/MEDIUM/HIGHのいずれでもない特別値
}
```

#### 検出不能時の分岐(4.3節の優先順位と同じ考え方を適用する)

Ambiguity Detectionの時点ではDomain Classification(3.4節)がまだ
実行されていないため、「Privacy/Health/Welfare関連かどうか」を
本格的なDomain分類では判定できない。そのため、**この分岐専用の、
軽量なキーワード予備チェック**(Domain Registry(5章)の各Domainの
`entities`/`forbidden_assumptions`とのキーワード一致のみを見る、
Domain Classificationの決定的スコアリングより単純な事前チェック)を
用いる。

| 予備チェック結果 | 扱い |
|---|---|
| privacy/health/welfare/reservation/permission関連のキーワードに
  一致する(welfare_support・health_tracking・reservation等の
  entities/forbidden_assumptionsと一致) | **Human Confirmation/
  Escalationへ進む、またはPrivacy要件が絡む可能性がある場合は安全停止する**(4.3節優先順位1と同じ扱い) |
| 一致しない、かつDomain候補が単純(task_management/shopping/diary/
  generic等、低リスク)と推測される | `warning`を付与した上で、**限定的に
  継続してよい**(例: Ambiguity Detectionの結果を「検出できなかった」と
  明記したまま後続段階へ渡し、後続の各段階(特に4.3節優先順位2の
  Domain confidence判定)がその`warning`を踏まえてより慎重に評価する) |

**この予備チェックはDomain Classification(3.4節)の代わりにはならない。**
あくまで「検出失敗時に、致命的なリスクを見逃して楽観継続しないための、
最小限の安全ネット」であり、正式なDomain判定は3.4節が担う。

---

## 5. Domain Model(詳細)

### 5.1 Domain構造

```
domain_id: str
name: str
actors: tuple[str, ...]
entities: tuple[str, ...]
common_actions: tuple[str, ...]
rules: tuple[str, ...]
constraints: tuple[str, ...]
recommended_patterns: tuple[str, ...]   # Template Familyへのヒント
forbidden_assumptions: tuple[str, ...]  # このDomainで勝手に仮定してはいけないこと
```

### 5.2 代表12 Domain

| domain_id | 代表actors | 代表entities | recommended_patterns |
|---|---|---|---|
| task_management | user, collaborator | task, deadline, priority | checklist, crud |
| shopping | user, family_member | item, price, store | checklist |
| household_budget | user | transaction, category, budget | tracker, dashboard |
| diary | user | entry, date, mood | memo, tracker |
| survey | respondent, administrator | question, response, respondent | form |
| schedule | user, participant | event, time_slot | calendar |
| inventory | user, staff | stock, location, threshold | tracker, catalog |
| reservation | customer, provider | slot, booking | calendar, form |
| welfare_support | recipient, caseworker, supervisor | case, record, service | crud, detail_list |
| education | student, teacher | lesson, assignment, grade | tracker, crud |
| health_tracking | user, caregiver | measurement, symptom, medication | tracker |
| generic | user | item | checklist |

`forbidden_assumptions`の例(welfare_support): 「対象者の同意なく第三者と
記録を共有してよいと仮定しない」「氏名以外の識別情報を必須項目にしない」。

### 5.3 Domain Knowledge保存先の比較・決定

| 方式 | 精度/表現力 | コスト | 速度 | 説明可能性 | 保守性 | テスト容易性 | オフライン |
|---|---|---|---|---|---|---|---|
| Python定義(dataclass) | ◎(型付き、IDE補完) | 無料 | 最速(import) | ◎(コード=文書) | ◎(既存forge_ai/と同じ形) | ◎(単体テストが書きやすい) | ◎ |
| JSON | ○ | 無料 | 速い | △(コメント不可) | △(手で書くとミスしやすい) | ○ | ◎ |
| YAML | ○ | 無料 | 速い | ○(コメント可) | ○ | ○ | ◎ |
| JSON Schema併用 | ◎(検証付き) | 無料 | 普通 | ○ | △(定義とSchemaの二重管理) | ○ | ◎ |
| Database | ◎(動的更新) | **有料/運用コスト** | 普通(I/O) | △ | △(マイグレーション管理必要) | △(DB無しでテスト困難) | ✗ |

**決定: Python定義を採用する**(forge_ai/core/domain_model.pyの既存方式を
そのまま拡張する)。理由: 初期段階で最優先すべき「無料・ローカル・テスト
容易性」を最も満たし、既存実装(`DomainRegistry`)との一貫性も保てる。
Databaseは「初期段階では」明確に不採用(コスト・オフライン対応の観点で
劣る。禁止事項26章「Database追加」とも整合)。

**将来の移行条件**: Domain数が大幅に増え(例: 50以上)、かつ非エンジニアが
Domain定義を編集する必要が生じた場合、YAML+ローダーへの移行を検討する
(ADR-002で詳細)。

---

## 6. World Model(詳細)

### 6.1 構造(UIを知らない)

```
Actors: tuple[Actor, ...]
Entities: tuple[Entity, ...]
Relationships: tuple[Relationship, ...]
Rules: tuple[Rule, ...]
Events: tuple[Event, ...]
States: tuple[StateDefinition, ...]
Permissions: tuple[Permission, ...]
Constraints: tuple[Constraint, ...]
```

forge_ai/既存の`World`(Actor/WorldObject/Relationship/Ruleの4フィールド)
との差分: `Events`・`States`・`Permissions`を新設する(ADR-002で理由を記録)。
既存4フィールドの意味は変更しない。

### 6.2 例: 病院予約(welfare_support系ではなくreservation Domain)

```
Actor: 患者、医師、管理者
Entity: 予約、診療科、時間枠
Relationship: 患者が予約を持つ / 医師が時間枠を提供する
Rule: 同一時間枠へ重複予約不可
Event: 予約作成、予約キャンセル、予約変更
State: 予約ステータス(仮予約/確定/キャンセル済み)
Permission: 患者は自分の予約のみ閲覧可、管理者は全予約閲覧可
Constraint: 時間枠は診療科の営業時間内のみ
```

画面・ボタン・Widgetという概念はここに一切登場しない(2.3節 Meaning
Before UI原則)。

---

## 7. Meaning Model(詳細)

### 7.1 構造

```
normalized_statement: str
semantic_units: tuple[SemanticUnit, ...]
referenced_entities: tuple[str, ...]
requested_operations: tuple[str, ...]
temporal_constraints: tuple[str, ...]
quantitative_constraints: tuple[str, ...]
privacy_implications: tuple[str, ...]
accessibility_implications: tuple[str, ...]
confidence: float
evidence_spans: tuple[EvidenceSpan, ...]
```

`SemanticUnit`は`{text, entity_ref: str | None, operation_ref: str | None}`
という形で、入力文の断片ごとにWorld Modelとの対応を保持する。対応付け
できない断片は`entity_ref=None`のまま残す(無理に紐付けない)。

---

## 8. Requirement Extraction(詳細)

### 8.1 8分類

Functional / Non-Functional / Data / Interaction / Validation / Privacy /
Accessibility / Open Questions。

### 8.2 Requirement構造

```
requirement_id: str
category: RequirementCategory  # 上記8分類
source: str          # どのMeaning/Intent項目から来たか
priority: Literal["must", "should", "could"]
confidence: float
mandatory: bool
rationale: str
```

Privacy/Accessibility要件は、`mandatory=True`かつ`priority="must"`が
既定(明示的にユーザーが不要と述べない限り、安全側に倒す)。

---

## 9. Planner(詳細)

### 9.1 ApplicationPlan構造(13フィールド)

```
app_goal: str
actors: tuple[str, ...]
entities: tuple[str, ...]
screens: tuple[ScreenSpec, ...]
screen_responsibilities: dict[str, str]
navigation_edges: tuple[tuple[str, str], ...]
state_requirements: tuple[str, ...]
action_requirements: tuple[str, ...]
validation_requirements: tuple[str, ...]
empty_state_requirements: tuple[str, ...]
error_state_requirements: tuple[str, ...]
unassigned_requirements: tuple[str, ...]
design_rationale: str
```

Plannerは`ScreenSpec`(画面ごとの抽象仕様)までを出力し、Widget個別配置
(text_field/button等)には踏み込まない(既存forge_ai/ Plannerと同じ境界)。

---

## 10. Template Selection(詳細)

### 10.1 11 Template Family

`checklist` / `form` / `memo` / `crud` / `dashboard` / `calendar` /
`tracker` / `catalog` / `detail_list` / `wizard` / `generic`。

### 10.2 評価基準(9項目)

Dominant user action / Data lifecycle / Number of entities / Need for
editing / Need for history / Need for aggregation / Need for navigation /
Need for validation / Need for multiple users。

### 10.3 Template定義テンプレート(各Templateがこの形を持つ)

```
template_id: str
applicable_when: tuple[str, ...]      # 適用条件
not_applicable_when: tuple[str, ...]  # 不適用条件
required_screens: tuple[str, ...]
recommended_state: tuple[str, ...]
recommended_actions: tuple[str, ...]
typical_failure_modes: tuple[str, ...]
fallback_templates: tuple[str, ...]   # 代替Template
```

### 10.4 例: checklist と form の判別

| 評価項目 | checklist | form |
|---|---|---|
| Dominant user action | 完了マーク・追加・削除 | 入力・送信 |
| Data lifecycle | 項目が独立して完了/未完了を遷移 | 1回の送信でまとまったデータが確定 |
| Need for validation | 低い(空でなければ良い程度) | 高い(必須項目・形式検証) |
| Need for multiple users | 低い | 中〜高(アンケート等) |

「項目ごとに独立した完了状態」が無く「入力項目が複数あり送信処理を要する」
場合はform、そうでない場合はchecklistを優先する、という決定的スコアリング
を第一候補とし、僅差の場合のみLLMでtie-breakする(16章)。

---

## 11. Design Critic(詳細)

### 11.1 14評価軸

Completeness / Simplicity / Intent Fidelity / Domain Consistency /
Navigation Coherence / State Completeness / Action Completeness /
Validation Coverage / Empty State Quality / Error Recovery /
Accessibility / Privacy / Explainability / Runtime Safety。

forge_ai/既存`QualityScore`(6軸)との関係: 既存6軸(correctness/
completeness/simplicity/runtime_safety/explainability/maintainability)
はForge IR生成**後**の静的な品質測定であり、Design Criticは
`ApplicationPlan`(IR生成**前**)に対する、より広い14軸の設計品質評価
である。両者は評価対象(Plan vs IR)も評価タイミングも異なるため、
統合せず併存させる(ADR-004)。

### 11.2 CriticReport構造

```
issues: tuple[CriticIssue, ...]
overall_score: float
release_ready: bool
```

```
CriticIssue {
  issue_id: str
  severity: Literal["blocking", "major", "minor"]
  evidence: str
  recommended_fix: str
  affected_component: str
  auto_fixable: bool
}
```


---

## 12. Self-Revision Loop

### 12.1 フロー

```
Plan → Critic → Revision → Critic → (合格 or 上限到達) → 次段階
```

### 12.2 決定事項

| 項目 | 決定 |
|---|---|
| 最大Revision回数 | **2回**(既存のSchema Repair上限と同じ値に揃え、共通指示書6.5節の精神を踏襲する。ただし別カウンタで管理する、12.4節) |
| 同じ問題の再発検出 | 直前のCriticReportと今回のCriticReportで、同一`issue_id`(または同一`affected_component`+`category`)が再度blockingで出た場合、「再発」として記録し、3回目を待たずその時点で人間確認へ切り替える |
| スコアが改善しない場合の停止条件 | `overall_score`が前回より悪化、または改善幅が閾値(暫定0.05)未満の場合、Revisionを打ち切る |
| 人間確認へ切り替える条件 | 上限到達後もblocking issueが残る、または同一問題が再発した場合 |
| Validator Repairとの責務差 | 12.3節 |

### 12.3 Cognitive RevisionとSchema Repairの違い(重要)

| | Cognitive Revision(本Loop) | Schema Repair(既存M004/M005) |
|---|---|---|
| 対象 | `ApplicationPlan`(IR化される前) | Forge IR(JSON化された後) |
| 目的 | 設計として良いか(Design Critic基準) | 仕様上正しいか(Validator基準) |
| 実行者 | Design Critic + Revision | Validator + `forge_ai.RepairEngine` |
| 呼ばれる順序 | Forge IR Compilation**より前** | Forge IR Compilation**より後** |

両者は別のループであり、カウンタも独立する(混同しない。15章原則)。

### 12.4 二重ループ防止の設計原則

既存M005で発見した「Repair二重ループ問題」(ADR、`docs/DECISIONS.md` D59)
と同じ轍を踏まないため、Cognitive Revision LoopとSchema Repair Loopは
**それぞれ独立したカウンタを持ち、どちらか一方が他方の内部で暗黙に
リトライを増やす構造にしない**ことを、実装時の必須要件として明記する。

---

## 13. LLM使用方針(14 Transformation Stage)

| 段階 | 分類 | 理由 |
|---|---|---|
| Input Normalization | Deterministic(既定) / Hybrid(例外時) | 文字列処理は決定的に可能。著しい崩れのみLLM |
| Ambiguity Detection | Hybrid | 欠落検出はRule、意味的曖昧さの判定はLLM |
| Intent Recognition | Hybrid | 候補抽出はRule、自由記述の要約・統合はLLM |
| Domain Classification | Rule + LLM fallback | スコアリングで決定、僅差のみLLM |
| World Model Construction | Deterministic(既定) | Domain定義の機械的展開。特殊Entity追加のみLLM補助 |
| Meaning Model | Hybrid | 直接一致はRule、比喩・言い換えはLLM |
| Requirement Extraction | Hybrid | Domain由来の要件はRule、自由記述からの抽出はLLM |
| Application Planning | Hybrid | 画面candidate生成はRule、統合判断はLLM |
| Template Selection | Rule-based scoring + LLM tie-break | 13章のスコアリングが基本、僅差のみLLM |
| Design Critic | Deterministic checks + LLM semantic review | 構造チェックはRule、意味的一貫性はLLM |
| Self-Revision | Hybrid | 修正方針の生成はLLM、適用可否の判定はRule(Criticの再評価) |
| Forge IR Compilation | Deterministic(既存踏襲) | 既存forge_ai/ Compilerの方針を継続 |
| Validation | Deterministic(既存) | 変更なし |
| Repair(Schema) | Deterministic中心(既存) | 変更なし |
| Quality Evaluation | Deterministic(既存) | 変更なし |

### 13.1 LLMへ渡す情報の最小化

- 各段階のLLM呼び出しは、その段階が必要とする情報のみを渡す
  (例: Template SelectionのLLM tie-breakには`ApplicationPlan`の
  該当画面情報のみ渡し、他画面・他Actorの詳細は渡さない)。
- 個人情報・機密情報(Privacy Requirements該当項目)は、明示的に
  そのLLM呼び出しの目的に必要でない限りPromptへ含めない。
- forge_ai/既存の`Prompt`(stage/system/instruction/context)という
  構造化設計は維持し、文字列連結でcontextを膨張させない。

---

## 14. Confidence Model

### 14.1 6種の信頼度

`intent_confidence` / `domain_confidence` / `entity_confidence` /
`planning_confidence` / `template_confidence` / `overall_confidence`
(各段階のconfidenceの重み付き平均、重みは実装時に調整可能なパラメータとする)。

### 14.2 低信頼度時の挙動決定(CEO監査により4.3節の優先順位と統合)

**修正内容**: 以前は本節が独自に「confidence 0.3〜0.5未満はGenericへ
落とす」という閾値表を持ち、4.3節の「Domain confidenceが0.5未満なら
HIGH(確認要求)」と、0.3〜0.5の範囲で矛盾していた。以下のように、
**4.3節の3段階優先順位を先に適用し、その上でconfidence帯を評価する**
という順序へ統合する(独立した閾値表としては扱わない)。

#### 評価順序

1. まず4.3節の優先順位1(Privacy/Safety/Permission関連のHIGH
   ambiguity)に該当するかを判定する。該当すれば、confidenceの値に
   関わらずHuman Confirmation/Escalation(3.12節)へ進む。
2. 該当しない場合、`overall_confidence`(14.1節)を以下の帯域で評価する。

| 信頼度帯 | 挙動 |
|---|---|
| 0.8以上 | そのまま継続 |
| 0.5〜0.8未満 | 複数案を保持(Application Planを複数生成し、Design Criticスコアで選択、4.2節MEDIUM相当) |
| 0.5未満 | **4.3節優先順位2の適用として、原則Human Confirmation/Escalationへ進む。** ただし4.3節優先順位3(低リスクかつ後から安全に変更可能)の条件を満たす場合に限り、確認を経ずGenericへ仮設計してよい(以前の「0.3〜0.5未満は無条件でGeneric」という扱いを廃止し、低リスク条件を必須にした) |

**0.3という以前の追加閾値(「0.3未満は生成拒否」)は廃止する。** 0.5未満は
一貫して「原則確認、低リスク時のみGeneric仮設計」という1つのルールで
扱い、0.3/0.5という2段階の閾値を持たない(閾値が2つあること自体が
以前の矛盾の一因だったため、閾値は0.5・0.8の2つに整理した)。

数値の根拠: 現時点で実運用データが無いため、この閾値は**暫定**であり、
実際のCriticスコア・ユーザーフィードバックの蓄積(16章)を踏まえて
実装時・運用開始後に再調整することを前提とする(事実と推測の分離:
これは提案であり確定値ではない)。

### 14.3 根拠を伴う信頼度

各confidenceは単独の数値ではなく、`ConfidenceRecord {value, basis:
tuple[str, ...]}`という形で、何を根拠にその値になったかを保持する
(例: `intent_confidence=0.6, basis=("required_actionsが1つのみ抽出",
"actorsが明示されていない")`)。

---

## 15. Explainability Record(Decision Trace)

### 15.1 構造

```
DecisionTrace {
  decision_id: str
  stage: str              # Cognitive Pipelineの14 Transformation StageまたはTerminal Outcomeのいずれか
  decision: str
  reason: str
  evidence: tuple[str, ...]
  alternatives: tuple[RejectedAlternative, ...]
  confidence: float
  rule_used: str | None
  provider_used: str | None
  timestamp: str
}

RejectedAlternative { option: str, reason_rejected: str }
```

### 15.2 例

```
decision_id: "d-2026-07-15-0001"
stage: "template_selection"
decision: "Template = Form"
reason: "入力項目が複数あり、必須検証と送信処理が必要"
alternatives: [
  { option: "Checklist", reason_rejected: "項目ごとに独立した完了状態を管理する用途ではない" }
]
confidence: 0.82
rule_used: "template_scoring_v1"
provider_used: "mock"
```

### 15.3 保存方針

Decision Traceは、パイプライン全段階を通して1つのリストへ追記していく
(各段階が自分のDecisionTraceエントリを積む)。最終的に`ApplicationPlan.
design_rationale`・HTTPレスポンスの`diagnostics`(既存M005 Adapter
Contractの`intent_ir`/`plan_ir`/`conversion_warnings`と同じ思想)経由で
可視化する。

---

## 16. Learning-Ready Design

今回、学習機能自体は実装しない。ただし将来蓄積できるよう、以下のデータを
「保存する場合の形」だけ設計する(保存の実装自体はNon-Goal、26章)。

- User corrections(ユーザーがForgeの提案を修正した内容)
- Rejected plans(候補になったが採用されなかったApplicationPlan)
- Selected alternatives(Ambiguity/Template選択で採用された案)
- Validation failures(Schema Validator不合格の履歴)
- Repair history(既存M004 RepairEngineの履歴)
- Critic issues(Design Criticが指摘した内容)
- Final accepted design(最終的にユーザーが受理したForge IR)
- Runtime failures(Flutter Runtime側で発生したエラー、将来の接続点)

### 16.1 プライバシー・匿名化・opt-in方針

- 既定は**保存しない**(方針10章のプライバシー原則を継続)。
- 保存する場合は、ユーザーの明示的なopt-inを要件とする。
- 保存対象から、Privacy Requirements(11章)に該当する入力内容は
  匿名化・除去した上で保存する(個人を特定しうる文字列は、Decision
  Traceの`evidence`であっても保持しない)。
- プロジェクト単位・ユーザー単位で分離し、削除可能・学習対象からの
  除外可能な設計を前提とする(共通指示書10章の既存原則を継承)。

---

## 17. Failure Modes(14種)

各Failure Modeについて「原因・検出方法・予防策・復旧方法・テスト方法」
を記載する。

### 17.1 Domain誤分類
- 原因: Domain Registryのcommon_actions/entitiesが実際の入力語彙と
  乖離している。
- 検出方法: Domain Classificationの`confidence`が閾値未満。
- 予防策: Domain定義のentitiesを、実際の想定入力例(25章の6例)で
  事前検証する。
- 復旧方法: `candidate_domains`の次点を提示し、ユーザーに選ばせる。
- テスト方法: 25章の6例それぞれで、期待Domainと一致するかの回帰テスト。

### 17.2 Intent過剰推定
- 原因: LLMが入力に無い要求を「補完」してしまう。
- 検出方法: `evidence`が空、または入力文中に対応箇所が無いフィールドの検出。
- 予防策: Intent Recognitionの各フィールドに`evidence`を必須とし、
  `evidence`が無い抽出結果は`confidence`を強制的に下げる。
- 復旧方法: 低confidenceフィールドをOpen Questionsへ差し戻す。
- テスト方法: 意図的に情報の少ない入力を与え、過剰な断定が起きないことを確認する契約テスト。

### 17.3 必須要件の欠落
- 原因: Requirement Extractionの分類漏れ。
- 検出方法: Design Criticの`Completeness`軸。
- 予防策: Domain Registryの`rules`/`constraints`からの機械的導出(8.2節)を優先する。
- 復旧方法: Self-Revision Loopで指摘・補完する。
- テスト方法: Domain定義ごとに「最低限含まれるべき要件」のゴールデンテスト。

### 17.4 不要な画面増加
- 原因: Application Planningが要件ごとに画面を分割しすぎる。
- 検出方法: Design Criticの`Simplicity`軸。
- 予防策: Template Selectionの`required_screens`を上限の目安にする。
- 復旧方法: Self-Revision Loopで画面統合を提案する。
- テスト方法: 25章の例で「画面数が想定範囲内か」の回帰テスト。

### 17.5 Template誤選択
- 原因: 評価基準9項目のスコアが僅差、またはLLM tie-breakの誤判断。
- 検出方法: Design Criticの`Domain Consistency`軸、typical_failure_modes
  (10.3節)との一致。
- 予防策: 決定的スコアリングを常に先に行い、LLMは僅差のみに限定する(16章)。
- 復旧方法: `fallback_templates`(10.3節)へのフォールバック。
- テスト方法: 10.4節のような判別境界例をゴールデンテスト化する。

### 17.6 Action不足 / 17.7 State不足
- 原因: Requirement ExtractionのFunctional Requirementsが
  Application Planningの`action_requirements`/`state_requirements`へ
  正しく写像されない。
- 検出方法: Design Criticの`Action Completeness`/`State Completeness`軸。
- 予防策: 写像ロジックを決定的にし、写像漏れを`unassigned_requirements`
  として可視化する(捨てない、9.1節)。
- 復旧方法: Self-Revision Loop。
- テスト方法: 要件→Action/State写像の単体テスト。

### 17.8 Navigation不整合
- 原因: `navigation_edges`が実際の`screens`と矛盾する(存在しない画面への遷移等)。
- 検出方法: Design Criticの`Navigation Coherence`軸(決定的チェックが可能)。
- 予防策: Application Planning出力時に、edgeの両端が`screens`に存在することを構造的に保証する。
- 復旧方法: Self-Revision Loop、または決定的な自動修正(auto_fixable=true)。
- テスト方法: 不正なedgeを含むPlanを人工的に与え、Criticが検出することを確認する。

### 17.9 Privacy要件無視 / 17.10 Accessibility要件無視
- 原因: Requirement Extractionが検出したPrivacy/Accessibility要件が
  Application Planningで反映されない。
- 検出方法: Design Criticの`Privacy`/`Accessibility`軸。
- 予防策: これらの要件は`mandatory=True`が既定(8.2節)であり、
  Application Planningは`mandatory`要件を無視した場合に構造的エラーとする。
- 復旧方法: Self-Revision Loop(blocking扱い、通常のmajor/minorより優先)。
- テスト方法: Privacy要件を含む入力例(福祉支援記録)での回帰テスト。

### 17.11 Providerごとの出力差
- 原因: LLM Provider(OpenAI/Claude/Gemini/OSS/Mock)ごとの応答の質・
  形式の違い。
- 検出方法: 同一入力を複数Providerで実行し、Design Criticスコアの
  分散を測定する(将来の評価基盤、Non-Goal)。
- 予防策: 16章「Rule Before Prompt」により、LLMが関与する範囲を最小化する。
- 復旧方法: 該当なし(設計段階の予防が中心)。
- テスト方法: Provider非依存性を検証する契約テスト(forge_ai/の既存
  `MockProvider`ベーステストと同じ考え方を、将来複数Providerへ拡張する)。

### 17.12 Revision無限ループ
- 原因: Self-Revision Loopの停止条件が機能しない実装ミス。
- 検出方法: 12.2節の停止条件(最大回数・スコア改善なし・再発検出)。
- 予防策: 12.4節の独立カウンタ設計。
- 復旧方法: 上限到達で強制的に人間確認へ。
- テスト方法: 「絶対に直らない問題」を人工的に与え、上限で必ず停止する
  ことを確認する契約テスト(既存M005の`test_repair_exhausted_still_
  invalid_raises_forge_validation_error`と同種のテスト設計)。

### 17.13 Confidence過信
- 原因: 実際には不確実な判断に高いconfidenceを割り当ててしまう。
- 検出方法: 実際のユーザー修正率(Learning-Ready Designで蓄積、将来)との乖離。
- 予防策: `evidence`を伴わないconfidenceの引き上げを禁止する(17.2と同じ機構)。
- 復旧方法: 該当なし(運用データ蓄積後の閾値再調整、14.2節)。
- テスト方法: 現時点ではテスト不能(将来のユーザーデータが必要、Non-Goal)。

### 17.14 Generic fallback乱用
- 原因: 曖昧さ・低confidenceのたびに安易にGenericへ倒し、Forgeの
  価値(Domain特化の提案)が失われる。
- 検出方法: Generic Domain/Templateの採用率をDecision Traceから集計する(将来)。
- 予防策: 14.2節の閾値を「安易に下げない」よう、閾値変更にはCEO承認を要件とする。
- 復旧方法: 該当なし。
- テスト方法: 25章の6例が、少なくとも1つはGeneric以外のDomain/Templateに
  正しく分類されることを確認する回帰テスト。


---

## 18. M004/M005との責務境界(維持)

M006はM004(forge_ai/)のCognitive Architecture強化であり、M005
(`backend/app/ai/runtime/`)の責務は変更しない。

| M005が引き続き担うもの(変更しない) | M006が扱うもの(M004内部) |
|---|---|
| HTTP | Intent Recognition |
| Provider解決(`ProviderRouter`) | Domain Classification |
| Validator呼び出し | World Model Construction |
| Schema Repair制御(`RepairEngine`呼び出し回数) | Meaning Model |
| Error Envelope | Requirement Extraction |
| Diagnostics(`conversion_warnings`等) | Application Planning |
| | Template Selection |
| | Design Critic(Cognitive、新設) |
| | Self-Revision Loop(新設) |

**M005へ認知ロジックを追加してはならない**という制約を守るため、本設計の
新規コンポーネント(Ambiguity Detection・Design Critic・Self-Revision
Loop等)は、すべて`forge_ai/`(M004)内に実装する前提とする(実装は
今回行わない、Non-Goal)。

---

## 19. Nativeディレクトリの扱い

`backend/app/ai/native/`は引き続きExperimental。今回変更していない
(タイムスタンプで確認可能)。

M006設計の一部(例: ルールベースのIntent認識)が、既に`backend/app/ai/
native/_01_intent/intent_recognizer.py`等に類似の実装として存在する
可能性がある。**今回、これらのコードの内容を精査・比較・採用判断は
行っていない**(実装作業ではなく設計作業であるため、コードレベルの
詳細比較は本ドキュメントのスコープ外とした)。将来M007以降で実装に
入る際、`backend/app/ai/native/`を実装の土台として使うかどうかは、
`docs/spec/FORGE_AI_ARCHITECTURE_V1.md`(Architecture Freeze)の
既定方針通り、**まず責務・品質・重複を監査し、CEO承認を得てから**
判断する。本設計書は、その判断を先取り・既成事実化しない。

---

## 20. 設計方式比較(Option A/B/C)

| 評価軸 | Option A: Rule-Based中心 | Option B: LLM中心 | Option C: Hybrid(本設計の採用案) |
|---|---|---|---|
| 精度 | Domain定義済みの範囲では高いが、未知パターンに弱い | 未知パターンにも対応しやすいが、幻覚・過剰推定のリスク | Rule部分は安定、LLM部分のみ不確実性を局所化 |
| コスト | 最安(推論コスト無し) | 最高(全段階でLLM呼び出し) | 中(必要段階のみLLM) |
| 速度 | 最速 | 最遅(複数回のLLM往復) | 中(Rule段階は高速、LLM段階のみ待機) |
| 説明可能性 | 最高(ルールがそのまま説明になる) | 低い(LLM推論の内部は追跡困難) | 高い(Rule部分は完全説明可能、LLM部分もDecision Traceで根拠記録) |
| Provider依存 | 無し | 高い(Providerごとの品質差が結果に直結) | 低い(2.5節、LLMは補助的役割に限定) |
| 保守性 | Domain/Rule追加のたびにコード変更が必要 | プロンプト調整のみで済むことが多いが、挙動の予測が困難 | Rule変更は明示的、LLM部分は限定的なので影響範囲が狭い |
| テスト容易性 | 最高(決定的、既存forge_ai/のテスト資産と親和性が高い) | 低い(LLM出力の非決定性、Mock頼みになる) | 高い(Rule部分は既存同様にテスト可能、LLM部分もMockで検証可能) |
| 日本語対応 | Domain定義次第(手動整備が必要) | LLM次第(Providerにより差) | Rule部分で最低限を保証しつつ、LLMで補強 |
| 拡張性 | 新Domain追加のたびに大きな実装コストがかかりうる | 新Domainへの適応はしやすいが、精度が不安定 | Domain Registry拡張(Rule)+LLM補助という組み合わせで、段階的に拡張しやすい |
| オフライン対応 | ◎(Providerが無くても動作可能) | ✗(LLM無しでは機能しない) | ◎(Mock Providerのみでも、Rule部分中心に一定の品質を保てる) |

**結論**: Hybrid(Option C)を採用する。理由は上表の通り、既存forge_ai/
の資産(Rule-basedな決定的処理の蓄積、80テスト)を活かしながら、LLMの
強みを補助的な範囲に限定できるため。ただし「結論ありきにしない」という
指示に従い、Option A・Bが優位な観点(Aの速度・オフライン対応の完全性、
Bの未知パターン対応力)も上表に明記した。ADR-001で詳細を記録する。

---

## 21. 図・ADR・完全トレース例(別ファイル)

- 図(9種、Mermaid): `docs/diagrams/`
- ADR(8件、ADR-008を本改訂で追加): `docs/adr/`
- 完全トレース例(6件): `docs/examples/`

以降の章(完了条件・自己レビュー)は本ファイル末尾に記載する。

---

## 22. 完了条件チェックリスト(CEO監査による4点修正を反映)

**CEO監査(2026-07-15)による4点の修正**: ①Cognitive Pipelineの段階数
不一致(14→16)を解消(3章)。②Confidence/Ambiguityの優先順位を統一
(4.3節・14.2節)。③Ambiguity Detection失敗時の楽観的継続を廃止(4.4節)。
④Application Planning/Template Selectionの循環依存を解消し、
Preliminary/Final 2フェーズへ明示的に分割(3.8節・3.9節・ADR-008新設)。

| 条件 | 状態 |
|---|---|
| Cognitive Pipeline確定 | ✅ 3章(**14 Transformation Stage + 1 Terminal Outcome**、各9項目。「16段階」という表記は撤回し、性質を区別した数え方へ改めた) |
| 全モジュール責務確定 | ✅ 3章の各表 |
| Input/Output契約定義 | ✅ 3章の各表 |
| Intent Model確定 | ✅ 3.3節・7章 |
| Domain Model確定 | ✅ 5章 |
| World Model確定 | ✅ 6章 |
| Planner契約確定 | ✅ 9章、**Preliminary/Final Template Selectionとの境界を明確化(3.8節)** |
| Template Selection方式確定 | ✅ 10章、**Final Template Selectionとして3.9節で再定義** |
| Critic方式確定 | ✅ 11章 |
| Revision Loop確定 | ✅ 12章、**Planning⇔Template Selection再計画とのカウンタ共有を明記(12.4節・ADR-008)** |
| Confidence Model確定 | ✅ 14章、**4.3節の優先順位と統合し矛盾を解消** |
| Decision Trace確定 | ✅ 15章 |
| LLM使用境界確定 | ✅ 13章 |
| M004/M005責務境界維持 | ✅ 18章 |
| 6例の完全トレース | ✅ `docs/examples/`(6ファイル、CEO監査を受け該当箇所を更新) |
| Failure Mode分析 | ✅ 17章(14種) |
| ADR完成 | ✅ `docs/adr/`(**8件**、ADR-008を本改訂で追加) |
| 新規コード0行 | ✅ 本Taskで追加・修正したのはMarkdownドキュメントのみ |

---

## 23. 自己レビュー(提出前チェック)

| 観点 | 所見 |
|---|---|
| Architecture | Cognitive Pipelineの14 Transformation Stageが、既存M004(forge_ai/)のモジュール構成(domain_model/world_model/meaning_model/intent_model/planner/compiler)と自然に対応しており、既存資産を活かした拡張になっている。 |
| AI Design | Rule Before Promptにより、LLM依存箇所を最小化。Provider非依存性を維持。 |
| DDD | Domain Model(5章)・World Model(6章)がドメイン駆動設計の語彙(Actor/Entity/Relationship/Rule)に沿っており、UIから独立している。 |
| Explainability | Decision Trace(15章)により全段階の判断根拠を追跡可能。 |
| Provider Independence | 20章の比較・13章のLLM使用方針により、Provider差の影響範囲を限定。 |
| Privacy | 11章のPrivacy Requirements、16章の匿名化・opt-in方針で対応。 |
| Accessibility | 11章のAccessibility Requirements、11.1節のCritic軸で継続的に検証。 |
| Testability | 既存forge_ai/と同じくRule部分は決定的でテストしやすい。LLM部分もMock前提でテスト可能な設計。 |
| Maintainability | Domain Knowledge(Python定義)・Template定義がいずれも構造化されており、追加・変更が局所化される。 |
| Scalability | Domain/Template追加は既存Registryパターンの拡張で対応可能(5.3節)。 |
| Runtime Safety | Self-Revision Loop・Schema Repairとも上限付き(12章)、無限ループを構造的に防止。 |
| Failure Recovery | 17章で14種のFailure Modeそれぞれに検出・予防・復旧・テスト方法を記載。 |
| Cost | 20章の比較で、Hybrid方式がLLM呼び出し回数を最小化しコストを抑えることを明記。 |
| Performance | 同上、Rule部分は既存同様高速。LLM呼び出し回数の最小化(13.1節)で速度も確保。 |
| Future Learning | 16章でLearning-Ready Designを設計(実装はNon-Goal)。 |

**事実と推測の分離の明記**: 本ドキュメントの数値(Confidence閾値
0.8/0.5(本改訂で0.3を廃止し2閾値へ整理、14.2節)、Revision改善閾値
0.05等)は、実運用データが無い現時点での**提案**であり、確定した仕様
ではない。実装・運用開始後に、実際のCriticスコア分布・ユーザー修正率
等のデータに基づき再調整することを前提とする。
