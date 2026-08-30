"""必須項目は **Catalog が宣言する**。Planner が能力名で分岐しない（020E-3）。

---

## 何を直したか

以前 `capability_plan.py` はこう書いていた。

```python
if "view.map" in directly_requested:
    ... latitude / longitude を足す
```

これは**能力ごとの枝**である。能力を1つ獲得するたびに枝が増えるなら、
それは Template を1つ増やすのと同じであり、Self-Extension で獲得した
能力は永久にこの枝を書いてもらえない（＝自力では成立しない）。

宣言を `CapabilityDefinition.required_fields` へ移し、Planner は
**表を舐めるだけ**にした。

## これは geocoding の許可ではない

地図は**明示的な緯度・経度**を要求する、という宣言である。
場所の名前から座標を導いてよいという意味ではない。
自由入力の地名が座標へ化けていないことも、ここで固定する。
"""

from __future__ import annotations

import pathlib
import unittest

from forge_ai.core.semantics.capabilities import SEMANTIC_CAPABILITIES
from forge_ai.core.semantics.capability_plan import plan_capabilities

_PLANNER = (
    pathlib.Path(__file__).resolve().parents[1]
    / "core" / "semantics" / "capability_plan.py"
)

MAP_NEED = "観測地点の名前と緯度・経度を記録して、地図で見られるアプリを作りたい"
#: **座標を1語も言っていない**地図要求。
#:
#: 上の MAP_NEED は「緯度・経度」と明言しているので、宣言を消しても
#: 役の抽出だけで座標欄が立つ——**宣言を検査したことにならない**
#: （実際に配線破壊試験で通ってしまい、この need を足した）。
MAP_NEED_WITHOUT_COORDINATE_WORDS = "釣った場所を地図に残して魚の種類を記録したい"
PLACE_NAME_NEED = "札幌駅の混み具合を記録したい"


class TestPrerequisitesComeFromTheCatalog(unittest.TestCase):
    def test_the_map_capability_declares_its_required_fields(self) -> None:
        definition = SEMANTIC_CAPABILITIES["view.map"]
        self.assertEqual(definition.required_fields, ("latitude", "longitude"))

    def test_the_planner_applies_the_declaration(self) -> None:
        """**要求文が座標を言っていなくても**、宣言だけで欄が立つこと。"""
        plan = plan_capabilities(MAP_NEED_WITHOUT_COORDINATE_WORDS)
        names = [field.name for field in plan.fields]
        self.assertIn("latitude", names)
        self.assertIn("longitude", names)

    def test_an_explicit_request_still_works(self) -> None:
        plan = plan_capabilities(MAP_NEED)
        names = [field.name for field in plan.fields]
        self.assertIn("latitude", names)
        self.assertIn("longitude", names)

    def test_the_coordinates_are_numeric(self) -> None:
        """**明示的な数値座標**であること。文字列の場所名で代用しない。"""
        plan = plan_capabilities(MAP_NEED_WITHOUT_COORDINATE_WORDS)
        for name in ("latitude", "longitude"):
            field = next(f for f in plan.fields if f.name == name)
            with self.subTest(field=name):
                self.assertEqual(field.kind, "number")
                self.assertEqual(field.capability, "data.number")


class TestThePlannerHasNoCapabilitySpecificBranch(unittest.TestCase):
    def test_the_planner_does_not_name_a_capability_to_add_fields(self) -> None:
        source = _PLANNER.read_text(encoding="utf-8")
        body = source.split('"""')
        executable = "".join(body[i] for i in range(0, len(body), 2))
        # コメント行も除く（禁止例として説明に書いてあるため）。
        code = "\n".join(
            line for line in executable.split("\n")
            if not line.lstrip().startswith("#")
        )
        self.assertNotIn(
            'if "view.map"', code,
            "能力名で分岐して必須項目を足している（Template を増やすのと同じ）",
        )

    def test_a_declaration_is_enough_to_take_effect(self) -> None:
        """**宣言した能力は、枝を書かなくても効く。**

        獲得した能力が自力で成立するために、これが要る。
        """
        declaring = [
            capability_id for capability_id, definition in SEMANTIC_CAPABILITIES.items()
            if definition.required_fields
        ]
        self.assertTrue(declaring, "必須項目を宣言している能力が1つも無い")
        for capability_id in declaring:
            with self.subTest(capability=capability_id):
                for value in SEMANTIC_CAPABILITIES[capability_id].required_fields:
                    self.assertTrue(value.strip())


class TestPlaceNamesAreNeverTurnedIntoCoordinates(unittest.TestCase):
    """**geocoding は別の能力である。**"""

    def test_a_place_name_alone_does_not_produce_coordinates(self) -> None:
        plan = plan_capabilities(PLACE_NAME_NEED)
        names = [field.name for field in plan.fields]
        self.assertNotIn("latitude", names)
        self.assertNotIn("longitude", names)

    def test_acquiring_map_does_not_imply_geocoding(self) -> None:
        """地図を宣言しても、地名→座標の能力が生えないこと。"""
        self.assertNotIn("effect.geocoding", SEMANTIC_CAPABILITIES)
        definition = SEMANTIC_CAPABILITIES["view.map"]
        self.assertNotIn("geocod", definition.intent.lower())


if __name__ == "__main__":
    unittest.main()
