"""**役の組み合わせから、作るものを決める**
（GENERATED-UI-QG-V2-R4 / FORGE-020A2、2026-08-26）。

---

## Capability Registry は語彙であって、生成結果ではない

`LEARNABLE-LOCAL-AI-VISION.md` §22 が言っているのはこれである。
Registry は「Forge が何を持っているか」を宣言する表であり、
**Need を入れると画面が出てくる装置ではない。**

Registry を引いて画面を返す設計にすると、Registry の行数が
「作れるアプリの種類」の上限になる。それが TD87 の形だった。

**Capability の表はここに無い。**
`forge_ai/core/semantics/capabilities.py` が唯一の場所である
（020A2 §1。R4 まではここに2つ目の表があり、会話側と ID が食い違って
いた）。

## 020A2 §2: 排他的な Shape をやめた

R4 の `PlanShape` は

    RECORD_LOG_WITH_TOTAL
    RECORD_LOG_WITH_GROUP_COMPARE
    RECORD_LOG_WITH_TREND

という**組み合わせ enum** だった。複数の見せ方を求められると1つしか
選べず、**残りは黙って捨てられていた**。修正前の実測:

```
「部署ごとの売上を比較して、合計と月別推移も見たい」
  役 : group_by, compare, total, trend   ← 4つ要求している
  結果: view.list, view.group_compare    ← total と trend が消えた
```

`RECORD_LOG_WITH_TOTAL_AND_TREND` を足すのは**禁止**である。組み合わせの
数だけ enum が増え、5つ目で破綻する。

**直交する成分に分けた。**

| 成分 | 何を言うか |
|---|---|
| `structure` | どういうデータ構造か（`StructuralMode`） |
| `fields` | 1件ごとに何を残すか |
| `views` | 何を見たいか（**集合**。1つ選ばない） |
| `interactions` | 画面で何をするか |
| `effects` | 外へ何をするか |
| `partial` / `missing` | **出来ないと分かっていること** |

「どういう構造か」と「何を見たいか」は別の軸である。

## 要求は必ずどこかに現れる

`requested` に入ったものは、`views` / `interactions` / `effects` /
`fields` / `partial` / `missing` の**どれかに必ず現れる**
（`test_everything_requested_is_accounted_for` が固定する）。

消えるのと「出来ないと言われる」のは違う。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from forge_ai.core.semantics.capabilities import (
    SEMANTIC_CAPABILITIES,
    SupportLevel,
)
from forge_ai.core.semantics.roles import (
    SemanticRole,
    SemanticRoleExtraction,
    extract_semantic_roles,
)

class UnknownCapabilityError(LookupError):
    """**Catalog に無い Capability ID が Plan から出た。**

    利用者の要求の問題ではなく、`capability_plan.py` と
    `capabilities.py` の食い違いである。MISSING で握り潰すと、
    「作れません」という嘘の説明になって表に出る。
    """

    def __init__(self, capability_id: str) -> None:
        super().__init__(
            f"Catalog に無い Capability ID: {capability_id!r}。"
            " forge_ai/core/semantics/capabilities.py へ足すか、"
            " Plan 側の綴りを直すこと（MISSING へ倒さない）",
        )
        self.capability_id = capability_id


__all__ = [
    "CapabilityPlan",
    "PlannedField",
    "StructuralMode",
    "plan_capabilities",
    "UnknownCapabilityError",
]


class StructuralMode(str, Enum):
    """**どういうデータ構造の道具か。** 見せ方は含まない。

    view を足しても、この enum は増えない。それが R4 との違いである。
    """

    UNKNOWN = "unknown"
    """**何も分からなかった。** 既定の checklist へ倒さない。"""

    CHECKLIST = "checklist"
    """1件ずつ済みにしていく。**記録する値を持たない。**"""

    RECORD_ENTITY = "record_entity"
    """1件ずつ値を残す。合計も比較も推移も、**この構造の上の見せ方**である。"""


@dataclass(frozen=True)
class PlannedField:
    """記録する1つの値。**役から来たものだけ。**"""

    name: str
    label: str
    kind: str
    """`string` / `number` / `date` / `choice`。IR の `FieldType` と対応。"""

    measure: str = "unknown"
    """`additive`（足せる）/ `average`（平均する）/ `unknown`。"""

    capability: str = "data.text"
    """**Canonical Capability ID**（`capabilities.py`）。"""

    origin_role: SemanticRole = SemanticRole.RECORDED_DATA


#: 正規化値 → 記録する Field の作り方。**一般的な primitive だけ。**
#:
#: `capability` は Canonical ID である（`record.text` のような別名は
#: 020A2 で廃止した）。
_FIELD_BLUEPRINT: dict[str, tuple[str, str, str, str]] = {
    # value: (name, label, kind, canonical capability id)
    "photo": ("photo", "写真", "string", "data.photo"),
    "note": ("note", "メモ", "string", "data.text"),
    "date": ("date", "日付", "date", "data.date"),
    "deadline": ("deadline", "期限", "date", "data.date"),
    "amount": ("amount", "金額", "number", "data.number"),
    "accuracy": ("accuracy", "正解率", "number", "data.number"),
    "difficulty": ("difficulty", "難易度", "number", "data.number"),
    "impression": ("impression", "手応え", "string", "data.text"),
    "mood": ("mood", "気分", "string", "data.text"),
    "weight": ("weight", "体重", "number", "data.number"),
    "height": ("height", "身長", "number", "data.number"),
    "place": ("place", "場所", "string", "data.text"),
    "kind": ("kind", "種類", "string", "data.text"),
    "condition": ("condition", "条件", "string", "data.text"),
    "result": ("result", "結果", "string", "data.text"),
    "sound": ("sound", "音", "string", "data.audio"),
}

#: 平均する量（合計しても意味が無いもの）。`CLAUDE.md` の Measure Semantics。
_AVERAGED_VALUES = frozenset({"accuracy", "difficulty", "weight", "height"})
_ADDITIVE_VALUES = frozenset({"amount"})

#: **見たい形 → Canonical Capability ID。**
#:
#: `elif` ではない。**役に現れたものを全部引く**——ここが 020A2 の要点で
#: ある。1つ選ぶ構造だったから、残りが消えていた。
_VIEW_CAPABILITIES: dict[str, str] = {
    "list": "view.list",
    "total": "view.metric",
    "balance": "view.metric",
    "aggregate": "view.group_compare",
    "compare": "view.group_compare",
    # **`group_by` だけでは比較を求めていない**（020A2 §6 で気付いた）。
    #
    # 「日付ごとに残して」の「ごと」は並べ方の話であって、
    # 「部署ごとに比べたい」の比較とは違う。ここを同じ扱いにしていたので、
    # 写真アプリが **comparison-first** の画面になっていた。
    #
    # `group_by` は役としては残る（`roles`）。**Capability の要求では
    # ない**というだけである。
    "chart": "view.bar_chart",
    "trend": "view.trend",
    "filter": "interact.filter",
}

#: 画面での操作 → Canonical ID。
_INTERACTION_CAPABILITIES: dict[str, str] = {
    "check_off": "interact.check_off",
}

#: 外への作用 → Canonical ID。
_EFFECT_CAPABILITIES: dict[str, str] = {
    "notify": "effect.notify",
}

#: 行い → 「Forge が持っていない振る舞い」の Canonical ID。
_ACTIVITY_CAPABILITIES: dict[str, tuple[str, ...]] = {}

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

#: `CONTEXT` → 比較の軸として使える次元。
_GROUPING_LABELS: dict[str, tuple[str, str]] = {
    "department": ("department", "部署"),
    "school": ("school", "学校"),
    "workplace": ("workplace", "職場"),
    "travel": ("trip", "旅行"),
    "meeting": ("meeting", "会議"),
    "store": ("store", "店"),
    "team": ("team", "チーム"),
}


@dataclass(frozen=True)
class CapabilityPlan:
    """**この Need のために何を作るか。**

    直交する成分を持つ。1つを選んで残りを捨てる構造にしない。
    """

    roles: SemanticRoleExtraction
    structure: StructuralMode

    entity_name: str = ""
    entity_label: str = ""
    fields: tuple[PlannedField, ...] = ()

    views: tuple[str, ...] = ()
    """**集合である。** `view.list` と `view.metric` と `view.trend` は
    同時に成立する。"""

    interactions: tuple[str, ...] = ()
    effects: tuple[str, ...] = ()
    simulations: tuple[str, ...] = ()
    """時間経過・生成的な振る舞い。View/Effectへ混ぜず独立軸で保持する。"""

    structure_capabilities: tuple[str, ...] = ()
    """構造そのものが満たす Capability（`data.entity` 等）。

    Field にも View にも現れないが**要求は満たされている**。ここが無いと
    「要求されたのにどこにも記録されていない」判定に引っかかる。
    """

    requested: tuple[str, ...] = ()
    """**利用者が求めた Capability 全部。** 出来た / 出来ないの前の姿。

    `requested` にあって他のどこにも無い ID は、**黙って消えた**という
    ことである。テストがそれを落とす。
    """

    partial: tuple[str, ...] = field(default=())
    """出来るが本来の形ではないもの。"""

    missing: tuple[str, ...] = field(default=())
    """**持っていないもの。** 名指しして残す。代用して黙らない。"""

    @property
    def is_actionable(self) -> bool:
        """**IR を組めるだけの材料が揃っているか。**"""
        return self.structure is not StructuralMode.UNKNOWN and bool(self.entity_label)

    @property
    def unsupported(self) -> tuple[str, ...]:
        """R4 までの名前。**`missing` の別名として残す**（呼び出し側互換）。"""
        return self.missing

    def limitations(self) -> tuple[tuple[str, str], ...]:
        """**何が出来ないのか**を、利用者へ見せられる言葉で返す。

        `(capability_id, 説明)`。Catalog の `limitation` を引く——
        ここで文言を書かない（また2箇所になる）。
        """
        found: list[tuple[str, str]] = []
        for capability_id in (*self.missing, *self.partial):
            definition = SEMANTIC_CAPABILITIES.get(capability_id)
            if definition is not None and definition.limitation:
                found.append((capability_id, definition.limitation))
        return tuple(found)

    def to_dict(self) -> dict[str, object]:
        """Decision Trace / Evidence へそのまま載せる。"""
        return {
            "structure": self.structure.value,
            "entity": self.entity_name,
            "fields": [f.name for f in self.fields],
            "views": list(self.views),
            "interactions": list(self.interactions),
            "effects": list(self.effects),
            "structure_capabilities": list(self.structure_capabilities),
            "requested": list(self.requested),
            "partial": list(self.partial),
            "missing": list(self.missing),
            "roles": self.roles.to_dict(),
        }


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


def _subject_of(roles: SemanticRoleExtraction) -> tuple[str, str]:
    """Entity の名前と表示名。**ACTOR / CONTEXT からは作らない。**

    「子ども」から Entity を作ると「こどもの成長」になる。それが TD89。

    配線破壊試験（M11）で分かったこと: 下の for が構造役だけを回っていても、
    それを守っていたのは**表の中身**であってコードではなかった。
    `_SUBJECT_LABELS` に `travel` を1行足せば、黙って「旅行」を Entity に
    する。規則をコード側にも置く。
    """
    forbidden = set(roles.of(SemanticRole.ACTOR)) | set(roles.of(SemanticRole.CONTEXT))
    for role in (SemanticRole.MANAGED_OBJECT, SemanticRole.ACTIVITY, SemanticRole.SUBJECT):
        for value in roles.of(role):
            if value in forbidden:
                continue
            if value in _SUBJECT_LABELS:
                return _SUBJECT_LABELS[value]
    return ("", "")


def _classify(requested: set[str]) -> tuple[tuple[str, ...], tuple[str, ...], tuple[str, ...]]:
    """要求を **出来る / 一部 / 出来ない** へ分ける。

    判定は Catalog の `SupportLevel` だけを見る。**ここで status を
    書かない**——書いた時点で2つ目の Source of Truth になる。
    """
    ok: list[str] = []
    partial: list[str] = []
    missing: list[str] = []
    for capability_id in sorted(requested):
        definition = SEMANTIC_CAPABILITIES.get(capability_id)
        if definition is None:
            # **知らない ID を MISSING へ倒さない**（020A3B §4、2026-08-27）。
            #
            # 以前はここで `missing.append()` していた。それは
            # 「Forge がその能力を持っていない」という**利用者向けの事実**
            # だが、実際に起きているのは**綴りを間違えた**か
            # **Catalog へ足し忘れた**である。
            #
            # 黙って MISSING になると:
            #
            # * 利用者へ「それは作れません」と嘘を言う
            # * `capability_gap` に内部 ID が出る
            # * Catalog への追加漏れが永久に気付かれない
            #
            # **未知の semantic ID は設定/実装の誤りである。** 落とす。
            raise UnknownCapabilityError(capability_id)
        if definition.support is SupportLevel.IMPLEMENTED:
            ok.append(capability_id)
        elif definition.support is SupportLevel.PARTIAL:
            ok.append(capability_id)
            partial.append(capability_id)
        else:
            missing.append(capability_id)
    return tuple(ok), tuple(partial), tuple(missing)


def plan_capabilities(text: str) -> CapabilityPlan:  # noqa: PLR0912 — 段の見通しを優先
    """Need から Capability Plan を作る。**決定的**。

    Domain 名は1つも出てこない。出てくるのは役と、その役から必要になる
    Capability だけである。
    """
    roles = extract_semantic_roles(text)
    if roles.is_empty:
        return CapabilityPlan(roles=roles, structure=StructuralMode.UNKNOWN)

    requested: set[str] = set()
    activities = set(roles.of(SemanticRole.ACTIVITY))

    # -- 1件ごとに残す値 ------------------------------------------------
    fields: list[PlannedField] = []
    for value in roles.of(SemanticRole.RECORDED_DATA):
        # 「音を組み合わせる」の音は記録Fieldではなくミキサーの素材。
        # 同じ表層語を無条件にdata.audioへ落とすと、ゲームに意味のない
        # 音声ファイル名入力欄が生える。役の組み合わせで権限を限定する。
        if value == "sound" and "combine" in activities:
            continue
        blueprint = _FIELD_BLUEPRINT.get(value)
        if blueprint is None:
            continue
        name, label, kind, capability_id = blueprint
        requested.add(capability_id)
        fields.append(PlannedField(
            name=name, label=label, kind=kind, capability=capability_id,
            measure=(
                "additive" if value in _ADDITIVE_VALUES
                else "average" if value in _AVERAGED_VALUES
                else "unknown"
            ),
        ))

    view_values = set(roles.of(SemanticRole.DESIRED_VIEW))

    # **CONTEXT が Field へ昇格するのは、比較を求められたときだけ。**
    #
    # 「〜ごと」だけでは昇格させない（R4 で踏んだ）——「日付ごとに残して」
    # の「ごと」で写真1枚ごとに「旅行」欄が出ていた。
    if view_values & {"compare", "aggregate"}:
        for value in roles.of(SemanticRole.CONTEXT):
            grouping = _GROUPING_LABELS.get(value)
            if grouping is not None:
                name, label = grouping
                requested.add("data.text")
                fields.insert(0, PlannedField(
                    name=name, label=label, kind="string",
                    capability="data.text", origin_role=SemanticRole.CONTEXT,
                ))
                break

    wants_check_off = "check_off" in view_values

    # -- 数えられる対象には1件ずつの名前が要る --------------------------
    #
    # 「済みにしていく」道具は値を持たない（checklist）。それ以外で
    # 数えられる対象があるなら、**その対象自体が記録の1件**である
    # ——「作業を記録して…比べたい」に記録欄が無いのはおかしい。
    managed = _subject_of_role(roles, SemanticRole.MANAGED_OBJECT)
    if managed and not wants_check_off:
        name, label = managed
        if all(f.name != name for f in fields):
            requested.add("data.text")
            fields.insert(0, PlannedField(
                name=name, label=label, kind="string",
                capability="data.text", origin_role=SemanticRole.MANAGED_OBJECT,
            ))

    field_tuple = tuple(fields)

    # -- 構造（見せ方とは独立） -----------------------------------------
    if field_tuple:
        structure = StructuralMode.RECORD_ENTITY
    elif wants_check_off:
        structure = StructuralMode.CHECKLIST
    else:
        structure = StructuralMode.UNKNOWN

    # -- 見せ方（**集合**。1つ選ばない） --------------------------------
    for value in view_values:
        capability_id = _VIEW_CAPABILITIES.get(value)
        if capability_id is not None:
            requested.add(capability_id)
    if structure is StructuralMode.RECORD_ENTITY:
        # 記録する道具は、必ず一覧を持つ。
        requested.add("view.list")
        requested.add("data.entity")
        requested.add("interact.edit")

    # -- 画面での操作 / 外への作用 --------------------------------------
    if wants_check_off:
        requested.add(_INTERACTION_CAPABILITIES["check_off"])
    for value in roles.of(SemanticRole.EFFECT):
        capability_id = _EFFECT_CAPABILITIES.get(value)
        if capability_id is not None:
            requested.add(capability_id)
    for value in roles.of(SemanticRole.ACTIVITY):
        for capability_id in _ACTIVITY_CAPABILITIES.get(value, ()):
            requested.add(capability_id)

    if "combine" in activities:
        recorded_values = set(roles.of(SemanticRole.RECORDED_DATA))
        if "sound" in recorded_values:
            requested.add("interact.audio_mix")
        else:
            # Object of "combine" is not resolved to sound. Do not pretend the
            # narrower audio mixer satisfies generic image/media composition.
            requested.add("effect.media_compose")

    # **ゲームは「育てる」と「組み合わせる」が揃ったときに要求される。**
    if "grow" in activities and "combine" in activities:
        requested.add("simulate.loop")

    ok, partial, missing = _classify(requested)

    entity_name, entity_label = _subject_of(roles)
    if structure is StructuralMode.RECORD_ENTITY and not entity_label:
        # 主題が取れないが記録する値はある。**記録している値そのものから
        # 名乗る**（R4 の実描画で「記録」ばかりになったので直した）。
        recorded = roles.surfaces_of(SemanticRole.RECORDED_DATA)
        first = next(iter(recorded), "")
        entity_name = "record"
        entity_label = f"{first}記録" if first else "記録"

    # 出来ると判定されたものを、層ごとに仕分ける。
    views = tuple(c for c in ok if c.startswith("view."))
    interactions = tuple(c for c in ok if c.startswith("interact."))
    effects = tuple(c for c in ok if c.startswith("effect."))
    simulations = tuple(c for c in ok if c.startswith("simulate."))
    field_capabilities = {f.capability for f in field_tuple}
    structure_capabilities = tuple(
        c for c in ok if c.startswith("data.") and c not in field_capabilities
    )

    return CapabilityPlan(
        roles=roles, structure=structure,
        entity_name=entity_name, entity_label=entity_label,
        fields=field_tuple,
        views=views, interactions=interactions, effects=effects, simulations=simulations,
        structure_capabilities=structure_capabilities,
        requested=tuple(sorted(requested)),
        partial=partial, missing=missing,
    )
