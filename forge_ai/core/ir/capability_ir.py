"""**Capability Plan から IR を組む**
（GENERATED-UI-QG-V2-R4 / TD87、2026-08-26）。

---

## この module が置き換えるもの

以前、Curated Domain にも当たらず AI 合成も出来なかった Need は、
**全部 checklist へ落ちていた**。写真・データ分析・学習・ゲーム・
作業記録・子ども向けの6つが構造的に同一になっていたのはこれである
（TD87）。

その fallback は「作れないものを、作れる形に見せる」処理だった。

ここでは、`CapabilityPlan`（役から決まった、記録する値と見せ方）を
そのまま `EntitySpec` にする。**Domain 名は1つも出てこない。**

## 専用 Template を足していない

`kids_template` / `photo_template` は作らない。使うのは
`IRGenerator.build_from_spec()` ——**Curated Domain と AI 合成が
既に通っている、同じ入口**である。ここから先は3者を区別しない。

## 出せないものは出さない

`CapabilityPlan.is_actionable` が `False`（役が取れなかった）なら
`None` を返す。**既定の形へ倒さない。**
"""

from __future__ import annotations

from forge_ai.core.ir.ir_generator import EntitySpec, FieldSpec
from forge_ai.core.ir.ir_types import FieldType, MeasureSemantics
from forge_ai.core.semantics.capability_plan import CapabilityPlan, PlanShape

__all__ = ["entity_spec_from_plan", "visual_style_for_plan"]

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

#: Shape → 見た目のトーン。**Domain ごとの色表ではない。**
#:
#: 「比べる道具」と「毎日つける道具」は性格が違う、という一般的な
#: 対応だけを置く。Need が増えても行は増えない。
_SHAPE_STYLES: dict[PlanShape, str] = {
    PlanShape.CHECKLIST: "warm",
    PlanShape.RECORD_LOG: "calm",
    PlanShape.RECORD_LOG_WITH_TOTAL: "neutral",
    PlanShape.RECORD_LOG_WITH_GROUP_COMPARE: "vibrant",
    PlanShape.RECORD_LOG_WITH_TREND: "vibrant",
}


def visual_style_for_plan(plan: CapabilityPlan) -> str:
    return _SHAPE_STYLES.get(plan.shape, "calm")


def entity_spec_from_plan(plan: CapabilityPlan) -> EntitySpec | None:
    """Plan を `EntitySpec` にする。**組めなければ `None`。**

    `CHECKLIST` は Entity を持たない道具なので、ここでは組まない
    （`ForgeLanguageCompiler` の checklist 経路が受け持つ）。
    """
    if not plan.is_actionable or plan.shape is PlanShape.CHECKLIST:
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
