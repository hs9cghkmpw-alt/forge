"""Cognitive World Builder(FORGE-MILESTONE-007第一段階、M006 9章)。

DomainClassificationとIntentの両方から構築する(Blueprint Task4.4)。
既存Legacy`WorldModelBuilder.build(domain)`とは別クラスであり、
Cognitive経路ではこちらのみを使う。
"""

from __future__ import annotations

from forge_ai.core.domain_model import Domain
from forge_ai.core.intent_model import Intent
from forge_ai.core.orchestration.cognitive_types import DomainClassification
from forge_ai.core.world_model import Actor, Relationship, Rule, World, WorldObject


class CognitiveWorldBuilder:
    """`CognitiveWorldBuilderProtocol`を満たす。"""

    def build(self, classification: DomainClassification, intent: Intent) -> World:
        domain: Domain = classification.primary_domain

        # 1. Domain由来の基盤(既存WorldModelBuilderと同じ発想の、決定的な組み立て)。
        actors: list[Actor] = [Actor(name="user", role="primary_user")]
        objects: list[WorldObject] = [
            WorldObject(name=concept.name, attributes=(concept.description,))
            for concept in domain.typical_concepts
        ]
        relationships: list[Relationship] = [
            Relationship(subject="user", predicate=action, obj=domain.typical_concepts[0].name)
            for action in domain.typical_actions
            if domain.typical_concepts
        ]
        rules: list[Rule] = [
            Rule(description=f"'{concept.name}' には常に妥当な値が必要である。")
            for concept in domain.typical_concepts
        ]

        # 2. Intent由来の具体化(CEO指摘6への対応)。
        existing_object_names = {o.name for o in objects}
        for actor_name in intent.actors:
            if actor_name and actor_name not in {a.name for a in actors}:
                actors.append(Actor(name=actor_name, role="mentioned_actor"))
        for data_name in intent.required_data:
            if data_name and data_name not in existing_object_names:
                objects.append(WorldObject(name=data_name, attributes=("Intentが明示的に要求したデータ",)))
                existing_object_names.add(data_name)
        for constraint in intent.constraints:
            if constraint:
                rules.append(Rule(description=f"利用者からの制約: {constraint}"))

        return World(
            domain=domain,
            actors=tuple(actors),
            objects=tuple(objects),
            relationships=tuple(relationships),
            rules=tuple(rules),
        )
