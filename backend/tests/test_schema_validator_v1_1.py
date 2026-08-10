"""Language v1.1 拡張(6新規Widget)のテスト(FORGE-MILESTONE-002 PHASE1/3/9)。

version gating(v1.0文書がv1.1専用Widgetを使ったら不合格になること)と、
6つの新規Widget(heading/checkbox/card/list/divider/form)個別の
正常系・異常系を検証する。

実行方法:
    cd backend
    python -m unittest tests.test_schema_validator_v1_1 -v
"""

from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.ai.validators.schema_validator import validate_forge_document  # noqa: E402


def _v11_doc(body: dict, state: dict | None = None) -> dict:
    return {
        "version": "1.1",
        "initial_screen_id": "s1",
        "screens": [{"id": "s1", "title": "S1", "state": state or {}, "body": body}],
    }


class TestVersionGating(unittest.TestCase):
    def test_v1_0_document_cannot_use_heading(self):
        doc = {
            "version": "1.0",
            "initial_screen_id": "s1",
            "screens": [{"id": "s1", "title": "S1", "body": {"type": "heading", "id": "h1", "value": "見出し"}}],
        }
        result = validate_forge_document(doc)
        self.assertFalse(result.valid)
        self.assertTrue(any(e.rule == "widget_not_allowed_in_version" for e in result.errors))

    def test_v1_1_document_can_use_heading(self):
        doc = _v11_doc({"type": "heading", "id": "h1", "value": "見出し"})
        result = validate_forge_document(doc)
        self.assertTrue(result.valid, msg=result.to_dict())

    def test_v1_0_document_with_only_v1_0_widgets_still_passes(self):
        """後方互換性の核心: v1.0の6種だけを使う文書は、Validatorを
        書き換えた後も引き続き合格し続けなければならない。"""
        doc = {
            "version": "1.0",
            "initial_screen_id": "s1",
            "screens": [{"id": "s1", "title": "S1", "body": {"type": "text", "id": "t1", "value": "hello"}}],
        }
        result = validate_forge_document(doc)
        self.assertTrue(result.valid, msg=result.to_dict())

    def test_unsupported_version_string_rejected(self):
        doc = _v11_doc({"type": "text", "id": "t1", "value": "x"})
        doc["version"] = "2.0"
        result = validate_forge_document(doc)
        self.assertFalse(result.valid)
        self.assertTrue(any(e.rule == "version_const" for e in result.errors))


class TestHeadingWidget(unittest.TestCase):
    def test_valid_heading(self):
        doc = _v11_doc({"type": "heading", "id": "h1", "value": "セクション", "level": 2})
        self.assertTrue(validate_forge_document(doc).valid)

    def test_heading_missing_value(self):
        doc = _v11_doc({"type": "heading", "id": "h1"})
        self.assertFalse(validate_forge_document(doc).valid)

    def test_heading_invalid_level(self):
        doc = _v11_doc({"type": "heading", "id": "h1", "value": "x", "level": 3})
        result = validate_forge_document(doc)
        self.assertFalse(result.valid)
        self.assertTrue(any(e.rule == "enum" for e in result.errors))


class TestCheckboxWidget(unittest.TestCase):
    def test_valid_checkbox(self):
        doc = _v11_doc(
            {"type": "checkbox", "id": "c1", "label": "同意する", "state_ref": "agreed"},
            state={"agreed": {"type": "boolean", "value": False}},
        )
        self.assertTrue(validate_forge_document(doc).valid, msg=validate_forge_document(doc).to_dict())

    def test_checkbox_state_ref_type_mismatch(self):
        doc = _v11_doc(
            {"type": "checkbox", "id": "c1", "label": "同意する", "state_ref": "note"},
            state={"note": {"type": "string", "value": ""}},
        )
        result = validate_forge_document(doc)
        self.assertFalse(result.valid)
        self.assertTrue(any(e.rule == "state_reference_type_mismatch" for e in result.errors))

    def test_checkbox_missing_label(self):
        doc = _v11_doc(
            {"type": "checkbox", "id": "c1", "state_ref": "agreed"},
            state={"agreed": {"type": "boolean", "value": False}},
        )
        self.assertFalse(validate_forge_document(doc).valid)


class TestCardWidget(unittest.TestCase):
    def test_valid_card_with_children(self):
        doc = _v11_doc({
            "type": "card", "id": "card1",
            "children": [{"type": "text", "id": "t1", "value": "中身"}],
        })
        self.assertTrue(validate_forge_document(doc).valid)

    def test_card_with_empty_children_rejected(self):
        doc = _v11_doc({"type": "card", "id": "card1", "children": []})
        result = validate_forge_document(doc)
        self.assertFalse(result.valid)
        self.assertTrue(any(e.rule == "array_bounds" for e in result.errors))

    def test_card_can_nest_other_containers(self):
        doc = _v11_doc({
            "type": "card", "id": "card1",
            "children": [
                {"type": "heading", "id": "h1", "value": "タイトル"},
                {"type": "column", "id": "col1", "children": [
                    {"type": "text", "id": "t1", "value": "本文"},
                    {"type": "divider", "id": "d1"},
                ]},
            ],
        })
        self.assertTrue(validate_forge_document(doc).valid, msg=validate_forge_document(doc).to_dict())


class TestListWidget(unittest.TestCase):
    """TD7(string_list型を消費するWidgetが無い)の解消を検証する。"""

    def test_valid_list_bound_to_string_list_state(self):
        doc = _v11_doc(
            {"type": "list", "id": "l1", "state_ref": "tags"},
            state={"tags": {"type": "string_list", "value": ["緊急", "重要"]}},
        )
        self.assertTrue(validate_forge_document(doc).valid, msg=validate_forge_document(doc).to_dict())

    def test_list_state_ref_type_mismatch(self):
        doc = _v11_doc(
            {"type": "list", "id": "l1", "state_ref": "items"},
            state={"items": {"type": "checklist", "value": []}},
        )
        result = validate_forge_document(doc)
        self.assertFalse(result.valid)
        self.assertTrue(any(e.rule == "state_reference_type_mismatch" for e in result.errors))

    def test_list_state_ref_missing(self):
        doc = _v11_doc({"type": "list", "id": "l1", "state_ref": "does_not_exist"})
        result = validate_forge_document(doc)
        self.assertFalse(result.valid)
        self.assertTrue(any(e.rule == "state_reference_exists" for e in result.errors))


class TestDividerWidget(unittest.TestCase):
    def test_valid_divider(self):
        doc = _v11_doc({"type": "column", "id": "col1", "children": [
            {"type": "text", "id": "t1", "value": "上"},
            {"type": "divider", "id": "d1"},
            {"type": "text", "id": "t2", "value": "下"},
        ]})
        self.assertTrue(validate_forge_document(doc).valid)

    def test_divider_rejects_extra_properties(self):
        doc = _v11_doc({"type": "divider", "id": "d1", "color": "red"})
        result = validate_forge_document(doc)
        self.assertFalse(result.valid)
        self.assertTrue(any(e.rule == "additional_properties" for e in result.errors))


class TestFormWidget(unittest.TestCase):
    def test_valid_form_with_input_and_submit(self):
        doc = _v11_doc(
            {
                "type": "form", "id": "form1",
                "children": [
                    {"type": "text_field", "id": "name_field", "state_ref": "name"},
                    {"type": "checkbox", "id": "agree", "label": "同意する", "state_ref": "agreed"},
                ],
                "submit_label": "送信する",
                "submit_action": {"type": "navigate", "target_screen_id": "thanks"},
            },
        )
        doc["screens"][0]["state"] = {
            "name": {"type": "string", "value": ""},
            "agreed": {"type": "boolean", "value": False},
        }
        doc["screens"].append({"id": "thanks", "title": "Thanks", "body": {"type": "text", "id": "t1", "value": "ありがとう"}})
        result = validate_forge_document(doc)
        self.assertTrue(result.valid, msg=result.to_dict())

    def test_form_without_input_widgets_is_warning_not_error(self):
        doc = _v11_doc({
            "type": "form", "id": "form1",
            "children": [{"type": "text", "id": "t1", "value": "説明文だけ"}],
            "submit_label": "OK",
            "submit_action": {"type": "go_back"},
        })
        result = validate_forge_document(doc)
        self.assertTrue(result.valid, msg=result.to_dict())
        self.assertTrue(any(w.rule == "form_without_input" for w in result.warnings))

    def test_form_missing_submit_action(self):
        doc = _v11_doc({
            "type": "form", "id": "form1",
            "children": [{"type": "text_field", "id": "f1", "state_ref": "x"}],
            "submit_label": "OK",
        })
        doc["screens"][0]["state"] = {"x": {"type": "string", "value": ""}}
        result = validate_forge_document(doc)
        self.assertFalse(result.valid)
        self.assertTrue(any(e.rule == "required" for e in result.errors))

    def test_form_submit_action_navigate_target_must_exist(self):
        doc = _v11_doc({
            "type": "form", "id": "form1",
            "children": [{"type": "text_field", "id": "f1", "state_ref": "x"}],
            "submit_label": "OK",
            "submit_action": {"type": "navigate", "target_screen_id": "nowhere"},
        })
        doc["screens"][0]["state"] = {"x": {"type": "string", "value": ""}}
        result = validate_forge_document(doc)
        self.assertFalse(result.valid)
        self.assertTrue(any(e.rule == "navigation_target_exists" for e in result.errors))


class TestAllTwelveWidgetsTogether(unittest.TestCase):
    def test_document_using_all_twelve_widget_types_is_valid(self):
        doc = {
            "version": "1.1",
            "initial_screen_id": "s1",
            "screens": [{
                "id": "s1", "title": "全部入り",
                "state": {
                    "note": {"type": "string", "value": ""},
                    "items": {"type": "checklist", "value": [{"id": "i1", "text": "x", "done": False}]},
                    "tags": {"type": "string_list", "value": ["a"]},
                    "agreed": {"type": "boolean", "value": False},
                },
                "body": {
                    "type": "column", "id": "root",
                    "children": [
                        {"type": "heading", "id": "h1", "value": "タイトル", "level": 1},
                        {"type": "text", "id": "t1", "value": "本文"},
                        {"type": "divider", "id": "d1"},
                        {"type": "card", "id": "card1", "children": [
                            {"type": "list", "id": "l1", "state_ref": "tags"},
                        ]},
                        {"type": "checklist", "id": "cl1", "state_ref": "items"},
                        {"type": "checkbox", "id": "cb1", "label": "同意", "state_ref": "agreed"},
                        {"type": "row", "id": "r1", "children": [
                            {"type": "text_field", "id": "tf1", "state_ref": "note"},
                            {"type": "button", "id": "b1", "label": "OK", "action": {"type": "go_back"}},
                        ]},
                        {"type": "form", "id": "form1", "submit_label": "送信", "children": [
                            {"type": "text_field", "id": "tf2", "state_ref": "note"},
                        ], "submit_action": {"type": "go_back"}},
                    ],
                },
            }],
        }
        result = validate_forge_document(doc)
        self.assertTrue(result.valid, msg=result.to_dict())


if __name__ == "__main__":
    unittest.main()
