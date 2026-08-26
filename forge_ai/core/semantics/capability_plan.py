"""**役の組み合わせから、作るものの形を決める**
（GENERATED-UI-QG-V2-R4 / TD87、2026-08-26）。

---

## Capability Registry は語彙であって、生成結果ではない

`LEARNABLE-LOCAL-AI-VISION.md` §22 が言っているのはこれである。
Registry は「Forge が何を持っているか（語彙・制約・実装状態）」を
宣言する表であり、**Need を入れると画面が出てくる装置ではない。**

```
Need → 役 → 必要な Capability → Capability Plan → IR → Forge Language
                    ↑
            Registry は「それが在るか」を答えるだけ
```

Registry を引いて画面を返す設計にすると、Registry の行数が
「作れるアプリの種類」の上限になる。それが TD87
（8アプリが3種類の画面にしかならない）の形である。

## 専用 Template を作らない

`kids_template` / `photo_template` / `analytics_template` を作れば
8つの Need は「違う画面」になる。**それは対応したことにならない。**
9つ目の Need でまた同じ問題が起きる。

ここで使うのは一般的な primitive だけである。

* 記録する 1 件（Entity）と、その Field
* 一覧
* 集計（合計 / グループ別）
* 推移
* チェックの On/Off

## 分からなかったことを Plan に残す

`unsupported` を持つ。ゲームループも音の合成も Forge には無い。
**無いものを「checklist で代用」して黙るのが今までの壊れ方**だった。
持っていないなら Plan にそう書く。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from forge_ai.core.semantics.roles import (
    SemanticRole,
    SemanticRoleExtraction,
    extract_semantic_roles,
)

__all__ = [
    "CAPABILITY_REGISTRY",
    "CapabilityStatus",
    "CapabilityPlan",
    "PlanShape",
    "PlannedField",
    "plan_capabilities",
]


class CapabilityStatus(str, Enum):
    """**Forge がその能力を持っているか。** 実装状態の宣言。"""

    IMPLEMENTED = "implemented"
    PARTIAL = "partial"
    """出来るが本来の形ではない（写真を**文字で**記録する等）。"""

    MISSING = "missing"
    """**持っていない。** 代用して黙らない。"""


#: Capability の語彙と実装状態。**これは表であって、生成器ではない。**
#:
#: 行を足しても「作れるアプリの種類」は増えない。増えるのは
#: 「Forge が正直に名指しできるものの種類」である。
CAPABILITY_REGISTRY: dict[str, tuple[CapabilityStatus, str]] = {
    "record.entity": (CapabilityStatus.IMPLEMENTED, "1件分のデータを記録する"),
    "record.text": (CapabilityStatus.IMPLEMENTED, "文字を記録する"),
    "record.number": (CapabilityStatus.IMPLEMENTED, "数値を記録する"),
    "record.date": (CapabilityStatus.IMPLEMENTED, "日付を記録する"),
    "record.choice": (CapabilityStatus.IMPLEMENTED, "選択肢から選ぶ"),
    "record.photo": (
        CapabilityStatus.PARTIAL,
        "写真そのものは扱えない。ファイル名・説明を文字として記録する",
    ),
    "record.sound": (
        CapabilityStatus.PARTIAL,
        "音そのものは扱えない。名前・メモを文字として記録する",
    ),
    "view.list": (CapabilityStatus.IMPLEMENTED, "記録を一覧で見る"),
    "view.total": (CapabilityStatus.IMPLEMENTED, "合計・残高を出す"),
    "view.group_compare": (
        CapabilityStatus.IMPLEMENTED, "グループごとに集計して比べる",
    ),
    "view.trend": (
        CapabilityStatus.PARTIAL,
        "推移は**時系列グラフでは無い**。日付順の一覧と平均で近似する",
    ),
    "interact.check_off": (CapabilityStatus.IMPLEMENTED, "1件ずつ済みにする"),
    "interact.notify": (CapabilityStatus.MISSING, "通知は送れない"),
    "simulate.loop": (CapabilityStatus.MISSING, "ゲームループ・時間経過は無い"),
    "media.compose": (CapabilityStatus.MISSING, "音や画像を合成できない"),
}


class PlanShape(str, Enum):
    """**作るものの骨格。** Template 名ではない。

    Template は「この画面を出す」という指定である。Shape は
    「この道具は何をする道具か」という性質であり、同じ Shape でも
    Field が違えば別の画面になる。
    """

    CHECKLIST = "checklist"
    """1件ずつ済みにしていく。**記録する値を持たない。**"""

    RECORD_LOG = "record_log"
    """1件ずつ値を残して、一覧で見る。"""

    RECORD_LOG_WITH_TOTAL = "record_log_with_total"
    """記録 + 合計・残高。"""

    RECORD_LOG_WITH_GROUP_COMPARE = "record_log_with_group_compare"
    """記録 + グループごとの集計比較。"""

    RECORD_LOG_WITH_TREND = "record_log_with_trend"
    """記録 + 推移。"""

    UNKNOWN = "unknown"
    """**何も分からなかった。** 既定の checklist へ倒さない。"""


@dataclass(frozen=True)
class PlannedField:
    """記録する1つの値。**役から来たものだけ。**"""

    name: str
    label: str
    kind: str
    """`string` / `number` / `date` / `choice`。IR の `FieldType` と対応。"""

    measure: str = "unknown"
    """`additive`（足せる）/ `average`（平均する）/ `unknown`。"""

    capability: str = "record.text"
    origin_role: SemanticRole = SemanticRole.RECORDED_DATA


#: 正規化値 → 記録する Field の作り方。**一般的な primitive だけ。**
_FIELD_BLUEPRINT: dict[str, tuple[str, str, str, str]] = {
    # value: (name, label, kind, capability)
    "photo": ("photo", "写真", "string", "record.photo"),
    "note": ("note", "メモ", "string", "record.text"),
    "date": ("date", "日付", "date", "record.date"),
    "deadline": ("deadline", "期限", "date", "record.date"),
    "amount": ("amount", "金額", "number", "record.number"),
    "accuracy": ("accuracy", "正解率", "number", "record.number"),
    "difficulty": ("difficulty", "難易度", "number", "record.number"),
    "impression": ("impression", "手応え", "string", "record.text"),
    "mood": ("mood", "気分", "string", "record.text"),
    "weight": ("weight", "体重", "number", "record.number"),
    "height": ("height", "身長", "number", "record.number"),
    "place": ("place", "場所", "string", "record.text"),
    "kind": ("kind", "種類", "string", "record.text"),
    "condition": ("condition", "条件", "string", "record.text"),
    "result": ("result", "結果", "string", "record.text"),
    "sound": ("sound", "音", "string", "record.sound"),
}

#: 平均する量（合計しても意味が無いもの）。`CLAUDE.md` の Measure Semantics。
_AVERAGED_VALUES = frozenset({"accuracy", "difficulty", "weight", "height"})
_ADDITIVE_VALUES = frozenset({"amount"})

#: `MANAGED_OBJECT` / `ACTIVITY` → Entity の名前と表示名。
_SUBJECT_LABELS: dict[str, tuple[str, str]] = {
    "task": ("task", "やること"),
    "item": ("item", "品物"),
    "belonging": ("belonging", "持ち物"),
    "stock": ("stock", "在庫"),
    "word": ("word", "単語"),
    "plant": ("plant", "植物"),
    "song": ("song", "曲"),
    "book": ("book", "本"),
    "fish": ("fish", "魚"),
    "getting_ready": ("preparation_step", "支度"),
    "preparation": ("preparation_step", "準備"),
    "practice": ("practice_log", "練習"),
    "quiz": ("quiz_log", "出題"),
    "study": ("study_log", "学習"),
    "exercise": ("exercise_log", "運動"),
    "experiment": ("experiment_log", "実験"),
    "grow": ("growth_log", "育成"),
    "fishing": ("catch_log", "釣果"),
    "shopping": ("shopping_item", "買うもの"),
    "clinic_visit": ("visit_log", "通院"),
}

#: `CONTEXT` → グループ分けに使える次元の表示名。
#:
#: **CONTEXT だけでは Field にならない。** `DESIRED_VIEW` が
#: 「〜ごとに比べたい」と言ったときにだけ、比較の軸として昇格する。
_GROUPING_LABELS: dict[str, tuple[str, str]] = {
    "department": ("department", "部署"),
    "school": ("school", "学校"),
    "workplace": ("workplace", "職場"),
    "travel": ("trip", "旅行"),
    "meeting": ("meeting", "会議"),
    "store": ("store", "店"),
}


@dataclass(frozen=True)
class CapabilityPlan:
    """**この Need のために何を作るか。**"""

    roles: SemanticRoleExtraction
    shape: PlanShape
    entity_name: str = ""
    entity_label: str = ""
    fields: tuple[PlannedField, ...] = ()
    views: tuple[str, ...] = ()
    interactions: tuple[str, ...] = ()
    unsupported: tuple[str, ...] = field(default=())
    """**持っていない能力**。名指しして残す。代用して黙らない。"""

    partial: tuple[str, ...] = field(default=())
    """出来るが本来の形ではない能力。"""

    @property
    def is_actionable(self) -> bool:
        """**IR を組めるだけの材料が揃っているか。**"""
        return self.shape is not PlanShape.UNKNOWN and bool(self.entity_label)

    def to_dict(self) -> dict[str, object]:
        """Decision Trace / Evidence へそのまま載せる。"""
        return {
            "shape": self.shape.value,
            "entity": self.entity_name,
            "fields": [f.name for f in self.fields],
            "views": list(self.views),
            "interactions": list(self.interactions),
            "unsupported": list(self.unsupported),
            "partial": list(self.partial),
            "roles": self.roles.to_dict(),
        }


def _subject_of(roles: SemanticRoleExtraction) -> tuple[str, str]:
    """Entity の名前と表示名。**ACTOR / CONTEXT からは作らない。**

    「子ども」からEntityを作ると「こどもの成長」になる。それが TD89。
    """
    # **ACTOR / CONTEXT の値は、表に載っていても採らない。**
    #
    # 配線破壊試験で分かったこと（M11、2026-08-26）: 下の for が
    # 構造役だけを回っていても、それを守っていたのは**表の中身**で
    # あって、コードではなかった。`_SUBJECT_LABELS` に `travel` を
    # 1行足せば、この関数は黙って「旅行」を Entity にする。
    #
    # 規則をコード側にも置き、静的検査（`test_semantic_roles_and_
    # capability_plan.py`）で表の中身も固定する。二重にする。
    forbidden = set(roles.of(SemanticRole.ACTOR)) | set(roles.of(SemanticRole.CONTEXT))
    for role in (SemanticRole.MANAGED_OBJECT, SemanticRole.ACTIVITY, SemanticRole.SUBJECT):
        for value in roles.of(role):
            if value in forbidden:
                continue
            if value in _SUBJECT_LABELS:
                return _SUBJECT_LABELS[value]
    return ("", "")


def _subject_of_role(
    roles: SemanticRoleExtraction, role: SemanticRole,
) -> tuple[str, str] | None:
    """その役から主題ラベルを引く。**ACTOR / CONTEXT には使わない。**"""
    if role in (SemanticRole.ACTOR, SemanticRole.CONTEXT):
        msg = f"{role.value} を主題にしてはならない"
        raise ValueError(msg)
    for value in roles.of(role):
        if value in _SUBJECT_LABELS:
            return _SUBJECT_LABELS[value]
    return None


def _shape_of(roles: SemanticRoleExtraction, fields: tuple[PlannedField, ...]) -> PlanShape:
    views = set(roles.of(SemanticRole.DESIRED_VIEW))
    # **チェックして消す道具に、記録する値は要らない。**
    if "check_off" in views and not fields:
        return PlanShape.CHECKLIST
    if not fields:
        return PlanShape.CHECKLIST if "check_off" in views else PlanShape.UNKNOWN
    if views & {"compare", "aggregate", "chart"}:
        return PlanShape.RECORD_LOG_WITH_GROUP_COMPARE
    if "trend" in views:
        return PlanShape.RECORD_LOG_WITH_TREND
    if views & {"total", "balance"}:
        return PlanShape.RECORD_LOG_WITH_TOTAL
    return PlanShape.RECORD_LOG


def plan_capabilities(text: str) -> CapabilityPlan:
    """Need から Capability Plan を作る。**決定的**。

    Domain 名は1つも出てこない。出てくるのは役と、その役から必要になる
    能力だけである。
    """
    roles = extract_semantic_roles(text)
    if roles.is_empty:
        return CapabilityPlan(roles=roles, shape=PlanShape.UNKNOWN)

    fields: list[PlannedField] = []
    for value in roles.of(SemanticRole.RECORDED_DATA):
        blueprint = _FIELD_BLUEPRINT.get(value)
        if blueprint is None:
            continue
        name, label, kind, capability = blueprint
        fields.append(PlannedField(
            name=name, label=label, kind=kind, capability=capability,
            measure=(
                "additive" if value in _ADDITIVE_VALUES
                else "average" if value in _AVERAGED_VALUES
                else "unknown"
            ),
        ))

    views = set(roles.of(SemanticRole.DESIRED_VIEW))

    # **CONTEXT が Field へ昇格するのは、比較を求められたときだけ。**
    #
    # 「部署ごとの売上を比べたい」は、部署を記録しなければ比べられない。
    # 一方「旅行の写真を残したい」の旅行は、記録すべき値ではなく場面で
    # ある。求められた view が違うので、扱いも違ってよい。
    #
    # **`group_by` だけでは昇格させない**（実装中に踏んだ）。
    # 「日付ごとに残して」の「ごと」で `group_by` が立ち、CONTEXT の
    # 「旅行」が Field へ昇格して**写真1枚ごとに「旅行」欄**が出た。
    # 「〜ごと」は日付でも成立する——**比較（compare / aggregate）を
    # 明示的に求められたときだけ**、軸として記録する必要が生まれる。
    if views & {"compare", "aggregate"}:
        for value in roles.of(SemanticRole.CONTEXT):
            grouping = _GROUPING_LABELS.get(value)
            if grouping is not None:
                name, label = grouping
                fields.insert(0, PlannedField(
                    name=name, label=label, kind="string",
                    capability="record.text", origin_role=SemanticRole.CONTEXT,
                ))
                break

    entity_name, entity_label = _subject_of(roles)

    # **記録する主題そのものを1件目の欄にする**（実描画で見て直した）。
    #
    # Round 4 の2回目、「英単語を出題して、正解率の推移を見たい」が
    # **正解率の欄しか無い**画面になっていた。どの単語の正解率なのかを
    # 入れる場所が無い。「植物を育てながら…」も同じで、植物の名前を
    # 入れられなかった。
    #
    # `MANAGED_OBJECT` は**数えられる対象**である。数えられるものには
    # 1件ずつの名前が要る。Need ごとの表ではなく、役の性質から出る規則。
    managed = _subject_of_role(roles, SemanticRole.MANAGED_OBJECT)
    if managed and fields:
        name, label = managed
        if all(f.name != name for f in fields):
            fields.insert(0, PlannedField(
                name=name, label=label, kind="string",
                capability="record.text", origin_role=SemanticRole.MANAGED_OBJECT,
            ))

    field_tuple = tuple(fields)
    shape = _shape_of(roles, field_tuple)

    if shape is not PlanShape.UNKNOWN and not entity_label:
        # 主題が取れないが記録する値はある。
        #
        # **記録している値そのものから名乗る**（実描画で見て直した）。
        # Round 4 の1回目、写真アプリもデータ分析アプリも両方
        # 「記録」という名前になっていた。間違いではないが、
        # 何の道具か分からない。
        #
        # 利用者が実際に使った語（`surface`）を使う。「売上」「写真」は
        # 要求文の一部だが、**1語の名詞は名前である**（`naming.py` の
        # `is_name_like` が判定する）。文を写しているわけではない。
        #
        # Domain 表は引かない。**役から名乗る。**
        recorded = roles.surfaces_of(SemanticRole.RECORDED_DATA)
        first = next(
            (s for s in recorded
             if any(f.origin_role is SemanticRole.RECORDED_DATA for f in field_tuple)),
            "",
        )
        entity_name = "record"
        entity_label = f"{first}記録" if first else "記録"

    planned_views: list[str] = ["view.list"]
    interactions: list[str] = []
    if shape is PlanShape.CHECKLIST:
        planned_views = []
        interactions.append("interact.check_off")
    elif shape is PlanShape.RECORD_LOG_WITH_GROUP_COMPARE:
        planned_views.append("view.group_compare")
    elif shape is PlanShape.RECORD_LOG_WITH_TREND:
        planned_views.append("view.trend")
    elif shape is PlanShape.RECORD_LOG_WITH_TOTAL:
        planned_views.append("view.total")

    # **持っていない能力を名指しする。**
    requested = set(f.capability for f in field_tuple) | set(planned_views) | set(interactions)
    if roles.has(SemanticRole.EFFECT):
        requested.add("interact.notify")
    activities = set(roles.of(SemanticRole.ACTIVITY))
    if "combine" in activities:
        requested.add("media.compose")
    if "grow" in activities and "combine" in activities:
        requested.add("simulate.loop")

    unsupported = tuple(sorted(
        c for c in requested
        if CAPABILITY_REGISTRY.get(c, (CapabilityStatus.MISSING, ""))[0]
        is CapabilityStatus.MISSING
    ))
    partial = tuple(sorted(
        c for c in requested
        if CAPABILITY_REGISTRY.get(c, (CapabilityStatus.MISSING, ""))[0]
        is CapabilityStatus.PARTIAL
    ))

    return CapabilityPlan(
        roles=roles, shape=shape,
        entity_name=entity_name, entity_label=entity_label,
        fields=field_tuple, views=tuple(planned_views),
        interactions=tuple(interactions),
        unsupported=unsupported, partial=partial,
    )
