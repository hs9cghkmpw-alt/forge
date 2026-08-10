"""Contracts(Interface First)。

キックオフ指示書10章「Interface First」「Dependency Injection」に対応する、
各パイプライン段階の抽象契約(Protocol)。具体的な実装クラス
(core/*.py, repair/repair_engine.py, quality/quality_engine.py)は
これらのProtocolを構造的に満たす(Pythonの`Protocol`は`implements`宣言不要の
構造的部分型付けであるため、既存クラスに変更を加える必要はない)。

このファイルはどの具体的な実装クラスもimportしない
(依存方向: 具体実装 → Protocol、逆方向は禁止)。
"""

from __future__ import annotations

from typing import Protocol

from forge_ai.core.compiler import ForgeIRDocument
from forge_ai.core.domain_model import Domain
from forge_ai.core.intent_model import Intent
from forge_ai.core.meaning_model import ExtractedMeaning
from forge_ai.core.planner import ApplicationPlan
from forge_ai.core.world_model import World
from forge_ai.quality.quality_engine import QualityScore
from forge_ai.repair.repair_engine import RepairIssue, RepairResult


class MeaningExtractorProtocol(Protocol):
    """`MeaningExtractor`が満たす契約: テキストからMeaningを抽出する。"""

    def extract(self, text: str, world: World) -> ExtractedMeaning:
        """ユーザーの自然文とWorld(参照のみ)からExtractedMeaningを構築する。"""
        ...


class IntentBuilderProtocol(Protocol):
    """`IntentBuilder`が満たす契約: MeaningからIntentを構築する。"""

    def build(self, meaning: ExtractedMeaning, world: World) -> Intent:
        """ExtractedMeaningとWorldからIntentを構築する。"""
        ...


class PlannerProtocol(Protocol):
    """`Planner`が満たす契約: IntentからApplication Planを生成する。"""

    def plan(self, intent: Intent) -> ApplicationPlan:
        """IntentからRuntime非依存のApplicationPlanを生成する。"""
        ...


class CompilerProtocol(Protocol):
    """`Compiler`が満たす契約: Application PlanからForge IRを生成する。

    FORGE v0.3 Template-aware Compiler Stage1対応:
    `domain_category`(省略可能、既定`None`)を追加した。Data Model
    定義を持つDomain(fishing_log/household_budget/habit_tracking等)
    向けの2画面構成(一覧+入力フォーム)を生成するために使う。省略時
    (`None`)は既存のChecklist単一画面のまま(後方互換)。
    """

    def compile(self, plan: ApplicationPlan, *, domain_category: str | None = None) -> ForgeIRDocument:
        """ApplicationPlanをForge IR(ForgeIRDocument)へコンパイルする。"""
        ...


class RepairEngineProtocol(Protocol):
    """`RepairEngine`が満たす契約: 検証エラーをもとにForge IRを自己修正する。"""

    def repair(self, ir: ForgeIRDocument, issues: tuple[RepairIssue, ...]) -> RepairResult:
        """Forge IRと問題一覧から、修正済みのRepairResultを返す。"""
        ...


class QualityEngineProtocol(Protocol):
    """`QualityEngine`が満たす契約: Forge IRの品質を数値化する。"""

    def evaluate(self, ir: ForgeIRDocument, plan: ApplicationPlan) -> QualityScore:
        """Forge IRとApplication PlanからQualityScoreを算出する。"""
        ...


class DomainResolverProtocol(Protocol):
    """`DomainRegistry`が満たす契約。"""

    def resolve_from_keywords(self, text: str) -> Domain:
        """テキスト中のキーワードから最も一致するDomainを推定する。"""
        ...


class WorldModelBuilderProtocol(Protocol):
    """`WorldModelBuilder`が満たす契約: DomainからWorldを構築する。"""

    def build(self, domain: Domain) -> World:
        """DomainからActor/Object/Relationship/Ruleを備えたWorldを構築する。"""
        ...
