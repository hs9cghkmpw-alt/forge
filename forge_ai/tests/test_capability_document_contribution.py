"""**獲得した能力が、生成物へ届けるようになったこと**（020E-5）。

---

## 何を直したか

`forge_language_compiler.py` はこう書いていた。

```python
if "view.map" in promoted_capabilities:
    document = self._attach_map_view(document, entity)
```

**枝は人が書き足すもの**なので、Self-Extension で獲得した能力には
一生書かれない。つまり能力を獲得しても**生成物には現れない**——
獲得の目的そのものが果たせない。

宣言表へ移した。表であることが本質で、**獲得した能力は自分で登録できる。**

## 出力は1バイトも変えていない

`view.map` の JSON は属性の順序まで以前と同じである。ここが変わると
Dart 側（Validator / Parser / Widget Registry）の契約が壊れる。
既存の v1.16 テスト群と、下の順序テストがそれを押さえる。
"""

from __future__ import annotations

import pathlib
import unittest

from forge_ai.core.ir.capability_document_contribution import (
    CapabilityDocumentContribution,
    ContributionRequirementError,
    FieldNameRef,
    apply_capability_contributions,
    document_contribution_for,
    register_document_contribution,
)
from forge_ai.core.ir.ir_types import Entity, Field, FieldType
# 出荷済み宣言はこのモジュールが登録する。**import 順に頼らず明示する。**
from forge_ai.core.ir.shipped_contributions import register_shipped_contributions

register_shipped_contributions()

_COMPILER = (
    pathlib.Path(__file__).resolve().parents[1]
    / "core" / "ir" / "forge_language_compiler.py"
)


def _entity(*, numeric: bool = True) -> Entity:
    kind = FieldType.NUMBER if numeric else FieldType.STRING
    return Entity(
        name="record",
        label="記録",
        fields=(
            Field(name="place", label="場所", type=FieldType.STRING),
            Field(name="latitude", label="緯度", type=kind),
            Field(name="longitude", label="経度", type=kind),
        ),
    )


class TestTheShippedMapDeclarationMatchesTheOldOutput(unittest.TestCase):
    def test_the_map_contribution_is_registered(self) -> None:
        contribution = document_contribution_for("view.map")
        self.assertIsNotNone(contribution)
        assert contribution is not None
        self.assertEqual(contribution.widget_type, "map_view")
        self.assertEqual(contribution.widget_id, "record_map")

    def test_the_property_order_is_preserved(self) -> None:
        """**属性の順序まで**以前と同じであること。

        Dart 側の契約に触れないための下限である。
        """
        contribution = document_contribution_for("view.map")
        assert contribution is not None
        widget = contribution.build_widget(_entity())
        self.assertEqual(
            list(widget.properties),
            [
                "state_ref", "latitude_field", "longitude_field", "title",
                "empty_text", "initial_zoom", "height", "label_field",
            ],
        )
        self.assertEqual(widget.properties["latitude_field"], "latitude")
        self.assertEqual(widget.properties["longitude_field"], "longitude")
        self.assertEqual(widget.properties["label_field"], "place")
        self.assertEqual(widget.properties["initial_zoom"], 11)
        self.assertEqual(widget.properties["height"], 320)


class TestExplicitCoordinatesAreStillRequired(unittest.TestCase):
    """**地名から座標を捏造しない。** geocoding は別の能力である。"""

    def test_missing_coordinate_fields_are_refused(self) -> None:
        contribution = document_contribution_for("view.map")
        assert contribution is not None
        entity = Entity(
            name="record", label="記録",
            fields=(Field(name="place", label="場所", type=FieldType.STRING),),
        )
        with self.assertRaises(ContributionRequirementError) as caught:
            contribution.build_widget(entity)
        self.assertIn("latitude", str(caught.exception))

    def test_text_coordinates_are_refused(self) -> None:
        contribution = document_contribution_for("view.map")
        assert contribution is not None
        with self.assertRaises(ContributionRequirementError):
            contribution.build_widget(_entity(numeric=False))


class TestAnAcquiredCapabilityCanRegisterItsOwn(unittest.TestCase):
    """**これが本題。** 獲得した能力が自分の出力を宣言できること。"""

    def setUp(self) -> None:
        from forge_ai.core.ir import capability_document_contribution as module

        self._module = module
        self._saved = dict(module._CONTRIBUTIONS)
        self.addCleanup(
            lambda: (
                module._CONTRIBUTIONS.clear(),
                module._CONTRIBUTIONS.update(self._saved),
            ),
        )

    def test_a_newly_declared_capability_reaches_the_document(self) -> None:
        acquired = CapabilityDocumentContribution(
            capability_id="view.acquired_demo",
            widget_type="acquired_demo_view",
            widget_id="acquired_demo",
            document_version="1.16",
            required_numeric_fields=("latitude",),
            properties=(
                ("state_ref", "records"),
                ("value_field", FieldNameRef("latitude")),
            ),
        )
        register_document_contribution(acquired)

        from forge_ai.core.compiler import ForgeIRDocument, ForgeIRScreen, ForgeIRWidget

        document = ForgeIRDocument(
            version="1.16",
            initial_screen_id="s1",
            screens=(ForgeIRScreen(
                id="s1", title="t", state={},
                body=ForgeIRWidget(type="column", id="root"),
            ),),
            app_title="t",
        )
        result = apply_capability_contributions(
            document, ("view.acquired_demo",), _entity(),
        )
        emitted = result.screens[0].body.children
        self.assertEqual(len(emitted), 1)
        self.assertEqual(emitted[0].type, "acquired_demo_view")
        self.assertEqual(emitted[0].properties["value_field"], "latitude")

    def test_a_capability_without_a_declaration_emits_nothing(self) -> None:
        """宣言していない能力は**黙って何かを出したりしない**。"""
        from forge_ai.core.compiler import ForgeIRDocument, ForgeIRScreen, ForgeIRWidget

        document = ForgeIRDocument(
            version="1.16", initial_screen_id="s1",
            screens=(ForgeIRScreen(
                id="s1", title="t", state={},
                body=ForgeIRWidget(type="column", id="root"),
            ),),
            app_title="t",
        )
        result = apply_capability_contributions(document, ("view.no_such",), _entity())
        self.assertEqual(result.screens[0].body.children, ())

    def test_a_conflicting_redeclaration_is_refused(self) -> None:
        """**静かなすり替えを許さない。**"""
        first = CapabilityDocumentContribution(
            capability_id="view.conflict_demo", widget_type="a", widget_id="x",
            document_version="1.16",
        )
        register_document_contribution(first)
        register_document_contribution(first)  # 同じ宣言なら無害
        with self.assertRaises(ContributionRequirementError):
            register_document_contribution(
                CapabilityDocumentContribution(
                    capability_id="view.conflict_demo", widget_type="b", widget_id="x",
                    document_version="1.16",
                ),
            )


class TestTheCompilerNoLongerBranchesOnACapability(unittest.TestCase):
    def test_the_compiler_has_no_capability_id_branch(self) -> None:
        source = _COMPILER.read_text(encoding="utf-8")
        code = "\n".join(
            line for line in source.split("\n")
            if not line.lstrip().startswith("#")
        )
        body = code.split('"""')
        executable = "".join(body[i] for i in range(0, len(body), 2))
        self.assertNotIn(
            'if "view.map"', executable,
            "Compiler が能力名で分岐して widget を出している"
            "（獲得した能力には枝が書かれないので、生成物に現れない）",
        )

    def test_the_shipped_declaration_is_actually_registered_by_the_compiler(self) -> None:
        """**忘れれば落ちる形**であること。

        登録を呼ばなければ地図が出なくなる。
        """
        import forge_ai.core.ir.forge_language_compiler as compiler  # noqa: F401

        self.assertIsNotNone(document_contribution_for("view.map"))


if __name__ == "__main__":
    unittest.main()


class TestTheCompilerActuallyEmitsThroughTheDeclaration(unittest.TestCase):
    """**この経路にテストが1つも無かった。**

    宣言の登録を外しても backend 1984 件・forge_ai 全件が素通りした
    ——つまり `view.map` の**出力経路そのもの**が無検査だった
    （`_attach_map_view` の時代から）。実際に compile して確かめる。
    """

    def _ir(self):  # noqa: ANN202
        """**本番と同じ道で IR を作る。** 手組みの IR で通しても意味がない。"""
        from forge_ai.core.ir.capability_ir import entity_spec_from_plan
        from forge_ai.core.ir.ir_generator import IRGenerator
        from forge_ai.core.semantics.capability_plan import plan_capabilities

        plan = plan_capabilities("釣った場所を地図に残して魚の種類を記録したい")
        spec = entity_spec_from_plan(plan)
        assert spec is not None, plan
        return IRGenerator().build_from_spec(spec)

    def _compile(self, promoted: tuple[str, ...]):  # noqa: ANN202
        from forge_ai.core.ir.forge_language_compiler import ForgeLanguageCompiler

        return ForgeLanguageCompiler().compile(
            self._ir(), domain_category="generic", title="観測地点",
            promoted_capabilities=promoted,
        )

    @staticmethod
    def _widgets(document):  # noqa: ANN001, ANN205
        found = []

        def walk(node) -> None:  # noqa: ANN001
            found.append(node)
            for child in node.children:
                walk(child)

        for screen in document.screens:
            walk(screen.body)
        return found

    def test_a_promoted_capability_emits_its_widget(self) -> None:
        document = self._compile(("view.map",))
        types = [w.type for w in self._widgets(document)]
        self.assertIn("map_view", types, "PROMOTED なのに widget が出ていない")

    def test_the_emitted_widget_carries_the_declared_properties(self) -> None:
        document = self._compile(("view.map",))
        widget = next(w for w in self._widgets(document) if w.type == "map_view")
        self.assertEqual(widget.id, "record_map")
        self.assertEqual(widget.properties["latitude_field"], "latitude")
        self.assertEqual(widget.properties["longitude_field"], "longitude")
        self.assertEqual(widget.properties["state_ref"], "records")

    def test_without_promotion_no_widget_is_emitted(self) -> None:
        """**requested と PROMOTED を混同しない。** 昇格していなければ出ない。"""
        document = self._compile(())
        types = [w.type for w in self._widgets(document)]
        self.assertNotIn("map_view", types)

    def test_the_document_version_follows_the_declaration(self) -> None:
        self.assertEqual(self._compile(("view.map",)).version, "1.16")
