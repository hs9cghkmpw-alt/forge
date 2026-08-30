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
from forge_ai.core.ir.design_intent import DesignIntentSelector
from forge_ai.core.ir.entity_synthesizer import EntitySynthesizer


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
    # FORGE-PRODUCT-VISION-002(2026-08-12)新規。Curated Domain Library
    # (`ir_generator.py`の手書きテーブル)に無いDomainについて、記録する
    # データ構造をAIに合成させる(`entity_synthesizer.py`参照)。
    #
    # **既定を`None`にしている理由**: このフィールドを必須にすると、
    # 既にこのdataclassを直接構築している箇所(テストフィクスチャ等)を
    # 壊さないため型上は`None`を許す。ただし`None`はChecklistへ
    # フォールバックしてよいという意味ではない。Capability Planが明示的
    # CHECKLISTの場合だけlegacy compilerを使い、それ以外で合成手段が無い
    # 場合はCapability Gapとしてfail-closedする。実運用の組み立て
    # (`_default_cognitive_dependencies()`)では必ず注入される。
    entity_synthesizer: EntitySynthesizer | None = None

    # FORGE-R1(2026-08-17)新規。Design Languageの意味的役割をAIに選ばせる
    # (`design_intent.py`参照)。
    #
    # `entity_synthesizer`と同じく既定は`None`である。注入しなければ
    # Compilerが構造から決めた既定のroleだけになり、**以前と完全に同じ
    # 出力**になる。Design Languageが入ったせいで生成が落ちるのは
    # 本末転倒なので、純粋な追加にしてある。
    design_intent_selector: "DesignIntentSelector | None" = None
