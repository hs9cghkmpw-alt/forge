"""FieldSpecのmetadataが補正で失われないこと(FORGE-016A §2、2026-08-24)。

---

## 直した実バグ（再現済み）

`EntitySynthesizer`には「1つもrequiredが無ければ最初の項目を必須に
する」補正がある（何も入力せずに空レコードを追加できてしまうため）。

その補正が**FieldSpecを手で組み直しており、`measure`を書き写し忘れて
いた**。

```
AI:  amount / number / measure=additive / required=false
             ↓ 必須へ補正
実際: amount / number / measure=unknown  / required=true
```

R1で入れた「足せる量か」が失われるので、**Hero KPI（残高など）が
出なくなる**。しかもエラーにはならないので気付けない。

## なぜ`replace`にしたか

手で書き写す方式は、**属性が増えるたびに書き写し忘れの機会が増える**。
`unit` / `currency` / `temporal_semantics` を足す予定があるので、
同じ事故がまた起きる。

`FieldSpec`をfrozen dataclassにして`dataclasses.replace`で1属性だけ
変える形にした。**書き写す場所が無くなれば、書き忘れも起きない。**

## このファイルが守っているもの

「requiredだけが変わり、他は全部そのまま」を、metadataの種類ごとに
固定する。
"""

from __future__ import annotations

import dataclasses
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))  # forge_ai/ はrepoルート直下

from forge_ai.core.ir.entity_synthesizer import EntitySynthesizer  # noqa: E402
from forge_ai.core.ir.ir_generator import FieldSpec  # noqa: E402
from forge_ai.core.ir.ir_types import FieldType, MeasureSemantics  # noqa: E402


def _sanitize(raw_fields: list[dict]) -> tuple[FieldSpec, ...]:
    """本番の補正処理をそのまま呼ぶ。"""
    synthesizer = EntitySynthesizer.__new__(EntitySynthesizer)
    return EntitySynthesizer._sanitize_fields(synthesizer, raw_fields, entity_name="thing")


class TestTheRequiredCorrectionKeepsEveryOtherAttribute(unittest.TestCase):
    """**requiredだけが変わる。** 他は1つも変わらない。"""

    def test_every_measure_survives_the_correction(self) -> None:
        """全MeasureSemanticsについて確認する。

        `additive`だけ通っても意味が無い——次に足される値で同じことが
        起きる。
        """
        for measure in MeasureSemantics:
            with self.subTest(measure=measure.value):
                specs = _sanitize([
                    {"name": "value", "label": "値", "type": "number",
                     "measure": measure.value, "required": False},
                    {"name": "memo", "label": "メモ", "type": "string", "required": False},
                ])
                self.assertTrue(specs[0].required, "補正が効いていない")
                self.assertIs(
                    specs[0].measure, measure,
                    f"required補正で measure={measure.value} が失われた",
                )

    def test_only_required_changes(self) -> None:
        """**属性を1つずつ突き合わせる。**

        「measureだけ守る」テストにすると、次に足すmetadataで同じ事故が
        起きる。`dataclasses.fields()`で全属性を回すので、属性が増えても
        このテストが自動でそれを見る。
        """
        raw = {
            "name": "amount", "label": "金額", "type": "number",
            "measure": "additive", "required": False,
        }
        before = _sanitize([raw, {"name": "memo", "label": "メモ", "type": "string",
                                  "required": True}])[0]
        after = _sanitize([raw, {"name": "memo", "label": "メモ", "type": "string",
                                 "required": False}])[0]

        self.assertFalse(before.required, "前提が崩れている(補正前はFalseのはず)")
        self.assertTrue(after.required)
        for field in dataclasses.fields(FieldSpec):
            if field.name == "required":
                continue
            with self.subTest(attribute=field.name):
                self.assertEqual(
                    getattr(before, field.name), getattr(after, field.name),
                    f"required補正で '{field.name}' まで変わっている",
                )

    def test_bounded_numbers_keep_their_range(self) -> None:
        """min/maxが消えると`slider`が`text_field`へ落ちる。"""
        specs = _sanitize([
            {"name": "rating", "label": "評価", "type": "number",
             "min_value": 1, "max_value": 5, "measure": "averageable", "required": False},
            {"name": "memo", "label": "メモ", "type": "string", "required": False},
        ])
        self.assertEqual((specs[0].min_value, specs[0].max_value), (1.0, 5.0))
        self.assertIs(specs[0].measure, MeasureSemantics.AVERAGEABLE)

    def test_choices_survive_the_correction(self) -> None:
        specs = _sanitize([
            {"name": "kind", "label": "種別", "type": "choice",
             "choices": ["収入", "支出"], "required": False},
            {"name": "memo", "label": "メモ", "type": "string", "required": False},
        ])
        self.assertEqual(specs[0].choices, ("収入", "支出"))
        self.assertIs(specs[0].field_type, FieldType.CHOICE)

    def test_no_correction_happens_when_something_is_already_required(self) -> None:
        """既にrequiredがあれば触らない。"""
        specs = _sanitize([
            {"name": "amount", "label": "金額", "type": "number",
             "measure": "additive", "required": False},
            {"name": "memo", "label": "メモ", "type": "string", "required": True},
        ])
        self.assertFalse(specs[0].required)
        self.assertIs(specs[0].measure, MeasureSemantics.ADDITIVE)


class TestTheSpecIsSafeToExtend(unittest.TestCase):
    """**将来metadataを足しても同じ事故が起きない形**であること。"""

    def test_the_spec_is_an_immutable_dataclass(self) -> None:
        self.assertTrue(dataclasses.is_dataclass(FieldSpec))
        spec = FieldSpec("a", "A")
        with self.assertRaises(dataclasses.FrozenInstanceError):
            spec.required = False  # type: ignore[misc]

    def test_replace_changes_one_attribute_only(self) -> None:
        spec = FieldSpec(
            "amount", "金額", field_type=FieldType.NUMBER,
            measure=MeasureSemantics.ADDITIVE, required=False,
        )
        changed = dataclasses.replace(spec, required=True)
        self.assertTrue(changed.required)
        self.assertIs(changed.measure, MeasureSemantics.ADDITIVE)
        self.assertIs(changed.field_type, FieldType.NUMBER)

    def test_the_synthesizer_does_not_rebuild_specs_by_hand(self) -> None:
        """**手書きコピーが復活していないこと。**

        `FieldSpec(` を組み立て直す行がsanitize処理に現れたら、それは
        書き写し忘れの機会が戻ったということである。ソースを読んで
        確かめる——コメントでの申し合わせは破られるが、これは破られたら
        落ちる。
        """
        import inspect

        source = inspect.getsource(EntitySynthesizer._sanitize_fields)
        self.assertNotIn(
            "FieldSpec(", source,
            "required補正でFieldSpecを手で組み直している。"
            "dataclasses.replace を使うこと(§2)",
        )
        self.assertIn("replace(", source)


class TestTheHeroMetricSurvivesEndToEnd(unittest.TestCase):
    """**実害の側から確かめる。** measureが消えるとKPIが出なくなる。"""

    def test_a_synthesized_money_entity_still_gets_its_kpi(self) -> None:
        from forge_ai.core.ir.forge_language_compiler import ForgeLanguageCompiler
        from forge_ai.core.ir.ir_generator import EntitySpec, IRGenerator

        specs = _sanitize([
            {"name": "amount", "label": "金額", "type": "number",
             "measure": "additive", "required": False},
            {"name": "memo", "label": "メモ", "type": "string", "required": False},
        ])
        ir = IRGenerator().build_from_spec(EntitySpec("sale", "売上", specs))
        document = ForgeLanguageCompiler().compile(
            ir, domain_category="x", title="t"
        ).to_json_dict()

        def walk(widget: dict):
            yield widget
            for child in widget.get("children", []) or ():
                yield from walk(child)

        metrics = [w for s in document["screens"] for w in walk(s["body"])
                   if w["type"] == "metric_view"]
        self.assertTrue(metrics, "measureが失われてHero KPIが出ていない")
        self.assertEqual(metrics[0]["aggregate"], "sum")


if __name__ == "__main__":
    unittest.main()
