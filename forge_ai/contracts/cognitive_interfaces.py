"""Cognitive Protocols(M007 Phase 1 Minimal Cognitive Slice)。

`docs/spec/FORGE_M007_IMPLEMENTATION_BLUEPRINT.md` v1.3 Task4で定義された、
Cognitive Pipeline(`run_cognitive_pipeline()`)専用のProtocol群。

**`contracts/interfaces.py`(Legacy Protocol、既存)とは完全に別ファイルへ
分離した。** `CognitiveOrchestrator`はこのファイルのProtocolのみを型
注釈に使い、`interfaces.py`のLegacy Protocol(`IntentBuilderProtocol`・
`PlannerProtocol`・`DomainResolverProtocol`・`WorldModelBuilderProtocol`・
`MeaningExtractorProtocol`)は一切importしない・使わない(Blueprint 4.0節)。

`CompilerProtocol`・`QualityEngineProtocol`はLegacy/Cognitive両経路で
意味が変わらないため、`interfaces.py`のものをそのまま共有する
(このファイルでは再定義しない)。

**FORGE-MILESTONE-007 Phase 1.2でMeaning Modelを正式接続した**:
`CognitiveMeaningExtractorProtocol`を新設し、`RequirementExtractorProtocol.
extract()`をBlueprint v1.3 Task4.2本来の3引数
(`meaning, world, intent`)へ復元した(Phase 1では`meaning`を受け取らない
2引数版だったが、今回のMeaning Model導入によりこの簡略化を解消した)。
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

from forge_ai.core.domain_model import Domain, DomainRegistry
from forge_ai.core.intent_model import Intent
from forge_ai.core.orchestration.cognitive_types import (
    AmbiguityReport,
    ConfirmationRequest,
    CriticReport,
    DomainClassification,
    ExtractedMeaning,
    NormalizedInput,
    RequirementSet,
    TemplateSelection,
)
from forge_ai.core.planner import ApplicationPlan
from forge_ai.core.world_model import World

if TYPE_CHECKING:
    from forge_ai.core.orchestration.cognitive_context import CognitiveContext


class InputNormalizerProtocol(Protocol):
    """M006 5章。前後空白除去・表記揺れ・極端な長さ等を扱う。"""

    def normalize(self, raw_input: str) -> NormalizedInput:
        """生の自然言語入力から、正規化済み入力(元入力を保持したまま)を作る。"""
        ...


class AmbiguityDetectorProtocol(Protocol):
    """M006 4章。8分類・3段階の重大度で曖昧さを検出する。"""

    def detect(self, normalized: NormalizedInput, registry: DomainRegistry) -> AmbiguityReport:
        """正規化済み入力から曖昧さを検出する。`registry`は4.4節の
        「Priority1判定のための軽量なDomain予備チェック」にのみ使う
        (正式なDomain Classificationの代わりではない)。"""
        ...


class CognitiveIntentRecognizerProtocol(Protocol):
    """M006 7章。normalized_input・ambiguity_reportのみを入力とし、
    Domain/World/Meaningより前に実行する(Blueprint Task4.0)。"""

    def recognize(self, normalized: NormalizedInput, ambiguity_report: AmbiguityReport) -> Intent:
        """正規化済み入力とAmbiguity Reportから、Intentを構築する。"""
        ...


class CognitiveDomainClassifierProtocol(Protocol):
    """M006 8章。実際に複数Domainをスコアリングする(Blueprint Task4.3)。"""

    def classify(self, intent: Intent, registry: DomainRegistry) -> DomainClassification:
        """IntentとDomainRegistryから、実際のスコアリングに基づく
        DomainClassificationを構築する。"""
        ...


class CognitiveWorldBuilderProtocol(Protocol):
    """M006 9章。DomainとIntentの両方から構築する(Blueprint Task4.4)。"""

    def build(self, classification: DomainClassification, intent: Intent) -> World:
        """DomainClassification(primary_domain)由来の一般的な基盤に、
        Intent由来のユーザー固有の具体化(actors・required_data・
        constraints)を反映したWorldを構築する。"""
        ...


class CognitiveMeaningExtractorProtocol(Protocol):
    """M006 10章。FORGE-MILESTONE-007 Phase 1.2で新設。normalized_input・
    world・intentの3つから、構造化された意味情報(ExtractedMeaning)を
    抽出する。"""

    def extract(self, normalized: NormalizedInput, world: World, intent: Intent) -> ExtractedMeaning:
        """正規化済み入力・World・Intentから、Actor/Entity/Action/
        Constraint/Preference/Temporal condition/State conditionを
        含む構造化された意味情報を抽出する。"""
        ...


class RequirementExtractorProtocol(Protocol):
    """M006 11章。FORGE-MILESTONE-007 Phase 1.2で、Blueprint v1.3
    Task4.2本来の3引数(meaning, world, intent)へ復元した(Phase 1では
    meaningを受け取らない2引数の簡略版だった)。"""

    def extract(self, meaning: ExtractedMeaning, world: World, intent: Intent) -> RequirementSet:
        """Meaning/World/Intentから、機能/非機能/データ/検証/Privacy/
        Accessibility等の要件を抽出する。"""
        ...


class TemplateSelectorProtocol(Protocol):
    """M006 13章。Preliminary(絞り込みのみ)とFinal(確定)の2メソッドを持つ。"""

    def select_preliminary(
        self, domain: Domain, intent: Intent, requirements: RequirementSet
    ) -> tuple[str, ...]:
        """Domain/Intent/Requirementsのみで、Template Familyの候補を
        大まかに絞り込む(まだ画面数等のApplicationPlan詳細は使わない)。"""
        ...

    def select_final(self, plan: ApplicationPlan, preliminary_candidates: tuple[str, ...] = ()) -> TemplateSelection:
        """確定したApplicationPlan(画面数・編集/履歴/集計/遷移/検証要件)を
        使って、Template Familyを最終決定する。`preliminary_candidates`は
        同点時のtie-break(CEO実物監査Phase 1.1、Preliminary候補を
        優先する規則)に使う。"""
        ...


class CognitivePlannerProtocol(Protocol):
    """M006 12章。requirements・preliminary_candidatesを必須引数とし、
    生成しながら渡し忘れる契約違反を型レベルで防止する(Blueprint Task3)。"""

    def plan(
        self,
        intent: Intent,
        world: World,
        requirements: RequirementSet,
        preliminary_candidates: tuple[str, ...],
    ) -> ApplicationPlan:
        """Intent/World/Requirements/Preliminary候補から、Runtime非依存の
        ApplicationPlanを生成する。"""
        ...


class DesignCriticProtocol(Protocol):
    """M006 14章。Validatorとは別に、設計としての良し悪しを評価する。"""

    def evaluate(
        self, plan: ApplicationPlan, template_selection: TemplateSelection, requirements: RequirementSet
    ) -> CriticReport:
        """ApplicationPlan・TemplateSelection・Requirementsから、
        設計品質のCriticReportを算出する。"""
        ...


class RevisionEngineProtocol(Protocol):
    """M006 15章。Cognitive Revision(Schema Repairとは別、12.3節参照)。"""

    def revise(self, plan: ApplicationPlan, critic_report: CriticReport, attempt: int) -> ApplicationPlan:
        """CriticReportの指摘に基づき、ApplicationPlanを修正する。"""
        ...


class EscalationHandlerProtocol(Protocol):
    """M006 3.12節。Human Confirmation/Escalation(Terminal Outcome)。"""

    def build_confirmation_request(self, context: "CognitiveContext", reason: str) -> ConfirmationRequest:
        """到達理由(reason)とその時点のContextから、ユーザーへの確認
        リクエストを構築する。"""
        ...
