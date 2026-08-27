"""CognitiveContext(FORGE-MILESTONE-007第一段階)。

`docs/spec/FORGE_M007_IMPLEMENTATION_BLUEPRINT.md` v1.3 Task2で定義された、
Cognitive Pipelineを通して流れる、単一のImmutableなContextオブジェクト。
"""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass

from forge_ai.core.intent_model import Intent
from forge_ai.core.orchestration.cognitive_types import (
    AmbiguityReport,
    CriticReport,
    DecisionTrace,
    DomainClassification,
    ExtractedMeaning,
    NormalizedInput,
    RequirementSet,
    TemplateSelection,
)
from forge_ai.core.ir.design_intent import DesignIntent
from forge_ai.core.semantics.capability_plan import CapabilityPlan
# **構造の出所の型は1箇所にしか置かない**（020A2 §1/§3、merge 時に統合）。
#
# 020A2 と 020A3 が別々にこの4型を定義していた。同じ値の enum が2つ
# あると `is` 比較が常に False になる——TD85（`Deployment` enum が2つ）
# で実際に踏んだ形である。ここでは**再輸出するだけ**にする。
from forge_ai.core.semantics.structure_provenance import (  # noqa: F401 — 再輸出
    EntitySynthesisAttempt,
    EntitySynthesisRejectionReason,
    StructureProvenance,
    StructureProvider,
    StructureSource,
)
from forge_ai.core.planner import ApplicationPlan
from forge_ai.core.world_model import World


@dataclass(frozen=True)
class CognitiveContext:
    """`ir`(Forge IR)・`initial_quality`はここへ含めない
    (Blueprint 2.1節: これらはPipelineの「最終出力」であり、途中経過を
    表すContextの責務とは区別する。`CognitivePipelineSuccess`が別途保持する)。
    """

    # 常に存在(Pipeline開始時に確定)
    raw_input: str
    started_at: str  # ISO8601

    # 各Transformation Stageが完了するたびに埋まる(未完了はNone)
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
    # FORGE-R1-CLOSURE-015(2026-08-17)新規。AIが選んだDesign Roleと、
    # Forgeが既定で埋めた軸。**他のStage出力と同じ扱い**にしてある。
    #
    # Decision Traceの文字列から復元する案もあったが、書式が変わるたびに
    # 静かに壊れる。「後から文字列を読んで意味を取り出す」設計は、
    # 読む側が壊れたことに気付けない。
    design_intent: "DesignIntent | None" = None

    capability_plan: "CapabilityPlan | None" = None
    """役から決まった「何を作るか」（GENERATED-UI-QG-V2-R4、2026-08-26）。

    **Decision Trace の文字列に頼らない。** `design_intent` を Context へ
    持たせたのと同じ理由である——後から由来を取り出すのに書式へ依存すると、
    reason の書き方を変えただけで Evidence が壊れる。
    """

    structure_provenance: StructureProvenance = StructureProvenance()
    """**構造を誰が作ったか**（020A2 §3 / 020A3）。

    `source`（どの段） / `provider`（どの種類の AI） / `task`（どの stage）
    の**3つで1つの事実**なので、まとめて持つ。別々の欄にすると片方だけ
    更新してずれる。Decision Trace の文字列からは復元しない。
    """

    entity_synthesis_attempt: EntitySynthesisAttempt = EntitySynthesisAttempt()
    """AI の Entity 合成を**試したか / 受け取ったか / なぜ落としたか**。

    「試したが落とした」と「そもそも試していない」は違う。区別できないと
    Local Model が伸びているのかどうかが分からない。
    """

    # Pipeline全体を通して蓄積
    decision_trace: tuple[DecisionTrace, ...] = ()

    # ループ制御(Preliminary/Final再計画とCognitive Revisionが共有する単一カウンタ)
    revision_attempt: int = 0
    max_revision_attempts: int = 2

    def with_normalized_input(self, value: NormalizedInput) -> "CognitiveContext":
        return dataclasses.replace(self, normalized_input=value)

    def with_ambiguity_report(self, value: AmbiguityReport) -> "CognitiveContext":
        return dataclasses.replace(self, ambiguity_report=value)

    def with_intent(self, value: Intent) -> "CognitiveContext":
        return dataclasses.replace(self, intent=value)

    def with_domain_classification(self, value: DomainClassification) -> "CognitiveContext":
        return dataclasses.replace(self, domain_classification=value)

    def with_world(self, value: World) -> "CognitiveContext":
        return dataclasses.replace(self, world=value)

    def with_meaning(self, value: ExtractedMeaning) -> "CognitiveContext":
        return dataclasses.replace(self, meaning=value)

    def with_requirements(self, value: RequirementSet) -> "CognitiveContext":
        return dataclasses.replace(self, requirements=value)

    def with_preliminary_candidates(self, value: tuple[str, ...]) -> "CognitiveContext":
        return dataclasses.replace(self, preliminary_candidates=value)

    def with_plan(self, value: ApplicationPlan) -> "CognitiveContext":
        return dataclasses.replace(self, plan=value)

    def with_template_selection(self, value: TemplateSelection) -> "CognitiveContext":
        return dataclasses.replace(self, template_selection=value)

    def with_critic_report(self, value: CriticReport) -> "CognitiveContext":
        return dataclasses.replace(self, critic_report=value)

    def with_design_intent(self, value: "DesignIntent") -> "CognitiveContext":
        return dataclasses.replace(self, design_intent=value)

    def with_capability_plan(self, value: "CapabilityPlan") -> "CognitiveContext":
        return dataclasses.replace(self, capability_plan=value)

    def with_structure_provenance(self, value: StructureProvenance) -> "CognitiveContext":
        return dataclasses.replace(self, structure_provenance=value)

    def with_entity_synthesis_attempt(self, value: EntitySynthesisAttempt) -> "CognitiveContext":
        return dataclasses.replace(self, entity_synthesis_attempt=value)

    def with_decision(self, trace: DecisionTrace) -> "CognitiveContext":
        return dataclasses.replace(self, decision_trace=self.decision_trace + (trace,))

    def with_revision_attempt_incremented(self) -> "CognitiveContext":
        return dataclasses.replace(self, revision_attempt=self.revision_attempt + 1)
