"""**Capability Plan から IR と画面の性格を決める**
（GENERATED-UI-QG-V2-R4 / FORGE-020A2 §6、2026-08-26）。

---

## この module が置き換えたもの

R4 より前、Curated Domain にも当たらず AI 合成も出来なかった Need は
**全部 checklist へ落ちていた**（TD87）。「作れないものを、作れる形に
見せる」処理だった。

ここでは `CapabilityPlan`（役から決まった、記録する値と見せ方）を
そのまま `EntitySpec` にする。**Domain 名は1つも出てこない。**

通る入口は `IRGenerator.build_from_spec()` ——Curated Domain と AI 合成が
既に通っている、**同じ入口**である。ここから先は3者を区別しない。

## 020A2 §6（TD91）: 見た目を Capability の構成から決める

R4 では `record_log` 系のアプリが**全部同じ3タブ CRUD**で始まっていた。
写真アプリもデータ分析アプリも、入口の見た目が同じだった。

**専用の photo UI / analytics UI を作らない。**
`kids_template` を作れば8つは違って見えるが、9つ目でまた同じ問題が起きる。

代わりに、Plan の**構成**から画面の性格を導く。

| Capability の構成 | 画面の性格 |
|---|---|
| `data.photo` がある | media-first（見るものが主役） |
| `view.trend` がある | summary-first（まとめが先） |
| `view.group_compare` がある | comparison-first（比べるのが先） |
| どれも無い | input-first（入れて並べる） |

これは Template の選択ではない。**同じ record entity のまま、
Capability の構成だけで性格が変わる。**
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from forge_ai.core.ir.ir_generator import EntitySpec, FieldSpec
from forge_ai.core.ir.ir_types import FieldType, MeasureSemantics
from forge_ai.core.semantics.capability_plan import CapabilityPlan, StructuralMode

__all__ = [
    "LayoutEmphasis",
    "compose_layout",
    "entity_spec_from_plan",
    "visual_style_for_plan",
]

_FIELD_TYPES: dict[str, FieldType] = {
    "string": FieldType.STRING,
    "number": FieldType.NUMBER,
    "date": FieldType.DATE,
    "choice": FieldType.CHOICE,
    "boolean": FieldType.BOOLEAN,
}

_MEASURES: dict[str, MeasureSemantics] = {
    "additive": MeasureSemantics.ADDITIVE,
    "average": MeasureSemantics.AVERAGEABLE,
    "unknown": MeasureSemantics.UNKNOWN,
}


class LayoutEmphasis(str, Enum):
    """**画面で何が主役か。** Template 名ではない。

    Need ごとに増えない——増えるのは Capability の組み合わせであって、
    この enum ではない。
    """

    INPUT_FIRST = "input_first"
    """入れて並べる。記録が主役。"""

    MEDIA_FIRST = "media_first"
    """見るものが主役（写真・音）。"""

    SUMMARY_FIRST = "summary_first"
    """まとめ・推移が主役。"""

    COMPARISON_FIRST = "comparison_first"
    """比べることが主役。"""

    TASK_FIRST = "task_first"
    """済みにしていくことが主役（checklist）。"""

    NONE = "none"
    """**何も分からなかった。** 既定へ倒さない。"""


#: 性格 → 雰囲気。**Domain ごとの色表ではない。**
_EMPHASIS_STYLES: dict[LayoutEmphasis, str] = {
    LayoutEmphasis.TASK_FIRST: "warm",
    LayoutEmphasis.MEDIA_FIRST: "warm",
    LayoutEmphasis.INPUT_FIRST: "calm",
    LayoutEmphasis.SUMMARY_FIRST: "vibrant",
    LayoutEmphasis.COMPARISON_FIRST: "vibrant",
    LayoutEmphasis.NONE: "calm",
}

#: media を主役にする Capability。
_MEDIA_CAPABILITIES = frozenset({"data.photo", "data.audio"})


def compose_layout(plan: CapabilityPlan) -> LayoutEmphasis:
    """**Capability の構成から画面の性格を決める**（TD91）。

    優先順は「利用者がわざわざ言ったこと」が上である。比較や推移は
    明示的に求めないと出てこない語だが、写真は記録対象の1つとして
    自然に出る——だから比較・推移を先に見る。
    """
    if plan.structure is StructuralMode.UNKNOWN:
        return LayoutEmphasis.NONE
    if plan.structure is StructuralMode.CHECKLIST:
        return LayoutEmphasis.TASK_FIRST

    views = set(plan.views)
    if "view.group_compare" in views:
        return LayoutEmphasis.COMPARISON_FIRST
    if "view.trend" in views or "view.metric" in views:
        return LayoutEmphasis.SUMMARY_FIRST
    if any(f.capability in _MEDIA_CAPABILITIES for f in plan.fields):
        return LayoutEmphasis.MEDIA_FIRST
    return LayoutEmphasis.INPUT_FIRST


def visual_style_for_plan(plan: CapabilityPlan) -> str:
    return _EMPHASIS_STYLES.get(compose_layout(plan), "calm")


@dataclass(frozen=True)
class _Unused:
    """（将来 IR へ渡す追加情報の置き場。今は空。）"""


def entity_spec_from_plan(plan: CapabilityPlan) -> EntitySpec | None:
    """Plan を `EntitySpec` にする。**組めなければ `None`。**

    `CHECKLIST` は Entity を持たない道具なので、ここでは組まない
    （`ForgeLanguageCompiler` の checklist 経路が受け持つ）。
    """
    if not plan.is_actionable or plan.structure is not StructuralMode.RECORD_ENTITY:
        return None
    if not plan.fields:
        return None

    specs: list[FieldSpec] = []
    for index, planned in enumerate(plan.fields):
        specs.append(FieldSpec(
            name=planned.name,
            label=planned.label,
            field_type=_FIELD_TYPES.get(planned.kind, FieldType.STRING),
            # **最初の1つだけ必須。** 全部必須にすると、記録する前に
            # 全部埋めさせる道具になる。
            required=index == 0,
            measure=_MEASURES.get(planned.measure, MeasureSemantics.UNKNOWN),
        ))

    return EntitySpec(
        name=plan.entity_name or "record",
        label=plan.entity_label or "記録",
        field_specs=tuple(specs),
        visual_style=visual_style_for_plan(plan),
    )
