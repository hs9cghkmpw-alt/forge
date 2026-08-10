"""Cognitive Pipeline共有データ型(FORGE-MILESTONE-007第一段階)。

`docs/spec/FORGE_M007_IMPLEMENTATION_BLUEPRINT.md` v1.3で定義された、
Cognitive Pipeline専用の新規データ型をまとめる。既存の`core/*.py`
(domain_model.py・world_model.py・meaning_model.py・intent_model.py・
planner.py・compiler.py)は変更しない(Legacy Protocol・既存の型は
無変更のまま。Task1.3)。

このファイルはforge_ai/の他モジュールを一切importしない(依存の最下層)。
"""

from __future__ import annotations

from dataclasses import dataclass, field

from forge_ai.core.domain_model import Domain


# ---------------------------------------------------------------------------
# 1. Input Normalization
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class NormalizedInput:
    """Input Normalizationの出力(Blueprint 3.1、M006 5章)。

    元入力と正規化後入力を両方保持する(M006 5章「Normalizationはユーザーの
    意味を勝手に変更してはならない。元入力と正規化後入力を両方保持する」)。

    `title_seed`(FORGE_v0.2_最終修正指示(Final Gate) P3対応、新設):
    確認フロー(needs_confirmation→回答)経由の場合のみ設定される、
    タイトル/goal導出に使うべき「意味のある部分だけの」テキスト。
    元入力(`raw_input`)がノイズ的な短い入力("x"等)で、Human
    Confirmationへの回答で実質的な情報が補われた場合、
    `normalized_text`(全体の結合、ノイズを含む)ではなく、この
    `title_seed`(回答部分のみ)を`CognitiveIntentRecognizer`の
    goal導出が優先して使う。`None`の場合は`normalized_text`を使う
    (確認フローを経ていない通常の入力では、これまで通りの挙動)。
    """

    original_text: str
    normalized_text: str
    title_seed: str | None = None


# ---------------------------------------------------------------------------
# 2. Ambiguity Detection
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class AmbiguityIssue:
    """M006 4章の8分類のいずれか1件。"""

    category: str
    severity: str  # "low" | "medium" | "high"
    description: str


@dataclass(frozen=True)
class AmbiguityReport:
    """Ambiguity Detectionの出力。

    `detection_status`/`overall_severity="unknown"`はM006 4.4節
    (検出失敗時に「曖昧さ無し」として楽観的に継続しない)への対応。
    検出処理自体が失敗した場合のみ`detection_status="failed"`とする
    (今回の実装では、ルールベースの検出ロジック自体は例外を投げない
    設計にしているため、実運用ではほぼ`"ok"`になる。将来LLM補助を
    追加した際に、Provider呼び出し失敗等でこの分岐が実際に使われる)。
    """

    issues: tuple[AmbiguityIssue, ...]
    overall_severity: str  # "low" | "medium" | "high" | "unknown"
    detection_status: str = "ok"  # "ok" | "failed"

    @property
    def has_priority1_issue(self) -> bool:
        """M006 4.3節 優先順位1: Privacy/Safety/Permission関連のHIGH。"""
        return any(
            i.severity == "high" and i.category in ("privacy_safety_permission",)
            for i in self.issues
        )


# ---------------------------------------------------------------------------
# 3. Domain Classification
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class DomainCandidate:
    """スコアリング対象になった1つのDomainの結果(Blueprint 4.3)。"""

    domain: Domain
    raw_score: float
    normalized_score: float
    matched_concepts: tuple[str, ...]
    matched_actions: tuple[str, ...]


@dataclass(frozen=True)
class DomainClassification:
    """Domain Classificationの出力。CEO実物監査により、単純なラップ
    ではなく実際の複数候補スコアリング結果を保持する(Blueprint 4.3)。

    CEO実物監査(Phase 1.1)対応: `confidence`は実質的に「Intentの
    concept/actionをprimary_domainがどれだけ説明できたか」という
    **domain_coverage**であり、自然言語理解全体への確信度ではない
    (固定辞書によるIntent抽出→固定Domain辞書との照合、という
    自己採点に近い性質を持つ)。`domain_coverage`プロパティを
    明示的に追加し、`confidence`という名前だけでは伝わりにくい
    この性質を明確にした(既存の`confidence`フィールド自体は
    後方互換のため変更していない)。
    """

    primary_domain: Domain
    candidates: tuple[DomainCandidate, ...]
    confidence: float
    score_margin: float
    rationale: str

    @property
    def domain_coverage(self) -> float:
        """`confidence`と同じ値のプロパティ別名。CEO実物監査(Phase 1.1)
        指摘6「domain_coverage: Intentのconcept/actionをprimary domain
        が説明できた割合」に対応する、より明確な名前。"""
        return self.confidence


# ---------------------------------------------------------------------------
# 4. Meaning Model(FORGE-MILESTONE-007 Phase 1.2で新設)
# ---------------------------------------------------------------------------
#
# **Legacy `forge_ai.core.meaning_model.ExtractedMeaning`(4フィールド:
# raw_text/mentioned_concepts/mentioned_actions/keywords)とは別の型
# である。** 既存Legacy版は`raw_text: str`が必須の第1フィールドであり、
# 今回追加する`summary: str`も同様に必須の第1フィールドとなるため、
# 単純にフィールド追加で拡張しようとすると「意味の異なる2つの必須
# 第1フィールド」を抱える不自然な型になってしまう。Cognitive Protocol
# 分離の原則(Blueprint 4.0節)に倣い、このモジュール(cognitive_types.py)
# に独立した型として定義する(名前は同じ`ExtractedMeaning`だが、
# 別モジュール・別クラスであり、Legacy`MeaningExtractor`とは一切
# 混在しない)。


@dataclass(frozen=True)
class SemanticUnit:
    """1つの意味単位(誰が・何を・どうするか)。文字列の羅列ではなく、
    action/target/qualifierの関係を保持する。"""

    subject: str | None
    action: str
    target: str | None
    qualifiers: tuple[str, ...] = ()
    evidence: str = ""


@dataclass(frozen=True)
class ExtractedMeaning:
    """Meaning Modelの出力(M006 10章、CEO提示スキーマに準拠)。"""

    summary: str
    semantic_units: tuple[SemanticUnit, ...] = ()
    actors: tuple[str, ...] = ()
    entities: tuple[str, ...] = ()
    actions: tuple[str, ...] = ()
    constraints: tuple[str, ...] = ()
    preferences: tuple[str, ...] = ()
    temporal_conditions: tuple[str, ...] = ()
    state_conditions: tuple[str, ...] = ()
    evidence_spans: tuple[str, ...] = ()
    confidence: float = 1.0


# ---------------------------------------------------------------------------
# 5. Requirement Extraction
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Requirement:
    """M006 11章の1件。

    CEO実物監査(Phase 1.1、2回目)対応: `target_ref`・`operation_ref`を
    追加した(既定値`None`、既存の`Requirement(requirement_id=...,
    category=..., description=...)`という呼び出し方は無変更で動く)。
    これらは、ApplicationPlannerが「この要件が実際にPlanへ反映された
    かどうか」を、description文字列の一致に頼らず機械的に判定するために
    使う。`target_ref`はデータ実体(概念)名、`operation_ref`は操作
    (Action)名を指す。どちらのrefも持たない要件(Validation・Privacy・
    Accessibility等、概念/操作に紐付かない一般的な要件)は`None`のまま
    でよい。

    FORGE-MILESTONE-007 Phase 1.2で`derived_from`を追加した(既定値
    `"world"`)。Meaning Model導入に伴い、「target_ref/operation_refを
    持つ要件は無条件でPlanへ自動反映してよいか」という問題が生じた
    (実際にテストして発見: World由来の要件(例: 存在しないoperation_ref
    を意図的に持つテスト用要件)まで自動的に反映されてしまうと、
    「実際にPlanへ反映されていない要件はunassignedのままになる」
    というPhase 1.1の検証(CEO実物監査(Phase 1.1、2回目)指摘3)が
    無意味になってしまう)。`derived_from="meaning"`の要件のみを
    ApplicationPlannerが自動反映の対象とし、`"world"`(既定、World
    Modelの基本概念由来)・`"intent"`由来の要件は、Planner自身の
    通常の構築ロジック(World基盤+Meaning由来の追加)で実際に反映
    された場合にのみ割当済みとなる(不当に自動反映しない)。
    """

    requirement_id: str
    category: str  # functional/non_functional/data/interaction/validation/privacy/accessibility
    description: str
    mandatory: bool = True
    rationale: str = ""
    target_ref: str | None = None
    operation_ref: str | None = None
    derived_from: str = "world"  # "world" | "intent" | "meaning"


@dataclass(frozen=True)
class RequirementSet:
    requirements: tuple[Requirement, ...] = ()

    def by_category(self, category: str) -> tuple[Requirement, ...]:
        return tuple(r for r in self.requirements if r.category == category)


# ---------------------------------------------------------------------------
# 6. Template Selection(Preliminary / Final)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class TemplateSelection:
    """Final Template Selectionの出力(Blueprint 3.9)。"""

    template: str
    score_by_template: tuple[tuple[str, float], ...]
    differs_from_preliminary: bool
    rationale: str


# ---------------------------------------------------------------------------
# 7. Design Critic / Cognitive Revision
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CriticIssue:
    """M006 14章「Criticの出力」の1件。"""

    category: str
    severity: str  # "low" | "medium" | "high"
    evidence: str
    recommended_fix: str
    affected_component: str
    auto_fixable: bool = False


@dataclass(frozen=True)
class CriticReport:
    """CEO実物監査(Phase 1.1)指摘5への対応: `score`(旧来のフィールド、
    後方互換のため維持)を、単純な「アプリ全体の品質1.00」として誤読
    されないようにする。M006 14章は14の評価軸を定義するが、第一段階は
    そのうち4軸のみを実装している。この「実装済み軸だけの平均」と
    「M006が定義する全軸のうち何割を実際に評価したか」を、別々の
    フィールドとして明示する(CEO提示のA案「implemented_checks_scoreと
    coverage_ratioを分離する」を採用した)。
    """

    release_ready: bool
    score: float  # 後方互換のため維持。値の意味はimplemented_checks_scoreと同じ。
    issues: tuple[CriticIssue, ...] = ()
    implemented_checks_score: float = 0.0  # 実装済み軸(evaluated_axes)だけの平均
    coverage_ratio: float = 0.0  # len(evaluated_axes) / M006全軸数(14)
    evaluated_axes: tuple[str, ...] = ()
    unevaluated_axes: tuple[str, ...] = ()


# ---------------------------------------------------------------------------
# 8. Human Confirmation / Escalation
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ConfirmationRequest:
    """Human Confirmation/Escalationの出力(Terminal Outcomeの一部)。"""

    reason: str
    message: str
    open_questions: tuple[str, ...] = ()


# ---------------------------------------------------------------------------
# 9. Explainability(Decision Trace)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class DecisionTrace:
    """M006 15章。

    **Task042-1追加分(CEO指示、2026-07-21)**: `confidence_observation`
    は、Task042-2で「現行の判定ロジック」と「overall_confidenceベース
    の判定」を比較実験するための、**構造化された観測データ**。
    `reason`という自由記述の文字列を構文解析せずに、`overall_
    confidence`・`available_components`・`intent_confidence`・
    `domain_confidence`・各`basis`へ直接アクセスできるようにする
    (`OverallConfidence`自体がこれらを全て提供する、下記10章参照)。
    **このフィールドはどの制御フローにも使わない、純粋な観測データ
    である**(Task042-1のドキュメント方針を維持)。
    """

    stage: str
    decision: str
    reason: str
    confidence: float | None = None
    alternatives: tuple[str, ...] = field(default_factory=tuple)
    confidence_observation: OverallConfidence | None = None
    # Task042-2 Phase B追加分(CEO指示、2026-07-21)。現行モデルと
    # overall_confidenceモデルの判定を並行計算した結果(観測専用、
    # `forge_ai.core.orchestration.confidence.ShadowJudgment`)。
    # `shadow_judgment`という前方参照は、このファイル冒頭の
    # `from __future__ import annotations`により、定義順に関わらず
    # 有効(`OverallConfidence`と同様)。ただし`ShadowJudgment`自体は
    # `confidence.py`(このファイルとは別モジュール)で定義されているため、
    # 型注釈としてのみ`Any`寄りの扱いになる点に注意(実行時の型検査は
    # 行わない、既存の`OverallConfidence`のような同一ファイル内の
    # forward referenceとは異なる)。
    shadow_judgment: "object | None" = None


# ---------------------------------------------------------------------------
# 10. Confidence Model(ADR-007、Task042-1)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ConfidenceRecord:
    """M006 14.3節「根拠を伴う信頼度」。単独の数値ではなく、何を根拠に
    その値になったかを`basis`として保持する。

    **Task042-1(2026-07-21)での位置づけ**: この型自体はADR-007が
    要求する構造をそのまま実装したものだが、**観測専用**であり、
    どの制御フロー(`if`分岐)にも使われていない(下記`OverallConfidence`
    のdocstring、`compute_overall_confidence()`のdocstring参照)。
    """

    value: float
    basis: tuple[str, ...] = ()


@dataclass(frozen=True)
class OverallConfidence:
    """M006 14.1節「6種の信頼度」。`intent_confidence`・
    `domain_confidence`・`entity_confidence`・`planning_confidence`・
    `template_confidence`という5つの要素信頼度と、それらから計算される
    `overall_confidence`(`.value`プロパティ)を保持する。

    **Task042-1(2026-07-21)時点の制限**: `entity_confidence`・
    `planning_confidence`・`template_confidence`を算出するロジックは
    まだ存在しない(Entity抽出・Application Planning・Template
    Selectionの各段階が、今のところ個別のconfidenceを算出していない
    ため)。この3つは`None`のまま許容し、`.value`の計算からは除外する
    (存在する要素だけの単純平均。重み付けは「実装時に調整可能な
    パラメータ」というADR-007 14.1節の記述に沿って、将来調整できる
    余地を残すため、要素ごとに個別のフィールドとして保持し、単一の
    floatへ早期に潰さない——これはTask042-2で「既存シグナルを内部
    要素として残しつつ比較実験できる状態を作る」というCEO方針に
    対応するための、意図的な設計)。
    """

    intent_confidence: ConfidenceRecord
    domain_confidence: ConfidenceRecord
    entity_confidence: ConfidenceRecord | None = None
    planning_confidence: ConfidenceRecord | None = None
    template_confidence: ConfidenceRecord | None = None

    @property
    def available_components(self) -> tuple[ConfidenceRecord, ...]:
        """現時点で値が存在する要素信頼度のみを返す(Task042-2以降、
        entity/planning/template confidenceが実装され次第、自動的に
        平均へ加わる設計)。"""
        components = [self.intent_confidence, self.domain_confidence]
        for optional in (self.entity_confidence, self.planning_confidence, self.template_confidence):
            if optional is not None:
                components.append(optional)
        return tuple(components)

    @property
    def value(self) -> float:
        """`overall_confidence`(M006 14.1節)。現時点で存在する要素の
        単純平均(均等重み、ADR-007 14.1節「重みは実装時に調整可能な
        パラメータとする」を踏まえ、将来変更しうる暫定値)。"""
        components = self.available_components
        if not components:
            return 0.0
        return sum(c.value for c in components) / len(components)
