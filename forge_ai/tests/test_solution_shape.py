"""solution_shape.py のテスト(2026-08-12、CEO「常にニーズに合わせた
最適解を出せるようにして」対応)。

**このテストが守っているもの**: 以前は、ニーズが何であれ出力される形が
1種類(3タブCRUD)しか無かった。「買うものを並べて消したいだけ」の人にも
「釣果を細かく記録したい」人にも、同じ重さの道具を渡していた。

同時に、**軽くしすぎて情報を捨てないこと**も守る必要がある。
形を軽くすることと、ユーザーが記録したかった情報を失うことは別である。
"""

from __future__ import annotations

import importlib.util
import os
import sys
import unittest

from forge_ai.core.ir.forge_language_compiler import ForgeLanguageCompiler
from forge_ai.core.ir.ir_generator import EntitySpec, FieldSpec, IRGenerator, _ENTITY_DEFINITIONS
from forge_ai.core.ir.ir_types import Entity, Field, FieldType
from forge_ai.core.ir.solution_shape import SolutionShape, select_solution_shape


def _entity(*fields: Field) -> Entity:
    return Entity(name="thing", label="もの", fields=fields)


def _f(name: str, field_type: FieldType) -> Field:
    return Field(name=name, label=name, type=field_type)


class TestChecklistShapeSelection(unittest.TestCase):
    """「並べて、消す」だけで足りるケース。"""

    def test_a_single_string_field_becomes_a_checklist(self) -> None:
        """「買うものを忘れる」→ 品名だけ → 3タブCRUDは過剰。"""
        self.assertEqual(
            select_solution_shape(_entity(_f("item_name", FieldType.STRING))),
            SolutionShape.CHECKLIST,
        )

    def test_a_string_plus_boolean_becomes_a_checklist(self) -> None:
        """checklistの1項目は`{id, text, done}`であり、
        「やること」+「済んだか」をちょうど表現できる。"""
        self.assertEqual(
            select_solution_shape(_entity(
                _f("task", FieldType.STRING), _f("done", FieldType.BOOLEAN),
            )),
            SolutionShape.CHECKLIST,
        )

    def test_field_order_does_not_matter(self) -> None:
        self.assertEqual(
            select_solution_shape(_entity(
                _f("done", FieldType.BOOLEAN), _f("task", FieldType.STRING),
            )),
            SolutionShape.CHECKLIST,
        )


class TestRecordCrudShapeSelection(unittest.TestCase):
    """情報を落とさずに保持する必要があるケース。"""

    def test_a_single_number_field_is_not_a_checklist(self) -> None:
        """「回数を数えたい」はカウンタが最適だが、Forge Languageに
        increment相当のActionが無いため作れない(`solution_shape.py`
        のdocstring参照)。checklistへ倒すと数値が失われるため、
        情報を保持できるRECORD_CRUDにする。"""
        self.assertEqual(
            select_solution_shape(_entity(_f("count", FieldType.NUMBER))),
            SolutionShape.RECORD_CRUD,
        )

    def test_a_string_plus_date_stays_record_crud(self) -> None:
        """日付をchecklistへ押し込むと、記録したかった日付が消える。"""
        self.assertEqual(
            select_solution_shape(_entity(
                _f("title", FieldType.STRING), _f("date", FieldType.DATE),
            )),
            SolutionShape.RECORD_CRUD,
        )

    def test_two_strings_stay_record_crud(self) -> None:
        """文字列2つはchecklistの1行に収まらない(片方が消える)。"""
        self.assertEqual(
            select_solution_shape(_entity(
                _f("title", FieldType.STRING), _f("memo", FieldType.STRING),
            )),
            SolutionShape.RECORD_CRUD,
        )

    def test_three_or_more_fields_stay_record_crud(self) -> None:
        self.assertEqual(
            select_solution_shape(_entity(
                _f("a", FieldType.STRING), _f("b", FieldType.BOOLEAN), _f("c", FieldType.DATE),
            )),
            SolutionShape.RECORD_CRUD,
        )

    def test_an_entity_without_fields_falls_back_to_record_crud(self) -> None:
        self.assertEqual(select_solution_shape(_entity()), SolutionShape.RECORD_CRUD)


class TestCuratedDomainsAreUnaffected(unittest.TestCase):
    """既存のCurated Domain(手作りの7定義)は、いずれも4〜5 Fieldを
    持つため、この変更で形が変わってはならない(Golden Testと
    既存の生成結果を守る回帰テスト)。"""

    def test_every_curated_domain_still_uses_record_crud(self) -> None:
        for name, spec in _ENTITY_DEFINITIONS.items():
            with self.subTest(domain=name):
                ir = IRGenerator().build_from_spec(spec)
                self.assertEqual(
                    select_solution_shape(ir.entities[0]), SolutionShape.RECORD_CRUD,
                    f"{name}の形が変わってしまっている",
                )


def _widget_types(node: dict, acc: set[str]) -> set[str]:
    acc.add(node["type"])
    for child in node.get("children", []):
        _widget_types(child, acc)
    return acc


class TestChecklistCompilesToARealApp(unittest.TestCase):
    def _compile_checklist(self) -> dict:
        spec = EntitySpec(
            name="shopping_item", label="買うもの",
            field_specs=(FieldSpec("name", "品名", field_type=FieldType.STRING),),
            visual_style="warm",
        )
        ir = IRGenerator().build_from_spec(spec)
        return ForgeLanguageCompiler().compile(
            ir, domain_category="shopping", title="買い物メモ"
        ).to_json_dict()

    def test_checklist_output_has_no_tabs_and_no_form(self) -> None:
        """軽いニーズに、タブ・フォーム・編集画面を出さない。"""
        doc = self._compile_checklist()
        found = _widget_types(doc["screens"][0]["body"], set())
        self.assertNotIn("tab_view", found)
        self.assertNotIn("form", found)
        self.assertNotIn("record_list_view", found)
        self.assertIn("checklist", found)

    def test_checklist_output_can_still_add_items(self) -> None:
        """「並べて、消す」ために最低限必要な入力手段は残す。"""
        doc = self._compile_checklist()
        found = _widget_types(doc["screens"][0]["body"], set())
        self.assertIn("text_field", found)
        self.assertIn("button", found)
        state = doc["screens"][0]["state"]
        self.assertEqual(state["items"]["type"], "checklist")
        self.assertEqual(state["new_item_text"]["type"], "string")

    def test_checklist_output_still_gets_design_tokens(self) -> None:
        doc = self._compile_checklist()
        self.assertIn("design_tokens", doc)
        self.assertIn("primary", doc["design_tokens"]["color_scheme"])

    def test_checklist_output_omits_record_schemas(self) -> None:
        """record_listを使わないため、record_schemasは出さない
        (使わない定義を文書へ残さない)。"""
        self.assertNotIn("record_schemas", self._compile_checklist())

    def test_record_crud_still_produces_tabs(self) -> None:
        """対照実験: 属性の多いEntityは従来どおりタブCRUDになる。"""
        ir = IRGenerator().generate(None, domain_category="fishing_log")
        doc = ForgeLanguageCompiler().compile(
            ir, domain_category="fishing_log", title="釣果記録"
        ).to_json_dict()
        found = _widget_types(doc["screens"][0]["body"], set())
        self.assertIn("tab_view", found)
        self.assertIn("record_list_view", found)

    @unittest.skipUnless(
        importlib.util.find_spec("app") is not None or os.path.isdir(
            os.path.join(os.path.dirname(__file__), "..", "..", "backend", "app")
        ),
        "backend/app が無い環境では外部検証をスキップする",
    )
    def test_checklist_output_passes_the_real_backend_validator(self) -> None:
        backend_path = os.path.join(os.path.dirname(__file__), "..", "..", "backend")
        if backend_path not in sys.path:
            sys.path.insert(0, backend_path)
        try:
            from app.ai.validators.schema_validator import validate_forge_document
        except ImportError:
            self.skipTest("backend/appをimportできない環境")
            return
        result = validate_forge_document(self._compile_checklist())
        self.assertTrue(result.valid, msg=result.to_dict())


if __name__ == "__main__":
    unittest.main()
