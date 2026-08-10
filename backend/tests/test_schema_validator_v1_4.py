"""Language v1.4拡張(Typed Record Runtime Phase1)のテスト
(FORGE v0.9開発指示)。

`record_schemas`(文書トップレベル、record_listとは独立した定義)と、
`record_list` Stateの任意プロパティ`schema_ref`を検証する。v1.0〜v1.3
との後方互換性はtest_schema_validator*.py の既存テスト(無改変のまま)
が引き続き担保する。

実行方法:
    cd backend
    python -m unittest tests.test_schema_validator_v1_4 -v
"""

from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.ai.validators.schema_validator import validate_forge_document  # noqa: E402


def _v14_doc(body: dict, *, state: dict | None = None, record_schemas: dict | None = None) -> dict:
    doc: dict = {
        "version": "1.4",
        "initial_screen_id": "s1",
        "screens": [{"id": "s1", "title": "S1", "state": state or {}, "body": body}],
    }
    if record_schemas is not None:
        doc["record_schemas"] = record_schemas
    return doc


def _fish_record_schema() -> dict:
    """指示書の`record_schema`例をそのまま使う。"""
    return {
        "fish_record": {
            "fields": [
                {"name": "species", "type": "string", "label": "魚種", "required": True},
                {"name": "size", "type": "number", "label": "サイズ(cm)", "required": False},
                {"name": "date", "type": "date", "label": "日付", "required": False},
                {"name": "memo", "type": "string", "label": "メモ", "required": False},
            ],
        },
    }


class TestRecordSchemasVersionGating(unittest.TestCase):
    """record_schemasがv1.4以降でのみ使用でき、v1.0〜v1.3では拒否される
    ことを確認する。"""

    def test_v1_3_document_cannot_use_record_schemas(self) -> None:
        doc = {
            "version": "1.3", "initial_screen_id": "s1",
            "screens": [{"id": "s1", "title": "S1", "state": {},
                         "body": {"type": "text", "id": "t1", "value": "x"}}],
            "record_schemas": _fish_record_schema(),
        }
        result = validate_forge_document(doc)
        self.assertFalse(result.valid)
        self.assertTrue(any(e.rule == "field_not_allowed_in_version" for e in result.errors))

    def test_v1_3_document_cannot_use_schema_ref_on_record_list(self) -> None:
        doc = {
            "version": "1.3", "initial_screen_id": "s1",
            "screens": [{
                "id": "s1", "title": "S1",
                "state": {"records": {"type": "record_list", "value": [], "schema_ref": "fish_record"}},
                "body": {"type": "record_list_view", "id": "rlv1", "state_ref": "records"},
            }],
        }
        result = validate_forge_document(doc)
        self.assertFalse(result.valid)
        self.assertTrue(any(e.rule == "field_not_allowed_in_version" for e in result.errors))

    def test_v1_4_document_with_only_v1_3_features_still_passes(self) -> None:
        """後方互換性の核心: v1.4文書でも、record_schemaを一切使わなければ
        引き続き合格しなければならない。"""
        doc = _v14_doc(
            {"type": "record_list_view", "id": "rlv1", "state_ref": "records"},
            state={"records": {"type": "record_list", "value": []}},
        )
        result = validate_forge_document(doc)
        self.assertTrue(result.valid, msg=result.to_dict())


class TestRecordSchemasStructure(unittest.TestCase):
    """record_schemas自体の構造検証(指示書の例・Supported Types)。"""

    def test_valid_record_schema_with_all_supported_types_passes(self) -> None:
        record_schemas = {
            "sample": {
                "fields": [
                    {"name": "a", "type": "string", "label": "A", "required": True},
                    {"name": "b", "type": "number", "label": "B", "required": False},
                    {"name": "c", "type": "boolean", "label": "C", "required": False},
                    {"name": "d", "type": "date", "label": "D", "required": False},
                    {"name": "e", "type": "choice", "label": "E", "required": False, "options": ["x", "y"]},
                ],
            },
        }
        doc = _v14_doc({"type": "text", "id": "t1", "value": "x"}, record_schemas=record_schemas)
        result = validate_forge_document(doc)
        self.assertTrue(result.valid, msg=result.to_dict())

    def test_fish_record_example_from_instructions_passes(self) -> None:
        doc = _v14_doc({"type": "text", "id": "t1", "value": "x"}, record_schemas=_fish_record_schema())
        result = validate_forge_document(doc)
        self.assertTrue(result.valid, msg=result.to_dict())

    def test_unsupported_type_is_rejected(self) -> None:
        record_schemas = {"sample": {"fields": [{"name": "a", "type": "array", "label": "A"}]}}
        doc = _v14_doc({"type": "text", "id": "t1", "value": "x"}, record_schemas=record_schemas)
        result = validate_forge_document(doc)
        self.assertFalse(result.valid)
        self.assertTrue(any(e.rule == "enum" for e in result.errors))

    def test_choice_type_requires_options(self) -> None:
        record_schemas = {"sample": {"fields": [{"name": "a", "type": "choice", "label": "A"}]}}
        doc = _v14_doc({"type": "text", "id": "t1", "value": "x"}, record_schemas=record_schemas)
        result = validate_forge_document(doc)
        self.assertFalse(result.valid)
        self.assertTrue(any(e.rule == "array_bounds" for e in result.errors))

    def test_choice_type_with_empty_options_is_rejected(self) -> None:
        record_schemas = {"sample": {"fields": [{"name": "a", "type": "choice", "label": "A", "options": []}]}}
        doc = _v14_doc({"type": "text", "id": "t1", "value": "x"}, record_schemas=record_schemas)
        result = validate_forge_document(doc)
        self.assertFalse(result.valid)

    def test_non_choice_type_cannot_have_options(self) -> None:
        record_schemas = {"sample": {"fields": [{"name": "a", "type": "string", "label": "A", "options": ["x"]}]}}
        doc = _v14_doc({"type": "text", "id": "t1", "value": "x"}, record_schemas=record_schemas)
        result = validate_forge_document(doc)
        self.assertFalse(result.valid)
        self.assertTrue(any(e.rule == "field_not_applicable" for e in result.errors))

    def test_field_missing_name_is_rejected(self) -> None:
        record_schemas = {"sample": {"fields": [{"type": "string", "label": "A"}]}}
        doc = _v14_doc({"type": "text", "id": "t1", "value": "x"}, record_schemas=record_schemas)
        result = validate_forge_document(doc)
        self.assertFalse(result.valid)

    def test_field_missing_label_is_rejected(self) -> None:
        record_schemas = {"sample": {"fields": [{"name": "a", "type": "string"}]}}
        doc = _v14_doc({"type": "text", "id": "t1", "value": "x"}, record_schemas=record_schemas)
        result = validate_forge_document(doc)
        self.assertFalse(result.valid)

    def test_required_defaults_are_not_enforced_but_type_is_checked(self) -> None:
        """requiredは省略可能(Compiler/呼び出し元は常に明示するが、
        Schema上は必須ではない)。ただし指定した場合はbool型である必要
        がある。"""
        record_schemas = {"sample": {"fields": [{"name": "a", "type": "string", "label": "A", "required": "yes"}]}}
        doc = _v14_doc({"type": "text", "id": "t1", "value": "x"}, record_schemas=record_schemas)
        result = validate_forge_document(doc)
        self.assertFalse(result.valid)

    def test_duplicate_field_names_within_one_schema_are_rejected(self) -> None:
        record_schemas = {
            "sample": {
                "fields": [
                    {"name": "a", "type": "string", "label": "A"},
                    {"name": "a", "type": "number", "label": "A again"},
                ],
            },
        }
        doc = _v14_doc({"type": "text", "id": "t1", "value": "x"}, record_schemas=record_schemas)
        result = validate_forge_document(doc)
        self.assertFalse(result.valid)
        self.assertTrue(any(e.rule == "duplicate_field_name" for e in result.errors))

    def test_invalid_schema_name_is_rejected(self) -> None:
        record_schemas = {"Fish Record!": {"fields": [{"name": "a", "type": "string", "label": "A"}]}}
        doc = _v14_doc({"type": "text", "id": "t1", "value": "x"}, record_schemas=record_schemas)
        result = validate_forge_document(doc)
        self.assertFalse(result.valid)

    def test_empty_fields_list_is_rejected(self) -> None:
        record_schemas = {"sample": {"fields": []}}
        doc = _v14_doc({"type": "text", "id": "t1", "value": "x"}, record_schemas=record_schemas)
        result = validate_forge_document(doc)
        self.assertFalse(result.valid)

    def test_record_schemas_independent_of_record_list_can_exist_alone(self) -> None:
        """指示書「Record Listとは独立した定義として保持します」の裏付け:
        record_listのstateを1つも持たない文書でも、record_schemas単体は
        合格する。"""
        doc = _v14_doc({"type": "text", "id": "t1", "value": "hello"}, record_schemas=_fish_record_schema())
        result = validate_forge_document(doc)
        self.assertTrue(result.valid, msg=result.to_dict())


class TestRecordListSchemaRef(unittest.TestCase):
    """`record_list` Stateの`schema_ref`プロパティ。"""

    def test_schema_ref_pointing_to_existing_schema_passes(self) -> None:
        doc = _v14_doc(
            {"type": "record_list_view", "id": "rlv1", "state_ref": "records"},
            state={"records": {"type": "record_list", "value": [], "schema_ref": "fish_record"}},
            record_schemas=_fish_record_schema(),
        )
        result = validate_forge_document(doc)
        self.assertTrue(result.valid, msg=result.to_dict())

    def test_schema_ref_is_optional(self) -> None:
        """schema_ref無しのrecord_list(既存Phase1/2の形)は引き続き合格する。"""
        doc = _v14_doc(
            {"type": "record_list_view", "id": "rlv1", "state_ref": "records"},
            state={"records": {"type": "record_list", "value": []}},
        )
        result = validate_forge_document(doc)
        self.assertTrue(result.valid, msg=result.to_dict())

    def test_schema_ref_pointing_to_nonexistent_schema_is_rejected(self) -> None:
        doc = _v14_doc(
            {"type": "record_list_view", "id": "rlv1", "state_ref": "records"},
            state={"records": {"type": "record_list", "value": [], "schema_ref": "does_not_exist"}},
            record_schemas=_fish_record_schema(),
        )
        result = validate_forge_document(doc)
        self.assertFalse(result.valid)
        self.assertTrue(any(e.rule == "schema_reference_exists" for e in result.errors))

    def test_schema_ref_with_invalid_identifier_format_is_rejected(self) -> None:
        doc = _v14_doc(
            {"type": "record_list_view", "id": "rlv1", "state_ref": "records"},
            state={"records": {"type": "record_list", "value": [], "schema_ref": "Not Valid!"}},
        )
        result = validate_forge_document(doc)
        self.assertFalse(result.valid)

    def test_schema_ref_is_not_allowed_on_other_state_types(self) -> None:
        """schema_refはrecord_list型専用(checklist等では使えない)。"""
        doc = _v14_doc(
            {"type": "checklist", "id": "c1", "state_ref": "items"},
            state={"items": {"type": "checklist", "value": [], "schema_ref": "fish_record"}},
            record_schemas=_fish_record_schema(),
        )
        result = validate_forge_document(doc)
        self.assertFalse(result.valid)


class TestRecordSchemasDoNotAffectWidgetGeneration(unittest.TestCase):
    """指示書のDesign Policy「UI改善ではありません。Runtime動作も変更
    しません」の裏付け: record_schemasを追加してもWidget/Action/既存
    State型のVersion許可リストは無変更(v1.3と同じ)。"""

    def test_v1_4_allows_exactly_the_same_widget_types_as_v1_3(self) -> None:
        from app.ai.validators.schema_validator import WIDGET_TYPES_BY_VERSION

        self.assertEqual(WIDGET_TYPES_BY_VERSION["1.4"], WIDGET_TYPES_BY_VERSION["1.3"])

    def test_v1_4_allows_exactly_the_same_action_types_as_v1_3(self) -> None:
        from app.ai.validators.schema_validator import ACTION_TYPES_BY_VERSION

        self.assertEqual(ACTION_TYPES_BY_VERSION["1.4"], ACTION_TYPES_BY_VERSION["1.3"])


if __name__ == "__main__":
    unittest.main()
