"""schema_validator.py のテスト。

pytest でも `python -m unittest` でも実行できるよう、標準ライブラリの
unittest.TestCase のみで書いている(pytestはこの形式をそのまま収集・実行できる)。
Claudeのサンドボックスにはpytestが無いため、Claude自身は
`python -m unittest` で実行して検証した(本レポート Test Report 参照)。

実行方法:
    cd backend
    python -m unittest tests.test_schema_validator -v
    # または CI と同じ形式:
    pytest tests/test_schema_validator.py -v
"""

from __future__ import annotations

import copy
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.ai.validators.schema_validator import (  # noqa: E402
    validate_forge_document,
    validate_forge_document_from_text,
)


def _valid_document() -> dict:
    """有効な最小構成(text_field + checklist + add button + back button)を持つ1画面。"""
    return {
        "version": "1.0",
        "app": {"title": "買い物メモ"},
        "initial_screen_id": "shopping_list",
        "screens": [
            {
                "id": "shopping_list",
                "title": "買い物メモ",
                "state": {
                    "new_item_text": {"type": "string", "value": ""},
                    "items": {
                        "type": "checklist",
                        "value": [
                            {"id": "item_1", "text": "卵", "done": False},
                            {"id": "item_2", "text": "牛乳", "done": False},
                        ],
                    },
                },
                "body": {
                    "type": "column",
                    "id": "root_column",
                    "children": [
                        {"type": "checklist", "id": "list_view", "state_ref": "items", "empty_state_text": "アイテムはまだないよ"},
                        {
                            "type": "row",
                            "id": "add_row",
                            "children": [
                                {"type": "text_field", "id": "add_field", "state_ref": "new_item_text", "placeholder": "アイテムを追加"},
                                {
                                    "type": "button",
                                    "id": "add_button",
                                    "label": "追加",
                                    "action": {"type": "add_item", "target_state_ref": "items", "source_state_ref": "new_item_text"},
                                },
                            ],
                        },
                    ],
                },
            }
        ],
    }


class TestValidJson(unittest.TestCase):
    def test_valid_minimal_screen_passes(self):
        result = validate_forge_document(_valid_document())
        self.assertTrue(result.valid, msg=result.to_dict())
        self.assertEqual(result.errors, [])

    def test_valid_document_via_text_entrypoint(self):
        text = json.dumps(_valid_document())
        result = validate_forge_document_from_text(text)
        self.assertTrue(result.valid)

    def test_multiple_widgets_and_navigation_between_two_screens(self):
        doc = _valid_document()
        doc["screens"].append({
            "id": "about",
            "title": "About",
            "body": {"type": "text", "id": "about_text", "value": "Forge"},
        })
        doc["screens"][0]["body"]["children"].append({
            "type": "button", "id": "go_about", "label": "About",
            "action": {"type": "navigate", "target_screen_id": "about"},
        })
        result = validate_forge_document(doc)
        self.assertTrue(result.valid, msg=result.to_dict())

    def test_state_reference_in_confirm_style_text(self):
        doc = _valid_document()
        doc["screens"][0]["body"]["children"].append(
            {"type": "text", "id": "echo", "value": "", "state_ref": "new_item_text"}
        )
        result = validate_forge_document(doc)
        self.assertTrue(result.valid, msg=result.to_dict())


class TestInvalidJsonSyntax(unittest.TestCase):
    def test_broken_json_is_syntax_error(self):
        result = validate_forge_document_from_text("{ not valid json ")
        self.assertFalse(result.valid)
        self.assertEqual(result.errors[0].category.value, "syntax")
        self.assertEqual(result.errors[0].rule, "valid_json")


class TestMissingVersion(unittest.TestCase):
    def test_missing_version_is_schema_error(self):
        doc = _valid_document()
        del doc["version"]
        result = validate_forge_document(doc)
        self.assertFalse(result.valid)
        self.assertTrue(any(e.rule == "version_const" for e in result.errors))


class TestUnknownWidget(unittest.TestCase):
    def test_unknown_widget_type_is_rejected(self):
        doc = _valid_document()
        doc["screens"][0]["body"]["children"].append({"type": "video_player", "id": "vp1"})
        result = validate_forge_document(doc)
        self.assertFalse(result.valid)
        self.assertTrue(any(e.rule == "unknown_widget" for e in result.errors))


class TestUnknownAction(unittest.TestCase):
    def test_unknown_action_type_is_rejected(self):
        doc = _valid_document()
        doc["screens"][0]["body"]["children"][1]["children"][1]["action"] = {"type": "delete_everything"}
        result = validate_forge_document(doc)
        self.assertFalse(result.valid)
        self.assertTrue(any(e.rule == "unknown_action" for e in result.errors))


class TestDuplicateIds(unittest.TestCase):
    def test_duplicate_screen_id(self):
        doc = _valid_document()
        dup = copy.deepcopy(doc["screens"][0])
        doc["screens"].append(dup)
        result = validate_forge_document(doc)
        self.assertFalse(result.valid)
        self.assertTrue(any(e.rule == "duplicate_screen_id" for e in result.errors))

    def test_duplicate_widget_id(self):
        doc = _valid_document()
        doc["screens"][0]["body"]["children"][0]["id"] = "add_row"  # add_rowと衝突させる
        result = validate_forge_document(doc)
        self.assertFalse(result.valid)
        self.assertTrue(any(e.rule == "duplicate_widget_id" for e in result.errors))


class TestNonexistentStateReference(unittest.TestCase):
    def test_state_ref_to_missing_key(self):
        doc = _valid_document()
        doc["screens"][0]["body"]["children"][1]["children"][0]["state_ref"] = "does_not_exist"
        result = validate_forge_document(doc)
        self.assertFalse(result.valid)
        self.assertTrue(any(e.rule == "state_reference_exists" for e in result.errors))

    def test_state_ref_type_mismatch(self):
        doc = _valid_document()
        # checklist widgetにstring型のstateを結びつける(型不一致)
        doc["screens"][0]["body"]["children"][0]["state_ref"] = "new_item_text"
        result = validate_forge_document(doc)
        self.assertFalse(result.valid)
        self.assertTrue(any(e.rule == "state_reference_type_mismatch" for e in result.errors))


class TestNonexistentNavigationTarget(unittest.TestCase):
    def test_navigate_to_missing_screen(self):
        doc = _valid_document()
        doc["screens"][0]["body"]["children"].append({
            "type": "button", "id": "broken_nav", "label": "どこかへ",
            "action": {"type": "navigate", "target_screen_id": "nowhere"},
        })
        result = validate_forge_document(doc)
        self.assertFalse(result.valid)
        self.assertTrue(any(e.rule == "navigation_target_exists" for e in result.errors))

    def test_initial_screen_id_must_exist(self):
        doc = _valid_document()
        doc["initial_screen_id"] = "does_not_exist"
        result = validate_forge_document(doc)
        self.assertFalse(result.valid)
        self.assertTrue(any(e.rule == "initial_screen_exists" for e in result.errors))


class TestExcessiveNesting(unittest.TestCase):
    def test_deep_nesting_beyond_limit_is_rejected(self):
        doc = _valid_document()
        # 深さ13のcolumnネストを作る(上限12を超える)
        leaf = {"type": "text", "id": "deep_leaf", "value": "x"}
        node = leaf
        for i in range(13):
            node = {"type": "column", "id": f"deep_{i}", "children": [node]}
        doc["screens"][0]["body"] = node
        result = validate_forge_document(doc)
        self.assertFalse(result.valid)
        self.assertTrue(any(e.rule == "max_nesting_depth" for e in result.errors))


class TestMissingRequiredField(unittest.TestCase):
    def test_button_without_action_is_rejected(self):
        doc = _valid_document()
        del doc["screens"][0]["body"]["children"][1]["children"][1]["action"]
        result = validate_forge_document(doc)
        self.assertFalse(result.valid)
        self.assertTrue(any(e.rule == "required" and "action" in e.path for e in result.errors))

    def test_screen_without_body_is_rejected(self):
        doc = _valid_document()
        del doc["screens"][0]["body"]
        result = validate_forge_document(doc)
        self.assertFalse(result.valid)
        self.assertTrue(any(e.rule == "required" for e in result.errors))


class TestExtraProperties(unittest.TestCase):
    def test_additional_property_on_widget_is_rejected(self):
        doc = _valid_document()
        doc["screens"][0]["body"]["children"][1]["children"][1]["onLongPress"] = "not_allowed"
        result = validate_forge_document(doc)
        self.assertFalse(result.valid)
        self.assertTrue(any(e.rule == "additional_properties" for e in result.errors))


class TestNoBackNavigationWarning(unittest.TestCase):
    def test_non_initial_screen_without_exit_gets_warning_not_error(self):
        doc = _valid_document()
        doc["screens"].append({
            "id": "dead_end",
            "title": "Dead End",
            "body": {"type": "text", "id": "de_text", "value": "hi"},
        })
        result = validate_forge_document(doc)
        # 行き止まりは警告(release_readyを止めない)であり、エラーではない
        self.assertTrue(result.valid, msg=result.to_dict())
        self.assertTrue(any(w.rule == "no_back_navigation" for w in result.warnings))


if __name__ == "__main__":
    unittest.main()
