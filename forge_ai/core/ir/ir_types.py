"""FORGE IR v1 — 型定義(Phase1、最小実装)。

`FORGE-IR-V1-PROPOSAL.md`(Architecture Proposal)の4章「IR Data
Model」に基づく。`ApplicationPlan`と`ForgeDocument`(Forge Language)の
間に挿入される、プラットフォーム非依存の中間表現。

**今回実装しないもの(指示書「FORGE v0.6 開発指示」の制約通り、正直な
申告)**:

* `Relationship`(Entity間の関係) — ADR-003・Proposal 2章参照。
  Stage1の3 Domain(fishing_log/household_budget/habit_tracking)は
  いずれも単一Entityのみで、Entity間の関係を必要としないため。
* Entity単位の横断Validation(`EntityValidationRule`、例:
  「開始日は終了日より前」のようなField横断ルール) — Proposal 5章で
  「優先度低・任意拡張」としたものと同じ理由(需要が実証されていない
  機能の先行実装を避けるため)。Field単位のValidation(`Field.
  validations`)のみ実装する。

このモジュールは`forge_ai`の他のモジュール(Planner・Compiler等)へ
一切依存しない、独立したデータ構造のみを定義する(Proposal 0章
「IRは複数のコンパイル先を平等に扱う」という設計思想を反映し、
Forge Language固有の概念——Widget名・state_ref・JSON構造——は含めない。
ADR-003参照)。
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class FieldType(str, Enum):
    """Fieldの値の型。プラットフォーム非依存の抽象的なデータ型のみを
    列挙する(入力Widgetの種類は含めない、ADR-003)。"""

    STRING = "string"
    NUMBER = "number"
    BOOLEAN = "boolean"
    DATE = "date"
    CHOICE = "choice"


@dataclass(frozen=True)
class FieldValidationRule:
    """Field単位のValidationルール。Forge Language v1.2の
    `validation.rules`(required/min/max/min_length/max_length/
    pattern)と同じ語彙を、IR層でも(Forge Language非依存な形で)
    再利用する。"""

    type: str  # "required" | "min" | "max" | "min_length" | "max_length" | "pattern"
    message: str
    value: object | None = None  # min/max/patternの場合の閾値・正規表現


@dataclass(frozen=True)
class Field:
    """Entityが持つ1つのField。"""

    name: str
    label: str
    type: FieldType
    required: bool = True
    choices: tuple[str, ...] = ()  # type=CHOICEの場合のみ使用
    validations: tuple[FieldValidationRule, ...] = ()
    # v1.8新規(FORGE-AI-QUALITY-001、2026-08-11)。type=NUMBERのFieldが
    # 両方とも指定している場合のみ、Forge Language Compilerが
    # `slider`Widget(構造的に範囲外の値を入力できない)を選ぶ判断材料と
    # して使う。どちらか一方でも`None`の場合は、従来通り`text_field`+
    # 数値patternのバリデーションのままにする(スライダーには
    # 「有限の範囲」が必須であり、根拠なく上限/下限を発明しないため)。
    min_value: float | None = None
    max_value: float | None = None


@dataclass(frozen=True)
class Entity:
    """アプリが扱うデータの型そのもの(例: FishRecord・Transaction・
    Habit)。Template-aware Compiler Stage1の`DomainDataModel`に相当する
    概念を、IR層へ格上げしたもの。

    `name`は`identifier`パターン(小文字スネークケース)を推奨する
    (Forge Language v1.3提案の`record_schemas`キー命名規則と揃える
    ため)。`label`は画面表示用の人間可読な名称(例: "釣果記録")。

    `visual_style`(FORGE v1.0 Product Quality Sprint1新規)は、この
    Entityの「雰囲気・トーン」を表す、プラットフォーム非依存な性質
    (例: "calm"・"warm"・"vibrant"・"neutral")。具体的な色コード・
    Corner Radius・Widget名はIRへ含めない(ADR-012の方針を維持)——
    これらはCompiler側が`visual_style`というヒントから選ぶ。一方、
    「落ち着いた雰囲気」「温かみのある雰囲気」という抽象的な性質
    自体は、どのプラットフォーム(Flutter/React/SwiftUI等)の
    Compiler Backendにとっても意味を持つ情報であるため、IR層に
    置くことが妥当と判断した。
    """

    name: str
    label: str
    fields: tuple[Field, ...]
    visual_style: str = "calm"

    def field_names(self) -> tuple[str, ...]:
        return tuple(f.name for f in self.fields)


class ViewKind(str, Enum):
    """Viewの種類。レイアウト(card/table等)やWidget選択はIRに含めず、
    「一覧を見せたい」「入力を受け付けたい」「詳細を見せたい」という
    **意図**のみを表現する(Proposal 3章、ADR-003)。"""

    LIST = "list"
    FORM = "form"
    DETAIL = "detail"


@dataclass(frozen=True)
class View:
    """画面の意図(1つ)。"""

    id: str
    kind: ViewKind
    entity: str  # Entity.nameへの参照
    display_fields: tuple[str, ...] = ()  # 空 = 全Field(Entity.field_names()の順)
    mode: str | None = None  # kind=FORMの場合のみ: "create" | "edit"


class ActionKind(str, Enum):
    """抽象的な操作の種類。Forge Languageでの実現方法(composite/
    add_item/reset_state等)はIRには一切現れない(ADR-003)。"""

    CREATE_ENTITY = "create_entity"
    UPDATE_ENTITY = "update_entity"
    DELETE_ENTITY = "delete_entity"
    NAVIGATE = "navigate"


@dataclass(frozen=True)
class Action:
    """抽象的な操作(1つ)。"""

    id: str
    kind: ActionKind
    entity: str | None = None  # CREATE/UPDATE/DELETE_ENTITYの場合、対象Entity.nameへの参照
    target_view: str | None = None  # NAVIGATEの場合、遷移先View.idへの参照


class EventTrigger(str, Enum):
    """Viewで発生しうる、ユーザー操作の種類。"""

    SUBMIT = "submit"
    TAP = "tap"


@dataclass(frozen=True)
class Event:
    """ViewとActionを結びつける(「このViewでこの操作が起きたら、この
    Actionを実行する」)。Forge Language Compilerが、これを実際の
    Action JSON(submit_action等)へ変換する際の入力になる。"""

    id: str
    trigger: EventTrigger
    source_view: str  # View.idへの参照
    action: str  # Action.idへの参照


@dataclass(frozen=True)
class NavigationGraph:
    """View間の遷移グラフ。

    **Stage1の3 Domainについての注記**: 現在のForge Language
    Compilerは、List ViewとForm Viewを**単一のForge Language画面**へ
    畳み込む(Template-aware Compiler Stage1、Proposal 3.3節)。その
    ため、今回生成するIRの`edges`は空(遷移が不要)になる。Forge
    Language側が複数画面構成に対応した時点で、`edges`が意味を持つ
    ようになる設計(IR自体は変更不要)。
    """

    initial_view: str  # View.idへの参照
    edges: tuple[tuple[str, str], ...] = ()  # (from_view_id, to_view_id)


@dataclass(frozen=True)
class ForgeIR:
    """FORGE IR v1 のルート。"""

    entities: tuple[Entity, ...]
    views: tuple[View, ...]
    actions: tuple[Action, ...]
    events: tuple[Event, ...]
    navigation: NavigationGraph

    def referential_integrity_errors(self) -> tuple[str, ...]:
        """View・Action・Eventの参照整合性を検査する。テスト・デバッグ
        両方から使う想定の、副作用の無い検査メソッド。"""
        errors: list[str] = []
        entity_names = {e.name for e in self.entities}
        view_ids = {v.id for v in self.views}
        action_ids = {a.id for a in self.actions}

        for v in self.views:
            if v.entity not in entity_names:
                errors.append(f"View '{v.id}' references unknown entity '{v.entity}'")
            entity = next((e for e in self.entities if e.name == v.entity), None)
            if entity is not None:
                known_fields = set(entity.field_names())
                for f in v.display_fields:
                    if f not in known_fields:
                        errors.append(f"View '{v.id}' references unknown field '{f}' on entity '{v.entity}'")

        for a in self.actions:
            if a.entity is not None and a.entity not in entity_names:
                errors.append(f"Action '{a.id}' references unknown entity '{a.entity}'")
            if a.target_view is not None and a.target_view not in view_ids:
                errors.append(f"Action '{a.id}' references unknown target_view '{a.target_view}'")

        for ev in self.events:
            if ev.source_view not in view_ids:
                errors.append(f"Event '{ev.id}' references unknown source_view '{ev.source_view}'")
            if ev.action not in action_ids:
                errors.append(f"Event '{ev.id}' references unknown action '{ev.action}'")

        if self.navigation.initial_view not in view_ids:
            errors.append(f"NavigationGraph.initial_view '{self.navigation.initial_view}' is not a known view")
        for from_id, to_id in self.navigation.edges:
            if from_id not in view_ids:
                errors.append(f"NavigationGraph edge references unknown view '{from_id}'")
            if to_id not in view_ids:
                errors.append(f"NavigationGraph edge references unknown view '{to_id}'")

        return tuple(errors)
