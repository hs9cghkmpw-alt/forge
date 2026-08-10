"""World Model。

Domainから Actor / Object / Relationship / Rule を構築する。
World Modelは「この問題領域には具体的にどんな登場人物・モノ・関係・制約が
あるか」という、ドメインの静的な構造をモデル化する。ユーザーの自然文
(Meaning Model以降の責務)にはまだ触れない。
"""

from __future__ import annotations

from dataclasses import dataclass

from forge_ai.core.domain_model import Domain


@dataclass(frozen=True)
class Actor:
    """Worldに登場する人物・主体。"""

    name: str
    role: str  # 例: "user", "admin", "guest"


@dataclass(frozen=True)
class WorldObject:
    """Worldに登場する「モノ」。Python組み込みの`object`と衝突しないよう命名した。"""

    name: str
    attributes: tuple[str, ...]


@dataclass(frozen=True)
class Relationship:
    """ActorとWorldObject、またはWorldObject同士の関係。"""

    subject: str
    predicate: str  # 例: "owns", "manages", "records"
    obj: str


@dataclass(frozen=True)
class Rule:
    """Worldが守るべき制約。自然文の説明として保持する
    (今回は実行可能なルールエンジンまでは実装しない、静的な記述)。"""

    description: str


@dataclass(frozen=True)
class Event:
    """Worldで起こりうる出来事(M006 9章)。"""

    name: str
    description: str


@dataclass(frozen=True)
class StateDefinition:
    """WorldObjectが取りうる状態(M006 9章。Forge Runtimeの`State`とは
    別概念、ここではドメイン上の「状態」を指す。例:「予約」の状態が
    「仮予約/確定/キャンセル」等)。"""

    name: str
    possible_values: tuple[str, ...]


@dataclass(frozen=True)
class Permission:
    """Actorが持つ権限(M006 9章)。"""

    actor: str
    action: str


@dataclass(frozen=True)
class World:
    """1つのDomainに対応する、具体的なActor/Object/Relationship/Ruleの集合。

    FORGE-MILESTONE-007第一段階で、M006 9章が要求するEvents/States/
    Permissionsを、既定値(空タプル)付きで追加した(既存の
    `World(domain=..., actors=..., objects=..., relationships=...,
    rules=...)`という呼び出し方は無変更で動く)。Legacy経路
    (`WorldModelBuilder`、既存)は常にこれらを空のままにする。
    Cognitive経路(`understanding/world_builder.py`、新規)のみが
    実際に埋める。
    """

    domain: Domain
    actors: tuple[Actor, ...]
    objects: tuple[WorldObject, ...]
    relationships: tuple[Relationship, ...]
    rules: tuple[Rule, ...]
    events: tuple[Event, ...] = ()
    states: tuple[StateDefinition, ...] = ()
    permissions: tuple[Permission, ...] = ()


class WorldModelBuilder:
    """DomainからWorldを構築する。Domainのtypical_concepts/typical_actionsを
    材料にして、決定的にActor/Object/Relationship/Ruleを組み立てる
    (LLM Providerを必要としない、純粋な構造変換)。
    """

    def build(self, domain: Domain) -> World:
        """DomainのtypicalConcepts/typicalActionsから、決定的にWorldを組み立てる。"""
        actors = (Actor(name="user", role="primary_user"),)
        objects = tuple(
            WorldObject(name=concept.name, attributes=(concept.description,))
            for concept in domain.typical_concepts
        )
        relationships = tuple(
            Relationship(subject="user", predicate=action, obj=domain.typical_concepts[0].name)
            for action in domain.typical_actions
            if domain.typical_concepts
        )
        rules = tuple(
            Rule(description=f"'{concept.name}' には常に妥当な値が必要である。")
            for concept in domain.typical_concepts
        )
        return World(domain=domain, actors=actors, objects=objects, relationships=relationships, rules=rules)
