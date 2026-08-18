"""数値Fieldの**量の性質**（`MeasureSemantics`）の検査
(FORGE-R1-CLOSURE-015 §2、2026-08-17)。

---

## 直した実バグ

v1.11のHero KPIは「Entityの最初のNUMBER Fieldを合計する」だった。
その結果、本番経路で実際に次が生成されていた（再現済み）。

```
読書記録  rating(評価5段階) → 評価の合計
釣果記録  size(サイズcm)   → 魚のサイズの合計
```

**「数値である」ことと「足すと意味のある量である」ことは別**なのに、
型だけで後者を推測していた。分からないものを「合計できる」という
楽観側へ倒していた（`CLAUDE.md` §3）。

## このファイルが守っているもの

型だけを根拠にKPIを発明しないこと。とくに**UNKNOWNを合計へ倒さない**
こと——倒した瞬間に上の2件が復活する。
"""

from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))  # forge_ai/ はrepoルート直下

from app.ai.validators.schema_validator import validate_forge_document  # noqa: E402
from forge_ai.core.ir import ir_generator as ir_gen  # noqa: E402
from forge_ai.core.ir.forge_language_compiler import ForgeLanguageCompiler  # noqa: E402
from forge_ai.core.ir.ir_generator import EntitySpec, FieldSpec, IRGenerator  # noqa: E402
from forge_ai.core.ir.ir_types import (  # noqa: E402
    FieldType,
    MeasureSemantics,
    preferred_aggregate,
)


def _walk(widget: dict):
    yield widget
    for child in widget.get("children", []) or ():
        yield from _walk(child)


def _metrics(document: dict) -> list[dict]:
    return [w for s in document["screens"] for w in _walk(s["body"]) if w["type"] == "metric_view"]


def _compile(spec: EntitySpec) -> dict:
    ir = IRGenerator().build_from_spec(spec)
    return ForgeLanguageCompiler().compile(ir, domain_category="x", title="t").to_json_dict()


def _one_number_entity(measure: MeasureSemantics, *, name: str = "value") -> EntitySpec:
    return EntitySpec(
        "thing", "もの",
        (
            FieldSpec("title", "名前", field_type=FieldType.STRING),
            FieldSpec(name, "値", field_type=FieldType.NUMBER, measure=measure),
        ),
    )


class TestTheSemanticDecidesTheAggregate(unittest.TestCase):
    """量の性質 → その量について**最初に知りたいこと**。"""

    def test_additive_is_summed(self) -> None:
        self.assertEqual(preferred_aggregate(MeasureSemantics.ADDITIVE), "sum")

    def test_averageable_is_never_summed(self) -> None:
        """「評価の合計が42」は何も言っていない。"""
        self.assertEqual(preferred_aggregate(MeasureSemantics.AVERAGEABLE), "average")

    def test_a_level_shows_the_latest_value(self) -> None:
        """体温・体重・残高。知りたいのは「今いくつか」である。"""
        self.assertEqual(preferred_aggregate(MeasureSemantics.LEVEL), "latest")

    def test_an_extremum_shows_the_maximum(self) -> None:
        self.assertEqual(preferred_aggregate(MeasureSemantics.EXTREMUM), "max")

    def test_an_identifier_produces_no_kpi(self) -> None:
        """年号・部屋番号。数値の形をしているだけで、量ではない。"""
        self.assertIsNone(preferred_aggregate(MeasureSemantics.IDENTIFIER))

    def test_unknown_produces_no_kpi(self) -> None:
        """**この1件が§2の本体。** 分からないものを合計へ倒さない。"""
        self.assertIsNone(preferred_aggregate(MeasureSemantics.UNKNOWN))


class TestTheCuratedDomainsDeclareTheirMeasures(unittest.TestCase):
    """実際に壊れていた2 Domainを名指しで固定する。"""

    def _measure(self, domain: str, field_name: str) -> MeasureSemantics:
        spec = ir_gen._ENTITY_DEFINITIONS[domain]
        return next(f.measure for f in spec.field_specs if f.name == field_name)

    def test_a_rating_is_not_additive(self) -> None:
        self.assertIs(self._measure("reading_log", "rating"), MeasureSemantics.AVERAGEABLE)

    def test_a_fish_size_is_not_additive(self) -> None:
        self.assertIs(self._measure("fishing_log", "size"), MeasureSemantics.EXTREMUM)

    def test_money_is_additive(self) -> None:
        self.assertIs(self._measure("household_budget", "amount"), MeasureSemantics.ADDITIVE)

    def test_a_stock_quantity_is_additive(self) -> None:
        self.assertIs(self._measure("inventory", "quantity"), MeasureSemantics.ADDITIVE)


class TestTheGeneratedAppUsesTheRightAggregate(unittest.TestCase):
    """Compilerまで届いていること。宣言しただけで使われていない、を防ぐ。"""

    def _hero(self, domain: str) -> dict | None:
        document = _compile(ir_gen._ENTITY_DEFINITIONS[domain])
        heroes = [m for m in _metrics(document) if m.get("style_role") == "metric.primary"]
        return heroes[0] if heroes else None

    def test_a_reading_log_averages_the_rating(self) -> None:
        hero = self._hero("reading_log")
        self.assertEqual(hero["aggregate"], "average")
        self.assertEqual(hero["value_field"], "rating")
        self.assertIn("平均", hero["label"], "『合計』と書いてあるのに平均、を作らない")

    def test_a_fishing_log_shows_the_biggest_catch(self) -> None:
        hero = self._hero("fishing_log")
        self.assertEqual(hero["aggregate"], "max")
        self.assertEqual(hero["value_field"], "size")

    def test_an_inventory_sums_the_quantity(self) -> None:
        hero = self._hero("inventory")
        self.assertEqual(hero["aggregate"], "sum")

    def test_an_unknown_number_gets_no_kpi(self) -> None:
        """**出せるからといって出さない。**"""
        document = _compile(_one_number_entity(MeasureSemantics.UNKNOWN))
        self.assertEqual(_metrics(document), [])

    def test_an_identifier_number_gets_no_kpi(self) -> None:
        document = _compile(_one_number_entity(MeasureSemantics.IDENTIFIER))
        self.assertEqual(_metrics(document), [])

    def test_a_level_shows_the_latest(self) -> None:
        document = _compile(_one_number_entity(MeasureSemantics.LEVEL))
        self.assertEqual(_metrics(document)[0]["aggregate"], "latest")

    def test_additive_wins_when_several_numbers_are_meaningful(self) -> None:
        """「全部でいくら」は「一番大きかったのは」より主KPIに向く。"""
        spec = EntitySpec(
            "thing", "もの",
            (
                FieldSpec("title", "名前", field_type=FieldType.STRING),
                FieldSpec("best", "自己ベスト", field_type=FieldType.NUMBER,
                          measure=MeasureSemantics.EXTREMUM),
                FieldSpec("spent", "金額", field_type=FieldType.NUMBER,
                          measure=MeasureSemantics.ADDITIVE),
            ),
        )
        hero = _metrics(_compile(spec))[0]
        self.assertEqual(hero["value_field"], "spent")
        self.assertEqual(hero["aggregate"], "sum")

    def test_every_generated_document_stays_valid(self) -> None:
        for domain in sorted(ir_gen._ENTITY_DEFINITIONS):
            with self.subTest(domain=domain):
                result = validate_forge_document(_compile(ir_gen._ENTITY_DEFINITIONS[domain]))
                self.assertTrue(result.valid, [e.to_dict() for e in result.errors])


class TestTheAiChoosesTheMeasure(unittest.TestCase):
    """合成経路（AIがEntityを設計する）でも、量の性質はAIが選ぶ。"""

    def _sanitize(self, raw: dict):
        from forge_ai.core.ir.entity_synthesizer import _sanitize_one_field

        return _sanitize_one_field(raw, entity_name="thing", seen_names=set())

    def test_a_valid_measure_is_accepted(self) -> None:
        spec = self._sanitize(
            {"name": "amount", "label": "金額", "type": "number", "measure": "additive"}
        )
        self.assertIs(spec.measure, MeasureSemantics.ADDITIVE)

    def test_an_invented_measure_falls_back_to_unknown(self) -> None:
        """**ADDITIVEへ倒さない。** 倒すと「評価の合計」が復活する。"""
        spec = self._sanitize(
            {"name": "score", "label": "点", "type": "number", "measure": "summable"}
        )
        self.assertIs(spec.measure, MeasureSemantics.UNKNOWN)

    def test_a_missing_measure_falls_back_to_unknown(self) -> None:
        spec = self._sanitize({"name": "score", "label": "点", "type": "number"})
        self.assertIs(spec.measure, MeasureSemantics.UNKNOWN)

    def test_a_non_numeric_field_never_carries_a_measure(self) -> None:
        """文字列に「足せる量か」を問う意味が無い。"""
        spec = self._sanitize(
            {"name": "memo", "label": "メモ", "type": "string", "measure": "additive"}
        )
        self.assertIs(spec.measure, MeasureSemantics.UNKNOWN)

    def test_the_prompt_offers_the_closed_option_set(self) -> None:
        from forge_ai.prompt.prompt_builder import PromptBuilder

        prompt = PromptBuilder().build_entity_synthesis_prompt(
            user_text="x", plan_summary={}, domain_name="y"
        )
        for option in ("additive", "averageable", "level", "extremum", "identifier", "unknown"):
            self.assertIn(option, prompt.system)


if __name__ == "__main__":
    unittest.main()
