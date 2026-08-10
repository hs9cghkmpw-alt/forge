"""CognitiveDependencies(FORGE-MILESTONE-007第一段階)。

`docs/spec/FORGE_M007_IMPLEMENTATION_BLUEPRINT.md` v1.3 Task3.1に対応。
各Protocol実装を1つのdataclassへまとめ、`CognitiveOrchestrator`へ単一の
引数として渡す(`**`展開は行わない。dataclassは`**`展開に対応しない)。

第一段階では、`compiler`・`quality_engine`(Legacy/Cognitive共有)のみ
`forge_ai.contracts.interfaces`(Legacy Protocol定義ファイル)から型を
importする。他は全て`forge_ai.contracts.cognitive_interfaces`。
"""

from __future__ import annotations

from dataclasses import dataclass

from forge_ai.contracts.cognitive_interfaces import (
    AmbiguityDetectorProtocol,
    CognitiveDomainClassifierProtocol,
    CognitiveIntentRecognizerProtocol,
    CognitiveMeaningExtractorProtocol,
    CognitivePlannerProtocol,
    CognitiveWorldBuilderProtocol,
    DesignCriticProtocol,
    EscalationHandlerProtocol,
    InputNormalizerProtocol,
    RequirementExtractorProtocol,
    RevisionEngineProtocol,
    TemplateSelectorProtocol,
)
from forge_ai.contracts.interfaces import CompilerProtocol, QualityEngineProtocol


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
