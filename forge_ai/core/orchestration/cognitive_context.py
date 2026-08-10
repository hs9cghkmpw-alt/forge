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

    def with_decision(self, trace: DecisionTrace) -> "CognitiveContext":
        return dataclasses.replace(self, decision_trace=self.decision_trace + (trace,))

    def with_revision_attempt_incremented(self) -> "CognitiveContext":
        return dataclasses.replace(self, revision_attempt=self.revision_attempt + 1)
