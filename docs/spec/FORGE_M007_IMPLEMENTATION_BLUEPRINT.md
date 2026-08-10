# Forge M007 Implementation Blueprint

**Status: ARCHITECTURE → IMPLEMENTATION TRANSITION — 実装コード0行**
**Ref:** FORGE-MILESTONE-007 PREPARATION（v1.3、Executable Contract Finalization）
**日付:** 2026-07-15　**担当:** Principal Engineer / Architect（Claude）
**前提:** `docs/spec/FORGE_COGNITIVE_ARCHITECTURE_V2.md`(M006、CEO承認済み)

本ドキュメントは設計のみである。新規Python/Dartコードは1行も追加して
いない。既存コード(`forge_ai/`・`backend/app/ai/`・Flutter Runtime)も
一切変更していない。実装はM007で、本設計に対するCEO承認を得てから
開始する。

**本版(v1.3)について**: これまで3回のCEO実物監査を経て、都度
本文中に「CEO実物監査により訂正」という注記を挿入する形で更新して
きたが、この方式は文書内に新旧の記述が混在し、かえって読みにくく
なる副作用を生んだ(4回目監査で指摘)。v1.3は、**現在採用している
設計のみを本文に記述し、過去に却下・訂正した設計は末尾の「16. 設計の
変遷(Superseded Design History)」へ集約する**という構成へ全面的に
書き直した。

---

## 0. 前提として再確認した既存事実

- `forge_ai/core/pipeline.py`の`run_pipeline(user_text: str, provider:
  AIProvider, *, domain_registry=None, world_builder=None) ->
  PipelineResult`が、M005(`backend/app/ai/runtime/prompt_pipeline.py`)
  から**現在実際に**呼ばれている(Facade)。この関数のシグネチャ・
  戻り値の形は変更しない。
- `forge_ai/contracts/interfaces.py`に、`MeaningExtractorProtocol`・
  `IntentBuilderProtocol`・`PlannerProtocol`・`CompilerProtocol`・
  `RepairEngineProtocol`・`QualityEngineProtocol`・
  `DomainResolverProtocol`・`WorldModelBuilderProtocol`の8 Legacy
  Protocolが既に存在する(既存`run_pipeline()`専用、シグネチャ変更なし)。
- `backend/app/ai/runtime/pipeline_errors.py`に既に`PlanningError`
  (`category="planning_error"`)・`ProviderError`
  (`category="provider_error"`)が存在する。既存の例外捕捉順序は
  「`NotImplementedError`→`ProviderError`」「それ以外の`Exception`→
  `PlanningError`」(6.3節で詳細)。
- forge_ai/は現在80テスト全合格、Backend/Flutter/実LLMへの依存が無い。

---

## Task 1: 実装ディレクトリ設計

### 1.1 方針: 既存ファイルは一切移動しない

`forge_ai/core/domain_model.py`・`world_model.py`・`meaning_model.py`・
`intent_model.py`・`planner.py`・`compiler.py`・`pipeline.py`は、
**位置を変更しない**(import pathを壊すと、既存80テスト・M005の
Facade呼び出しの双方に影響するため)。M006が要求する新しい認知能力は、
`core/`配下に**新設する6つのサブディレクトリ**へ追加する。

### 1.2 新設ディレクトリ(6つ)

```
forge_ai/core/
  domain_model.py            [既存、拡張(1.3節)]
  world_model.py               [既存、拡張]
  meaning_model.py              [既存、拡張]
  intent_model.py                [既存、拡張]
  planner.py                      [既存、拡張]
  compiler.py                      [既存、無変更]
  pipeline.py                       [既存、無変更。新規run_cognitive_pipeline()を同ファイルへ追加]

  input_processing/                [新設 1/6]
    __init__.py
    normalizer.py                   Input Normalization
    ambiguity_detector.py            Ambiguity Detection

  understanding/                    [新設 2/6]
    __init__.py
    intent_recognizer.py             新規Cognitive実装。`CognitiveIntentRecognizerProtocol`を実装する
    domain_classifier.py              新規Cognitive実装。`CognitiveDomainClassifierProtocol`を実装する(5章で詳細)
    world_builder.py                   新規Cognitive実装。`CognitiveWorldBuilderProtocol`を実装する
    meaning_extractor.py                新規Cognitive実装。`CognitiveMeaningExtractorProtocol`を実装する
    requirement_extractor.py             新規。`RequirementExtractorProtocol`を実装する

  planning/                          [新設 3/6]
    __init__.py
    application_planner.py             新規Cognitive実装。`CognitivePlannerProtocol`を実装する
    template_selector.py                新規。`TemplateSelectorProtocol`(select_preliminary/select_final両方)を実装する

  critic/                              [新設 4/6]
    __init__.py
    design_critic.py                     新規。`DesignCriticProtocol`を実装する
    revision_engine.py                    新規Cognitive Revision。`RevisionEngineProtocol`を実装する(既存repair/repair_engine.pyとは別、6章の区別を維持)

  confirmation/                         [新設 5/6]
    __init__.py
    escalation_handler.py                 新規。`EscalationHandlerProtocol`を実装する

  orchestration/                        [新設 6/6]
    __init__.py
    cognitive_context.py                  Task2
    cognitive_dependencies.py               Task3.1(依存注入契約)
    pipeline_orchestrator.py                 Task3.2〜3.4
    outcomes.py                               Task3.5(Outcome3型)
    errors.py                                  Task6
```

### 1.3 既存ファイルの「拡張」の意味

「拡張」とは、既存の公開クラス・関数のシグネチャを変えず、既存データ
クラスへ**既定値を持つ新規フィールドを追加する**ことを指す
(`backend/app/ai/foundation/interfaces.py`の`IntentIR`/`PlanIR`拡張と
全く同じ手法。既に実績のある後方互換パターン)。

```python
# forge_ai/core/intent_model.py(既存、拡張後のイメージ。今回は書かない)
@dataclass(frozen=True)
class Intent:
    goal: str
    required_concepts: tuple[str, ...] = ()
    required_actions: tuple[str, ...] = ()
    constraints: tuple[str, ...] = ()
    secondary_goals: tuple[str, ...] = ()
    actors: tuple[str, ...] = ()
    required_data: tuple[str, ...] = ()
    success_conditions: tuple[str, ...] = ()
    prohibited_behaviors: tuple[str, ...] = ()
    open_questions: tuple[str, ...] = ()
    confidence: float = 1.0
    evidence: tuple[str, ...] = ()
```

```python
# forge_ai/core/planner.py(既存、拡張後のイメージ。今回は書かない)
@dataclass(frozen=True)
class ApplicationPlan:
    title: str
    screens: tuple[ScreenPlan, ...] = ()
    data_entities: tuple[str, ...] = ()
    primary_flow: tuple[str, ...] = ()
    unassigned_requirements: tuple[str, ...] = ()  # 破棄せず保持(3章注記3)
```

`understanding/intent_recognizer.py`は、この拡張された`Intent`型を
実際に埋める処理を担う。**`intent_recognizer.py`は既存`IntentBuilder`
(Legacy Protocol)を内部でも一切呼び出さない**(4章の分離原則)。
`intent_model.py`自体は「データの形」の置き場に留める。

### 1.4 backend側Templateとの関係(誤解防止のため明記)

`backend/app/ai/generators/templates/`(Mock Generator用、
checklist/memo/form)は、**M006/M007のTemplate Selectionとは
別概念である**。前者はキーワードマッチによる決定的なJSON生成テンプレート
(現行の生成フロー)、後者はForge Language 11 Template Family
(checklist/form/memo/crud/dashboard/calendar/tracker/catalog/
detail_list/wizard/generic)からの設計判断である。今回は統合しない
(Non-Goal)。

---


## Task 2: Cognitive Context設計

### 2.1 構造

Cognitive Pipeline(3章)を通して流れる、単一のImmutableなContext
オブジェクト。

```python
# forge_ai/core/orchestration/cognitive_context.py(イメージ、今回は書かない)

@dataclass(frozen=True)
class CognitiveContext:
    # 常に存在(Pipeline開始時に確定)
    raw_input: str
    started_at: str  # ISO8601

    # 各Transformation Stage(3.1節)が完了するたびに埋まる(未完了はNone)
    normalized_input: NormalizedInput | None = None
    ambiguity_report: AmbiguityReport | None = None
    intent: Intent | None = None
    domain_classification: DomainClassification | None = None
    world: World | None = None
    meaning: ExtractedMeaning | None = None
    requirements: RequirementSet | None = None
    preliminary_candidates: tuple[str, ...] | None = None
    plan: ApplicationPlan | None = None
    template_selection: TemplateSelection | None = None
    critic_report: CriticReport | None = None

    # Pipeline全体を通して蓄積
    decision_trace: tuple[DecisionTrace, ...] = ()
    confidence_snapshot: ConfidenceSnapshot | None = None

    # ループ制御(6章、Preliminary/Final再計画とCognitive Revisionが共有する単一カウンタ)
    revision_attempt: int = 0
    max_revision_attempts: int = 2
```

**`ir`(Forge IR)・`initial_quality`はContextへ含めない**(Task9.2で
理由を説明する。これらはPipelineの「最終出力」であり、途中経過を表す
Contextの責務とは区別する)。

### 2.2 更新方針: Immutable、`with_*`メソッド経由でのみ「更新」

`CognitiveContext`自体は`frozen=True`で直接の変更を禁止する。各段階は
「現在のContextを受け取り、自分の結果を追加した**新しい**Context
インスタンスを返す」という形で処理する(`dataclasses.replace`を薄く
ラップする)。全フィールドに対応する`with_<field_name>`メソッドを
個別に用意する(`with_normalized_input`・`with_ambiguity_report`・
`with_intent`・`with_domain_classification`・`with_world`・
`with_meaning`・`with_requirements`・`with_preliminary_candidates`・
`with_plan`・`with_template_selection`・`with_critic_report`・
`with_decision`・`with_revision_attempt_incremented`)。

### 2.3 各段階のシグネチャ規約

全ての段階(Legacy・Cognitiveいずれも)は、「具体的な入力型→具体的な
出力型」を持つメソッドとして実装し、Orchestratorが戻り値を個別に
`with_*`でContextへ格納する。「Contextを引数に取りContextを返す、
汎用の`process()`」という抽象化は採用しない。

- **Legacy Protocol**(`IntentBuilderProtocol`等、既存): 既存
  `run_pipeline()`の後方互換経路専用。`CognitiveOrchestrator`は
  これらを一切呼ばない(4章)。
- **Cognitive Protocol**(`CognitiveIntentRecognizerProtocol`等、新規):
  `run_cognitive_pipeline()`専用。M006が要求する認知的な実行順を
  正しく表現する、独立したシグネチャを持つ(4章)。
- **共有Protocol**(`CompilerProtocol`・`QualityEngineProtocol`):
  両経路でそのまま共用する(既存シグネチャ、無変更)。


## Task 3: Pipeline Orchestrator

### 3.1 依存注入契約(`CognitiveDependencies`)

各Protocol実装をコンストラクタへ個別のキーワード引数として渡す設計は
採用しない。以下の専用dataclassへまとめ、`**`展開も行わない
(dataclassは`**`展開に対応しないため、展開しようとする疑似コードは
型として成立しない、という指摘への対応)。

```python
# forge_ai/core/orchestration/cognitive_dependencies.py(イメージ)

@dataclass(frozen=True)
class CognitiveDependencies:
    normalizer: InputNormalizerProtocol
    ambiguity_detector: AmbiguityDetectorProtocol
    intent_recognizer: CognitiveIntentRecognizerProtocol
    domain_classifier: CognitiveDomainClassifierProtocol
    world_builder: CognitiveWorldBuilderProtocol
    meaning_extractor: CognitiveMeaningExtractorProtocol
    requirement_extractor: RequirementExtractorProtocol
    template_selector: TemplateSelectorProtocol
    planner: CognitivePlannerProtocol
    design_critic: DesignCriticProtocol
    revision_engine: RevisionEngineProtocol
    escalation_handler: EscalationHandlerProtocol
    compiler: CompilerProtocol
    quality_engine: QualityEngineProtocol
```

### 3.2 Orchestratorの責務とコンストラクタ

`forge_ai/core/orchestration/pipeline_orchestrator.py`の
`CognitiveOrchestrator`が、Cognitive Pipelineの実行順序を知る**唯一**
のコンポーネントとする。個別モジュールは、自分がPipeline全体のどこに
いるかを一切知らない。

```python
class CognitiveOrchestrator:
    def __init__(
        self,
        provider: AIProvider,
        domain_registry: DomainRegistry,
        dependencies: CognitiveDependencies,
    ) -> None:
        self._provider = provider
        self._domain_registry = domain_registry
        self._deps = dependencies

    def run(self, raw_input: str) -> CognitivePipelineOutcome:
        """3.3節の順序で実行する。"""
```

### 3.3 段階の分類(4種類、CEO指摘4への対応)

Cognitive Pipelineを構成する要素は、性質の異なる4種類に分かれる。
これらを区別せず「段階」として一律に数えたことが、過去の版で
「16段階」という数の不一致を生んだ根本原因だった。

| 分類 | 意味 | 該当するもの |
|---|---|---|
| **Transformation Stage** | Contextへ新しいデータを追加する、実際の変換処理 | Input Normalization・Ambiguity Detection・Cognitive Intent Recognition・Domain Classification・World Model Construction・Meaning Model・Requirement Extraction・Preliminary Pattern Candidates・Application Planning・Final Template Selection・Design Critic・Cognitive Revision・Forge IR Compilation・Initial Quality Evaluation(**14個**) |
| **Control-flow Node** | データを変換せず、次にどこへ進むかを決めるだけの分岐 | Priority1/Priority2判定・`differs_from_preliminary`判定・`release_ready`判定(Orchestrator内部のif文であり、独立したProtocol・独立した「段階」ではない) |
| **Terminal Outcome** | Pipelineの実行がそこで終わる、分岐の着地点 | Human Confirmation/Escalation(**1個**。到達すると`CognitivePipelineNeedsConfirmation`を返して終了する。「次の段階」が存在しないため、直列のTransformation Stageとしては数えない) |
| **M005 Post-processing Stage** | `run_cognitive_pipeline()`の**外側**、M005が別途実行する処理 | Validation・Repair・Final Quality Evaluation(**3個**。Task9.4) |

**確定した数え方**: Cognitive Pipeline(M004側、`run_cognitive_pipeline()`
の内部)は、**14 Transformation Stage + 1 Terminal Outcome**から成る。
これに続くM005側の3 Post-processing Stageは、別の関数呼び出し
(既存`PromptPipeline`)であり、Cognitive Pipeline自体の段階数には
含めない。**「全16段階」という以前の呼称は、この4分類を区別せずに
数えた結果であり、不正確だったため廃止する。** 今後、Cognitive Pipeline
は「14 Transformation Stage」、全体の処理系(M004+M005)を指す場合は
「14 Transformation Stage + 1 Terminal Outcome + 3 M005 Post-processing
Stage」と表記する。

Initial Quality EvaluationはTransformation Stageの14番目として含める
(`(ir, plan) -> QualityScore`という実際の変換を行うため。Task9.3で
M004の責務であることも確認済み)。

### 3.4 実行フロー(疑似コード、今回は実装しない)

```python
context = CognitiveContext(raw_input=raw_input, started_at=now())
deps = self._deps

try:
    # 1. Input Normalization
    normalized = deps.normalizer.normalize(context.raw_input)
    context = context.with_normalized_input(normalized)

    # 2. Ambiguity Detection
    ambiguity_report = deps.ambiguity_detector.detect(context.normalized_input)
    context = context.with_ambiguity_report(ambiguity_report)
    if _priority1_escalation_needed(ambiguity_report):
        request = deps.escalation_handler.build_confirmation_request(context, reason="priority1_privacy_safety_permission")
        return CognitivePipelineNeedsConfirmation(
            confirmation_request=request, reached_stage="ambiguity_detection",
            partial_context=context, decision_trace=context.decision_trace,
        )

    # 3. Cognitive Intent Recognition(normalized_input・ambiguity_reportのみを入力とする)
    intent = deps.intent_recognizer.recognize(context.normalized_input, context.ambiguity_report)
    context = context.with_intent(intent)

    # 4. Domain Classification(5章: 実際の複数候補スコアリング)
    classification = deps.domain_classifier.classify(context.intent, self._domain_registry)
    context = context.with_domain_classification(classification)
    if _priority2_escalation_needed(classification):
        request = deps.escalation_handler.build_confirmation_request(context, reason="priority2_low_domain_confidence")
        return CognitivePipelineNeedsConfirmation(
            confirmation_request=request, reached_stage="domain_classification",
            partial_context=context, decision_trace=context.decision_trace,
        )

    # 5. World Model Construction(DomainとIntentの両方から構築)
    world = deps.world_builder.build(context.domain_classification, context.intent)
    context = context.with_world(world)

    # 6. Meaning Model
    meaning = deps.meaning_extractor.extract(context.normalized_input, context.world, context.intent)
    context = context.with_meaning(meaning)

    # 7. Requirement Extraction
    requirements = deps.requirement_extractor.extract(context.meaning, context.world, context.intent)
    context = context.with_requirements(requirements)

    # 8. Preliminary Pattern Candidates(独立ノード、Application Planner内部へ隠さない)
    preliminary_candidates = deps.template_selector.select_preliminary(
        context.domain_classification.primary_domain, context.intent, context.requirements,
    )
    context = context.with_preliminary_candidates(preliminary_candidates)

    # 9. Application Planning(requirements・preliminary_candidatesを必ず渡す)
    plan = deps.planner.plan(context.intent, context.world, context.requirements, context.preliminary_candidates)
    context = context.with_plan(plan)

    # 10. Final Template Selection
    final_selection = deps.template_selector.select_final(context.plan)
    context = context.with_template_selection(final_selection)

    if final_selection.differs_from_preliminary:
        # CEO指摘6: 同じ入力でplanner.plan()を再実行しても同じPlanが
        # 再生成されるだけなので、これを独立した再計画として扱わず、
        # Cognitive Revision(11章)へ一本化する。Final Selectionとの
        # 不一致を「合成Critic Issue」として構築し、revision_engineへ
        # 渡す(これにより、再計画に使う情報がPreliminary呼び出し時と
        # 変わり、同じPlanが再生成される問題を避ける)。
        mismatch_report = CriticReport(
            release_ready=False,
            issues=(CriticIssue(
                category="template_mismatch", severity="high",
                evidence=f"Preliminary候補{preliminary_candidates}に対し、"
                         f"Final Template Selectionは{final_selection.template}を選択",
                recommended_fix="Final Templateの要件(画面構成・State等)に合わせてApplicationPlanを再設計する",
                affected_component="application_plan", auto_fixable=True,
            ),),
        )
        if context.revision_attempt >= context.max_revision_attempts:
            request = deps.escalation_handler.build_confirmation_request(context, reason="preliminary_final_mismatch_exhausted")
            return CognitivePipelineNeedsConfirmation(
                confirmation_request=request, reached_stage="final_template_selection",
                partial_context=context, decision_trace=context.decision_trace,
            )
        revised_plan = deps.revision_engine.revise(context.plan, mismatch_report, context.revision_attempt)
        context = context.with_plan(revised_plan).with_revision_attempt_incremented()
        final_selection = deps.template_selector.select_final(context.plan)
        context = context.with_template_selection(final_selection)

    # 11. Design Critic
    critic_report = deps.design_critic.evaluate(context.plan, context.template_selection, context.requirements)
    context = context.with_critic_report(critic_report)

    # 12. Cognitive Revision(9〜10と同じrevision_attemptカウンタを使う)
    while not context.critic_report.release_ready:
        if context.revision_attempt >= context.max_revision_attempts:
            request = deps.escalation_handler.build_confirmation_request(context, reason="revision_exhausted")
            return CognitivePipelineNeedsConfirmation(
                confirmation_request=request, reached_stage="cognitive_revision",
                partial_context=context, decision_trace=context.decision_trace,
            )
        revised_plan = deps.revision_engine.revise(context.plan, context.critic_report, context.revision_attempt)
        context = context.with_plan(revised_plan).with_revision_attempt_incremented()
        final_selection = deps.template_selector.select_final(context.plan)
        context = context.with_template_selection(final_selection)
        critic_report = deps.design_critic.evaluate(context.plan, context.template_selection, context.requirements)
        context = context.with_critic_report(critic_report)

    # 13. Forge IR Compilation(共有Legacy Protocol、無変更)
    forge_document = deps.compiler.compile(context.plan)

    # 14. Initial Quality Evaluation(共有Legacy Protocol、無変更。M004の責務)
    initial_quality = deps.quality_engine.evaluate(forge_document, context.plan)

except (AmbiguityError, ConfirmationRequired) as exc:
    # CEO指摘7: 予備的な例外経路(3.4節が明示的に想定していない箇所で
    # 発生した場合の安全弁)。NeedsConfirmationへ変換する。
    request = deps.escalation_handler.build_confirmation_request(context, reason=str(exc))
    return CognitivePipelineNeedsConfirmation(
        confirmation_request=request, reached_stage=getattr(exc, "stage", "unknown"),
        partial_context=context, decision_trace=context.decision_trace,
    )
except (PlanningError, CriticFailure) as exc:
    # CEO指摘7: 回復不能な失敗。Failedへ変換する。
    return CognitivePipelineFailed(
        error=exc, reached_stage=getattr(exc, "stage", "unknown"), decision_trace=context.decision_trace,
    )
# CEO指摘7: NotImplementedErrorはここで一切捕捉しない。Facadeの外側
# (将来のM005呼び出し元)まで伝播させ、既存の`except NotImplementedError
# -> ProviderError`(6.3節)が処理できるようにする。Provider障害を
# CognitivePipelineFailed(planning_error相当)へ誤って吸収しない。

# CEO指摘2: Successを構築する前に、必要なContextフィールドが全て
# 埋まっていることを検証する(3.5節)。
_assert_context_ready_for_success(context)
return CognitivePipelineSuccess(context=context, ir=forge_document, initial_quality=initial_quality)
```

**注記1**: `_priority1_escalation_needed`・`_priority2_escalation_needed`・
`differs_from_preliminary`・`release_ready`はいずれもControl-flow Node
(3.3節)であり、独立したProtocol・独立した段階ではない。

**注記2**: Human Confirmation/Escalation(Terminal Outcome)は、
上記のいずれかの分岐が実際に呼び出す「受け皿」であり、無条件に実行
される独立ステップではない。

**注記3**: `context.requirements`は7段階目で生成された後、8段階目
(Preliminary)・9段階目(Planning)の両方で実際に参照される。
`CognitivePlannerProtocol.plan()`のシグネチャがrequirementsを必須
パラメータとして要求することで、生成しながら渡し忘れるという契約違反を
型システムレベルで防止する。

### 3.5 `CognitivePipelineOutcome`(3つの独立した具体型のUnion)

**CEO指摘1への対応**: `CognitivePipelineOutcome`は`Union`型エイリアス
であり、クラスではない。したがって`CognitivePipelineOutcome.success(...)`
のような呼び出しは**型として成立しない**(Union型エイリアスはメソッドを
持たない)。3.4節の疑似コードが示す通り、**対応する具体的なdataclassを
直接構築する**。便利のためのFactory関数が欲しい場合は、Union自体では
なく独立した関数(例: `outcomes.py`内の`build_success(...)`)として
定義する(今回は疑似コードの簡潔さを優先し、直接構築のみを示す)。

```python
# forge_ai/core/orchestration/outcomes.py(イメージ)

@dataclass(frozen=True)
class CognitivePipelineSuccess:
    """CEO指摘2への対応: contextへ「既に格納されている」情報を
    個別フィールドとして重複保持しない。ir・initial_qualityは
    Contextに含めていない情報(2.1節)なので、ここでのみ保持する。"""
    context: CognitiveContext
    ir: ForgeIRDocument
    initial_quality: QualityScore

@dataclass(frozen=True)
class CognitivePipelineNeedsConfirmation:
    confirmation_request: ConfirmationRequest
    reached_stage: str
    partial_context: CognitiveContext
    decision_trace: tuple[DecisionTrace, ...]

@dataclass(frozen=True)
class CognitivePipelineFailed:
    error: "CognitiveError"
    reached_stage: str
    decision_trace: tuple[DecisionTrace, ...]

CognitivePipelineOutcome = (
    CognitivePipelineSuccess | CognitivePipelineNeedsConfirmation | CognitivePipelineFailed
)


def _assert_context_ready_for_success(context: CognitiveContext) -> None:
    """CEO指摘2: Successを構築する前提条件を検証する。"""
    required_fields = (
        "intent", "domain_classification", "world", "meaning", "requirements",
        "preliminary_candidates", "plan", "template_selection", "critic_report",
    )
    missing = [f for f in required_fields if getattr(context, f) is None]
    if missing:
        raise PlanningError(f"Success構築の前提条件を満たしていません。未設定: {missing}")
```

呼び出し元(将来のM005・Golden Test)は、`isinstance(outcome,
CognitivePipelineSuccess)`等で分岐する。単一dataclassへ全フィールドを
Optionalとして詰め込む設計は採用しない(却下理由はADR-009参照)。

### 3.6 各モジュールが自分で他モジュールを呼ばないことの強制

実装時、各モジュールのコンストラクタ・メソッドが、他の
`understanding/`・`planning/`・`critic/`モジュールをimportしていない
ことを、Task7の契約テストで機械的に検査する。

---

## Task 4: Interface設計(Legacy/Cognitive Protocol分離)

### 4.1 分離の原則

既存Legacy Protocol(`DomainResolverProtocol`・`WorldModelBuilderProtocol`・
`MeaningExtractorProtocol`・`IntentBuilderProtocol`・`PlannerProtocol`)は、
既存`run_pipeline()`の後方互換経路**専用**。シグネチャ変更禁止。
`CognitiveOrchestrator`はこれらを一切参照しない。M006用には、別の
シグネチャを持つCognitive Protocolを新設する。`CompilerProtocol`・
`QualityEngineProtocol`は、Legacy/Cognitive両経路で意味が変わらない
ため共有する。

### 4.2 Cognitive Protocol(新規)

```python
# forge_ai/contracts/interfaces.py へ追加(イメージ)

class CognitiveIntentRecognizerProtocol(Protocol):
    def recognize(self, normalized: NormalizedInput, ambiguity_report: AmbiguityReport) -> Intent: ...

class CognitiveDomainClassifierProtocol(Protocol):
    def classify(self, intent: Intent, registry: DomainRegistry) -> DomainClassification: ...

class CognitiveWorldBuilderProtocol(Protocol):
    def build(self, classification: DomainClassification, intent: Intent) -> World: ...

class CognitiveMeaningExtractorProtocol(Protocol):
    def extract(self, normalized: NormalizedInput, world: World, intent: Intent) -> ExtractedMeaning: ...

class CognitivePlannerProtocol(Protocol):
    def plan(
        self, intent: Intent, world: World, requirements: RequirementSet, preliminary_candidates: tuple[str, ...],
    ) -> ApplicationPlan: ...

class InputNormalizerProtocol(Protocol):
    def normalize(self, raw_input: str) -> NormalizedInput: ...

class AmbiguityDetectorProtocol(Protocol):
    def detect(self, normalized: NormalizedInput) -> AmbiguityReport: ...

class RequirementExtractorProtocol(Protocol):
    def extract(self, meaning: ExtractedMeaning, world: World, intent: Intent) -> RequirementSet: ...

class TemplateSelectorProtocol(Protocol):
    def select_preliminary(self, domain: Domain, intent: Intent, requirements: RequirementSet) -> tuple[str, ...]: ...
    def select_final(self, plan: ApplicationPlan) -> TemplateSelection: ...

class DesignCriticProtocol(Protocol):
    def evaluate(self, plan: ApplicationPlan, template_selection: TemplateSelection, requirements: RequirementSet) -> CriticReport: ...

class RevisionEngineProtocol(Protocol):
    def revise(self, plan: ApplicationPlan, critic_report: CriticReport, attempt: int) -> ApplicationPlan: ...

class EscalationHandlerProtocol(Protocol):
    def build_confirmation_request(self, context: "CognitiveContext", reason: str) -> ConfirmationRequest: ...
```

### 4.3 `DomainClassification`: 安全な複数候補評価契約(CEO指摘5への全面対応)

**型定義**: `raw_score`(生の一致数)と`normalized_score`(正規化後の
値)を区別して保持する。`confidence`を単一の固定式にせず、比較の上で
決定する(下記参照)。

```python
@dataclass(frozen=True)
class DomainCandidate:
    domain: Domain
    raw_score: float           # Intentとの実際の一致数(素点)
    normalized_score: float    # 0.0〜1.0へ正規化した値(下記の式で算出)
    matched_concepts: tuple[str, ...]
    matched_actions: tuple[str, ...]

@dataclass(frozen=True)
class DomainClassification:
    primary_domain: Domain
    candidates: tuple[DomainCandidate, ...]  # 全Domain、スコア降順
    confidence: float
    score_margin: float
    rationale: str
```

**安全性の必須条件(CEO指摘5)**:

| 状況 | 必須の挙動 |
|---|---|
| 全Domainのスコアが0(Intentの`required_concepts`/`required_actions`が、どのDomainの`typical_concepts`/`typical_actions`とも一致しない) | `primary_domain = Generic`(スコア降順ソートの結果に依存する偶然ではなく、明示的な分岐で強制する)、`confidence = 0.0`、`score_margin = 0.0` |
| 1位が同点(2つ以上のDomainが同じ最高スコア) | `score_margin = 0.0`(低confidence判定の対象、4.3節・M006 4.3節の優先順位2で確認要求され得る) |

**confidenceの定義(2案を比較して決定)**:

| 案 | 定義 | 問題点 |
|---|---|---|
| A(却下) | `primary_raw_score / sum(全Domainのraw_score)` | Intentが持つconcept/actionのうち、実際に**一致した**割合ではなく、**他のDomainとの相対比較**でしかない。例えばIntentが10個のconcept/actionを持ち、Domain Xがそのうち3個だけに一致し、他の全Domainのスコアが0だった場合、この式では`confidence = 3/3 = 1.0`(100%)という、実態より過大な値になってしまう |
| **B(採用)** | `primary_raw_score / max(1, len(intent.required_concepts) + len(intent.required_actions))` | Intentが実際に述べた情報のうち、primary_domainが説明できた割合。上記の例では`confidence = 3/10 = 0.3`となり、「Intentの3割しか一致しなかった」という実態を正しく反映する |

**B案を採用する**。`score_margin`(1位と2位の差)とは別の軸であり、
「どれだけ他候補より優れていたか」ではなく「Intentの情報をどれだけ
説明できたか」を測る。この判断根拠(A案の過大評価問題)は、実装時に
`understanding/domain_classifier.py`のDocstringへ記録し、実際の
分類結果ではDecision Trace(M006 18章)の`rule_used`フィールドへ
`"domain_confidence_v_b"`のような識別子を記録して追跡可能にする。

**スコアリングの概略(疑似コード、今回は実装しない)**:

```python
def classify(self, intent: Intent, registry: DomainRegistry) -> DomainClassification:
    candidates: list[DomainCandidate] = []
    for domain in registry.all_domains():
        matched_concepts = tuple(set(intent.required_concepts) & set(domain.typical_concepts))
        matched_actions = tuple(set(intent.required_actions) & set(domain.typical_actions))
        raw_score = len(matched_concepts) + len(matched_actions)
        candidates.append(DomainCandidate(
            domain=domain, raw_score=raw_score, normalized_score=0.0,  # 後段で埋める
            matched_concepts=matched_concepts, matched_actions=matched_actions,
        ))

    candidates.sort(key=lambda c: c.raw_score, reverse=True)
    total_signal = max(1, len(intent.required_concepts) + len(intent.required_actions))
    candidates = tuple(dataclasses.replace(c, normalized_score=c.raw_score / total_signal) for c in candidates)

    if candidates[0].raw_score == 0:
        # 必須条件1: 全Domainのスコアが0 -> Genericを明示的に選ぶ
        generic = next(c for c in candidates if c.domain.category == DomainCategory.GENERIC)
        return DomainClassification(
            primary_domain=generic.domain, candidates=candidates,
            confidence=0.0, score_margin=0.0, rationale="Intentと一致するconcept/actionが見つからず、Genericへ既定しました。",
        )

    primary = candidates[0]
    second_score = candidates[1].raw_score if len(candidates) > 1 else 0.0
    score_margin = (primary.raw_score - second_score) / total_signal  # 必須条件2: 同点ならここが0.0になる

    return DomainClassification(
        primary_domain=primary.domain, candidates=candidates,
        confidence=primary.normalized_score, score_margin=score_margin,
        rationale=f"一致: concepts={primary.matched_concepts}, actions={primary.matched_actions}",
    )
```

### 4.4 `CognitiveWorldBuilder`: DomainとIntentの両方から構築する契約

`CognitiveWorldBuilderProtocol.build(classification, intent) -> World`
は、以下の2段階でWorldを構築する。

1. **Domain由来の基盤**: `classification.primary_domain`の
   `typical_concepts`・`typical_actions`から、一般的なActor/Entity/
   Rule群を構築する。
2. **Intent由来の具体化**: `intent.actors`(空でなければ)をWorldの
   `Actors`へ追加・統合する。`intent.required_data`を`Entities`へ
   反映する。`intent.constraints`を`Rules`へ変換する。

Legacy`WorldModelBuilderProtocol.build(domain)`(Domainのみ)は、既存
`run_pipeline()`専用として現状のまま残し、Cognitive経路では使用しない。

---

## Task 5: Dependency Rule

### 5.1 依存方向

```
orchestration/  (Orchestrator, Context, Dependencies, Outcomes, Errors)
      │ depends on (calls Protocols implemented by ↓)
      ▼
┌─────────────┬──────────────┬───────────┬──────────┬───────────────┐
│input_processing│ understanding │ planning  │ critic   │ confirmation  │
└─────────────┴──────────────┴───────────┴──────────┴───────────────┘
      │ depends on (imports data TYPES only from ↓)
      ▼
core/ (domain_model, world_model, meaning_model, intent_model, planner, compiler)
      │ depends on
      ▼
provider/ , prompt/ , contracts/
```

### 5.2 明示的な禁止事項

| 禁止 | 理由 |
|---|---|
| Circular Import | 通常のPython健全性 |
| `critic/` → `planning/`の直接呼び出し | Design Criticは`ApplicationPlan`をデータとして受け取るのみ |
| `core/compiler.py` → `understanding/`の参照 | 既存Compilerの責務を守るため |
| `input_processing/`・`understanding/`・`planning/`・`critic/`・`confirmation/`の同階層モジュール間の直接import | Task3.6を、import文レベルでも強制する |
| `orchestration/` → M005(`backend/app/ai/runtime/`)の参照 | forge_ai/はBackendを知らないという大原則を継続する |
| `understanding/`・`planning/`の各ファイル → `core/*.py`のLegacy Protocol実装クラス/メソッド(`IntentBuilder.build()`等)の呼び出し | Cognitive側は`Intent`等のデータ型定義のみをimportしてよいが、Legacy実装は呼ばない(4.1節) |

### 5.3 依存図

`docs/diagrams/10_m007_dependency_graph.md`参照。

---

## Task 6: Error Model

### 6.1 Cognitive Error階層

```python
# forge_ai/core/orchestration/errors.py(イメージ)

class CognitiveError(Exception):
    stage: str

class AmbiguityError(CognitiveError):
    """3.4節の疑似コードが明示的に想定していない箇所で、致命的な曖昧さが
    判明した場合の予備的な送出型(安全弁)。主要経路は例外を使わず直接
    `CognitivePipelineNeedsConfirmation`を返す(3.4節)。"""

class PlanningError(CognitiveError):
    """Application Planning・Success構築前提の検証(3.5節)が失敗した場合。
    backend/app/ai/runtime/pipeline_errors.PlanningErrorとは別クラス。"""

class CriticFailure(CognitiveError):
    """Design Critic自体が実行時エラーで失敗した場合。"""

class ConfirmationRequired(CognitiveError):
    """AmbiguityErrorと同じ位置づけの予備的な送出型。"""
```

### 6.2 例外の捕捉ルール(CEO指摘7への対応、精密化)

`CognitiveOrchestrator.run()`は、以下の3分類**のみ**を区別して扱う。

| 例外/経路 | 変換先 |
|---|---|
| 主要経路: Priority1/2判定・Revision上限到達(3.4節、例外を使わない直接return) | `CognitivePipelineNeedsConfirmation` |
| `AmbiguityError` / `ConfirmationRequired`(予備的経路) | `CognitivePipelineNeedsConfirmation` |
| `PlanningError` / `CriticFailure` / その他の`CognitiveError`派生 | `CognitivePipelineFailed` |
| **`NotImplementedError`** | **捕捉しない。`run()`の外側(将来のM005呼び出し元)まで伝播させる。** |

**`NotImplementedError`を捕捉しない理由**: これはProvider(LLM呼び出し)
自体が未実装であることを示す例外であり、「認知的な失敗」
(`CognitivePipelineFailed`=`planning_error`相当)ではない。既存
`prompt_pipeline.py`が`run_pipeline()`に対して既に持つ
`except NotImplementedError -> ProviderError`という処理を、
`run_cognitive_pipeline()`に対しても同じ形で適用できるよう、
Facadeの外側まで例外を伝播させる。**Provider障害を`CognitivePipelineFailed`
(`planning_error`相当)へ誤って吸収しないことを、この設計で保証する。**

### 6.3 M005側の実際のエラー処理との対応

```python
# backend/app/ai/runtime/prompt_pipeline.py(既存、変更しない)
try:
    pipeline_result = run_pipeline(natural_language, bridge)
except NotImplementedError as exc:
    raise ProviderError(str(exc), sub_reason="unavailable") from exc
except Exception as exc:
    raise PlanningError(f"run_pipeline()が失敗しました: {exc}") from exc
```

| forge_ai/側の状況 | M005側の実際の処理 | 結果 |
|---|---|---|
| Provider名がRouterに未登録(`ProviderNotAvailableError`) | 既存の明示的`except ProviderNotAvailableError` | `provider_error` / `unavailable` |
| 登録済みだが未実装のProviderを実際に呼んだ(`NotImplementedError`) | 既存の明示的`except NotImplementedError`。6.2節により`CognitiveOrchestrator`はこれを捕捉せず素通しするため、M005側のこの処理へ正しく到達する | `provider_error` / `unavailable` |
| `CognitivePipelineFailed`(`CognitiveError`系) | 将来のM005側で`isinstance`判定により`planning_error`へ変換する想定(9.1節、この変換自体は別Task) | `planning_error` |
| 上記以外の未捕捉例外 | 既存の`except Exception`キャッチオール | `planning_error` |

**M005側のコード変更は今回一切提案しない。**

---

## Task 7: Test Blueprint

### 7.1 テストカテゴリ

| カテゴリ | 目的 |
|---|---|
| Unit | 各モジュール単体の入出力・失敗時安全性 |
| Integration | Orchestratorが正しい順序で各段階を呼ぶか |
| Golden | `docs/examples/`の6例を固定入力として期待結果と比較 |
| Regression | 二重ループ・Union alias誤呼び出し等、過去の設計ミスの再発防止 |
| Contract | 依存方向・Legacy/Cognitive Protocol分離・M005 Facade互換性を静的検査 |

### 7.2 モジュール別テスト件数概算(暫定)

| モジュール | 概算件数 |
|---|---|
| `cognitive_context.py` | 8〜10 |
| `cognitive_dependencies.py`(3.1節) | 2〜3(dataclass構築・型検証のみ) |
| `normalizer.py` | 10〜12 |
| `ambiguity_detector.py` | 15〜18 |
| `intent_recognizer.py` | 8〜10 |
| `domain_classifier.py`(5章の安全性条件を含む) | 14〜16(通常ケース+全0/同点の境界テストを追加) |
| `world_builder.py` | 8〜10 |
| `meaning_extractor.py` | 8〜10 |
| `requirement_extractor.py` | 12〜15 |
| `application_planner.py` | 12〜15 |
| `template_selector.py` | 15〜18 |
| `design_critic.py` | 18〜20 |
| `revision_engine.py`(Preliminary/Final不一致の合成Issue処理を含む) | 12〜14 |
| `escalation_handler.py` | 8〜10 |
| `outcomes.py`(`_assert_context_ready_for_success`を含む) | 5〜6 |
| `pipeline_orchestrator.py`(Integration) | 18〜22(NotImplementedError非捕捉の確認を含む) |
| Golden(6例) | 6〜12 |
| Contract | 8〜10 |
| **合計(概算)** | **約189〜221** |

forge_ai/は80 + 189〜221 ≈ **269〜301件**になる見込み(概算、確定値ではない)。

---

## Task 8: 実装順序

```
1. Context・Dependencies・Errors・Outcomes(orchestration/)
   → 他の全モジュールが依存する型定義を先に固める。

2. Domain(understanding/domain_classifier.py)
   → World・Requirement Extraction等の前提になる。5章の安全性条件を
     最初にテストで固定する。

3. Input Processing(input_processing/normalizer.py → ambiguity_detector.py)

4. Understanding残り(intent_recognizer.py → world_builder.py →
   meaning_extractor.py → requirement_extractor.py)

5. Planning(template_selector.py の select_preliminary → application_planner.py
   → template_selector.py の select_final)

6. Critic(design_critic.py → revision_engine.py。Preliminary/Final
   不一致時の合成Issue処理を含める)

7. Confirmation(escalation_handler.py)

8. Orchestrator(pipeline_orchestrator.py)
   → 1〜7全てのProtocol実装が揃ってから最後に配線する。

9. Integration(Task9のFacade追加 + M005との結合確認)
```

---

## Task 9: Migration Plan

### 9.1 Facade分離方式

既存`run_pipeline()`と、新設`run_cognitive_pipeline()`を、別の関数・
別の戻り値型として完全に分離する(採用理由・却下した代替案はADR-009)。

```python
# forge_ai/core/pipeline.py(イメージ、今回は書かない)

def run_pipeline(
    user_text: str, provider: AIProvider, *,
    domain_registry: DomainRegistry | None = None, world_builder: WorldModelBuilder | None = None,
) -> PipelineResult:
    """既存互換。シグネチャ・戻り値型・内部ロジックとも一切変更しない。"""
    ...  # 既存のまま


def run_cognitive_pipeline(
    user_text: str,
    provider: AIProvider,
    domain_registry: DomainRegistry,
    dependencies: CognitiveDependencies,
) -> CognitivePipelineOutcome:
    """新規。M005がこちらを呼ぶようになるのは、CEO承認を経た将来のTaskでのみ。"""
    return CognitiveOrchestrator(provider, domain_registry, dependencies).run(user_text)
```

**段階導入の方式**: M005側のコード(`prompt_pipeline.py`)が、
`from forge_ai.core.pipeline import run_pipeline`という既存のimport文を、
然るべきタイミングで明示的なimport切り替え(または呼び出し箇所の書き換え)
に変更する、という意味である。実行時のBoolean引数による分岐ではなく、
コード上どちらを呼ぶかが常に一意に確定している状態を維持する。
**この切り替え自体は、M005のコード変更を伴うため、今回(forge_ai/側の
設計)のスコープには含まれず、CEO承認を得た別Taskとして実施する。**

### 9.2 `CognitivePipelineOutcome`の設計判断

3.5節参照。単一dataclassへ全フィールドをOptionalとして詰め込む設計は
採用しない(却下理由はADR-009)。`ir`・`initial_quality`をContextへ
含めない理由は、Context(2.1節)が「途中経過」を表すのに対し、これらは
「Pipelineの最終出力」であるため、責務を区別した。

### 9.3 Quality責務の確定(M004=Initial／M005=Final)

| | 責務 | 対象 |
|---|---|---|
| **M004**(`run_cognitive_pipeline()`) | **Initial Quality Evaluation**(Transformation Stage 14番目、3.3節)。Forge IR Compilation直後、Repair前の`ForgeIRDocument`に対して1回実行する | 3.4節疑似コード |
| **M005**(既存`PromptPipeline`) | **Final Quality Evaluation**。Repairが発生した場合のみ再実行する(既存コードに実装済み) | 既存コード、変更なし |

この責務分担は新規の設計判断ではなく、既存コード
(`backend/app/ai/runtime/prompt_pipeline.py`)に既に実装されている
挙動を明文化したものである。

### 9.4 段階導入・Rollback方針

- **段階導入**: `run_cognitive_pipeline()`を実装・テストしても、M005が
  実際にこれを呼び始めるまでは、本番経路への影響はゼロ。
- **Rollback**: 問題が発覚した場合、import文を`run_pipeline()`へ
  戻すだけで、既存の実績ある経路へ即座に復帰できる。

### 9.5 既存テストへの影響

既存80テストは無変更で合格し続ける(`run_pipeline()`のシグネチャ・
内部ロジックを一切変更しないため)。Task1.3の拡張手法自体も、既存
テストの呼び出しパターンに一切影響しない。

---

## 10. 完了条件チェックリスト

| 条件 | 状態 |
|---|---|
| 新規コード0行 | ✅ 本書はMarkdownドキュメントのみ |
| 実装可能な設計である | ✅ 各Taskで具体的なディレクトリ・クラス・シグネチャを提示 |
| M007で迷わない粒度である | ✅ Task1〜9で「どこに何を置き」「どの順序で作り」「何をテストするか」まで具体化 |
| M004/M005との責務境界を維持 | ✅ Task6.3・9.1〜9.3(M005側の変更は一切提案していない) |
| Union aliasへクラスメソッドを呼ばない | ✅ Task3.5(具体型を直接構築) |
| Successのフィールドと生成引数が一致 | ✅ Task3.5(`context`・`ir`・`initial_quality`の3フィールドのみ、重複保持なし) |
| Dependenciesを正しく注入できる | ✅ Task3.1(専用dataclass、`**`展開しない) |
| 段階数が全資料で一致 | ✅ Task3.3(14 Transformation Stage + 1 Terminal Outcome + 3 M005 Post-processing Stage、「16段階」表記は廃止) |
| 全スコア0なら必ずGeneric | ✅ Task4.3 |
| 再計画が同じ入力の単純再実行にならない | ✅ Task3.4(Cognitive Revisionへ一本化、合成Critic Issueを渡す) |
| Provider障害をPlanning失敗へ誤分類しない | ✅ Task6.2(NotImplementedErrorは非捕捉) |
| 旧仕様が現行本文に残っていない | ✅ 本版(v1.3)で全面書き直し、旧設計は16章のみに集約 |

---

## 11. 自己レビュー

| 観点 | 所見 |
|---|---|
| 後方互換性 | Task9のFacade分離方式により、既存M005・既存80テストへの影響をゼロに設計した |
| 型としての実行可能性 | Task3.5でUnion aliasの誤用を修正し、Task3.1でdataclassの`**`展開という誤りを修正した。疑似コードは今回、型として矛盾しない形になっている |
| M006への忠実性 | Legacy/Cognitive Protocol分離(Task4)により、M006の認知順序をLegacy Protocolの都合で変更する必要が無くなった |
| DomainClassificationの根拠 | Task4.3で、2つのconfidence定義案を比較し、Intentの情報をどれだけ説明できたかを測る方が実態に即すると判断した。重み付け自体は暫定 |
| リスク | Task7の件数は概算であり、Design Critic(14軸)・Template Selection(11 Family)は実装時に想定より複雑になる可能性がある |
| 未決定事項 | `understanding/`層のCognitive実装が、既存`core/*.py`のデータ型をどこまで直接importして再利用するかの具体的なコード配置は、実装着手時に最終決定する |

**事実と推測の分離**: Task7のテスト件数・Task4.3のスコアリング
重み付け係数は、既存資産からの類推または暫定値に基づく**提案**であり、
確定した仕様ではない。Task1〜6の構造自体は、M006本体・既存コードの
実際の構造から直接導出した、より確度の高い設計判断である。

---

## 12. CEOへの確認事項

1. Task1.2のディレクトリ構成(6新設サブディレクトリ)の妥当性。
2. Task9.1のFacade分離方式の採用可否、および「M005側のimport切り替えを
   いつ・どのTaskで行うか」。
3. Task6.3で示した「M005側で`CognitivePipelineFailed`を`planning_error`
   へ変換する処理」自体は、今回のforge_ai/側設計のスコープ外(M005側の
   変更を伴うため)としたが、これをいつ・どのTaskで扱うか。
4. Task8の実装順序を、M007の複数サブフェーズに分割する単位として
   使うか、一括で進めるか。
5. Task7のテスト件数概算(約189〜221件)を踏まえた、M007のスケジュール
   感・優先順位付け。
6. Task4.3の`DomainClassification`スコアリング(重み付け係数)は
   暫定値であり、実装時にDomain Registryの実データで検証・調整が
   必要になる。
7. Task3.3で確定した「14 Transformation Stage + 1 Terminal Outcome +
   3 M005 Post-processing Stage」という数え方を、M006本体
   (`FORGE_COGNITIVE_ARCHITECTURE_V2.md`)の正式な表記として反映済み
   (16章参照)。この反映内容に問題がないか。

---

## 13. Golden/Integration Test Blueprintにおける段階数表記

Golden Test・Integration Testの設計・命名において、「16段階」という
表現は使用しない。以下の表記を統一して使う。

- Cognitive Pipeline(M004側): 14 Transformation Stage
- Terminal Outcome: Human Confirmation/Escalation(1個、到達可能性の
  テストは`test_priority1_escalates`のように到達契機ごとに命名する)
- M005 Post-processing: Validation/Repair/Final Quality Evaluation
  (3個、既存`test_ai_runtime.py`のテストで既にカバー済み)

---

## 14. 設計の変遷(Superseded Design History)

過去のCEO実物監査を経て却下・訂正した設計を、現行本文と分離して
ここへ集約する。現行本文(Task1〜13)にはこれらの記述を含めない。

### 14.1 却下: Boolean Feature Flag方式

初版は`run_pipeline(..., use_cognitive_pipeline: bool = False)`という、
単一関数内でのBoolean分岐方式を提案していた。**却下理由**: 
`needs_confirmation`という結果は、Ambiguity Detection直後にも発生
しうるが、この時点では`domain`等の情報がまだ存在せず、既存
`PipelineResult`(7フィールド必須)へダミー値経由で変換する必要が
生じてしまう。Task9のFacade分離方式(`run_pipeline()`無変更+新規
`run_cognitive_pipeline()`)へ置き換えた。詳細はADR-009。

### 14.2 却下: 既存Legacy Protocolをそのまま再利用する設計

第2版は、既存`IntentBuilderProtocol`等をCognitive Pipelineでも
再利用しようとした結果、Legacy Protocolのシグネチャ(Domain→World→
Meaning→Intentという順序を前提とする)に合わせて、Cognitive Pipeline
の実行順を静かに変更してしまっていた。**却下理由**: M006が指定する
認知順序(Intentが最初)を、M004の都合で変更することは許されない。
Task4でLegacy ProtocolとCognitive Protocolを完全に分離した。

### 14.3 却下: Preliminary Pattern CandidatesをApplication Planning内部へ隠す設計

第3版は、Preliminary Pattern Candidatesを独立した段階として数えず、
Application Planningの内部フェーズとして隠すことで、段階数を「16」に
収めようとしていた(ADR-008の当初のDecision)。**却下理由**: 責務の
実態(Preliminary選択が実際に行われていること)を、段階数を保つために
隠すべきではない。Task3.3・3.4でOrchestratorが明示的に呼び出す独立
ノードへ変更した。

### 14.4 却下: `DomainClassification`を単純なラップとして扱う設計

第3版は、既存`resolve_from_keywords()`の単一Domain結果を
`DomainClassification`型へ包むだけで、`candidate_domains`は空、
`confidence`は固定値にせざるを得なかった。**却下理由**: 架空の値を
返す設計は、実際の判断根拠を持たない。Task4.3で、Intentと各Domainの
実際の一致度に基づくスコアリングへ全面的に書き換えた。

### 14.5 却下: `CognitivePipelineOutcome.success(...)`のようなUnion alias経由のFactory呼び出し

第3版までの疑似コードは、`CognitivePipelineOutcome`(Union型
エイリアス)に対して`.success(...)`・`.needs_confirmation(...)`という
メソッド呼び出しを行っていた。**却下理由**: Union型エイリアスは
クラスではなく、メソッドを持てない。型として成立しない疑似コード
だった。Task3.4・3.5で、対応する具体的なdataclass
(`CognitivePipelineSuccess`等)を直接構築する形へ修正した。

### 14.6 却下: `CognitivePipelineSuccess`が`domain`・`world`等を個別フィールドとして重複保持する設計

第3版は、`CognitiveContext`が既に保持している情報
(`domain`・`world`・`meaning`・`intent`・`plan`)を、
`CognitivePipelineSuccess`へも個別フィールドとして複製していた。
**却下理由**: Contextとの不一致(2つの場所が別の値を持ってしまう
リスク)を生む。Task3.5で`context: CognitiveContext`を1フィールドとして
保持し、Contextに含まれない情報(`ir`・`initial_quality`)のみを
追加で保持する設計へ変更した。

### 14.7 却下: `**cognitive_dependencies`という、dataclassの`**`展開

第3版は、`CognitiveDependencies`をdataclassとして定義しながら、
`CognitiveOrchestrator(provider, domain_registry, **cognitive_dependencies)`
という、dictのような`**`展開を行う疑似コードになっていた。**却下理由**:
dataclassは標準では`**`展開に対応しない。型として成立しない。Task3.1・
3.2で、`dependencies: CognitiveDependencies`を単一の引数として直接
渡す形へ修正した。

### 14.8 却下: 「全16段階」という数え方

M006初版・Blueprint初版は、Transformation Stage・Control-flow Node・
Terminal Outcome・M005 Post-processing Stageという性質の異なる要素を
区別せず、合計を「16段階」と称していた。**却下理由**: この4分類を
区別しないまま数を合わせようとした結果、Preliminary Pattern
Candidatesを隠す(14.3節)等の、責務を歪める判断を誘発した。Task3.3で
「14 Transformation Stage + 1 Terminal Outcome(M004側)+ 3 M005
Post-processing Stage」という、性質を区別した数え方へ改めた。この
数え方は`FORGE_COGNITIVE_ARCHITECTURE_V2.md`・関連する図・ADRへも
反映した(16章で詳細な反映箇所を記録)。

### 14.9 却下: Preliminary/Final不一致時に同じ引数でPlannerを再実行する設計

第3版は、Final SelectionがPreliminary候補と異なった場合、
`planner.plan(intent, world, requirements, preliminary_candidates)`を
**全く同じ引数**で再実行していた。**却下理由**: `CognitivePlannerProtocol.
plan()`が決定的な実装であれば、同じ入力から同じ`ApplicationPlan`が
再生成されるだけで、実質的に何も変わらない。Task3.4で、この不一致を
「合成Critic Issue」としてCognitive Revisionへ一本化し、
`revision_engine.revise()`が実際に新しい情報(不一致の内容)を受け取って
Planを更新する設計へ変更した。

### 14.10 訂正: 未捕捉Cognitive ErrorのM005側分類

第3版は、「未捕捉のCognitiveErrorが自動的に`provider_error`等へ
分類される」という趣旨の記載を含んでいたが、これは実際の
`prompt_pipeline.py`の実装(`except NotImplementedError -> ProviderError`、
それ以外の`except Exception -> PlanningError`)と一致していなかった。
Task6.3で、正確な対応関係へ訂正した。第4版ではさらに、
`NotImplementedError`自体を`CognitiveOrchestrator`が一切捕捉しない
設計へ変更し(Task6.2)、Provider障害が`CognitivePipelineFailed`
(planning_error相当)へ誤って吸収されないことを構造的に保証した。
