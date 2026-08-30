"""schema_validator.py の拡張テスト(FORGE-MERGE-002 Task 4)。

test_schema_validator.py の19件に対し、以下のカテゴリを体系的に追加する:
Unknown Widget / Unknown Property / Missing Property / Invalid Type / Enum Error /
Version Error / Duplicate ID / Deep Tree / Recursive Structure / Circular Reference /
Null / Array Error / Object Error / Action Error / Migration Error
に加えて、正常系・境界値のカバレッジも均等に追加する(指示書「正常系・異常系を
均等に作成する」に基づく)。

実行方法:
    cd backend
    python -m unittest tests.test_schema_validator_extended -v
"""

from __future__ import annotations

import copy
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.ai.validators.schema_validator import (  # noqa: E402
    MAX_CHECKLIST_ITEMS,
    MAX_NESTING_DEPTH,
    MAX_SCREENS,
    MAX_STRING_LIST_ITEMS,
    validate_forge_document,
)


def _minimal_doc() -> dict:
    """最小の有効文書(1画面・textのみ)。既存test_schema_validator.pyの
    _valid_document()より単純にし、各テストが変更する箇所を明確にする。"""
    return {
        "version": "1.0",
        "initial_screen_id": "s1",
        "screens": [
            {"id": "s1", "title": "Screen 1", "body": {"type": "text", "id": "t1", "value": "hello"}}
        ],
    }


def _deep_column(depth: int, leaf_id: str = "leaf") -> dict:
    """指定した深さのcolumnネストを作る。depth=1なら葉(text)そのもの。"""
    node = {"type": "text", "id": leaf_id, "value": "x"}
    for i in range(depth - 1):
        node = {"type": "column", "id": f"d{i}", "children": [node]}
    return node


# ---------------------------------------------------------------------------
# Unknown Widget
# ---------------------------------------------------------------------------

class TestUnknownWidget(unittest.TestCase):
    def test_unknown_widget_as_screen_root(self):
        doc = _minimal_doc()
        doc["screens"][0]["body"] = {"type": "video", "id": "v1"}
        result = validate_forge_document(doc)
        self.assertFalse(result.valid)
        self.assertTrue(any(e.rule == "unknown_widget" for e in result.errors))

    def test_unknown_widget_nested_in_column(self):
        doc = _minimal_doc()
        doc["screens"][0]["body"] = {
            "type": "column", "id": "c1",
            "children": [{"type": "future_map_widget", "id": "m1"}],
        }
        result = validate_forge_document(doc)
        self.assertFalse(result.valid)
        self.assertTrue(any(e.rule == "unknown_widget" for e in result.errors))

    def test_unknown_widget_type_is_empty_string(self):
        doc = _minimal_doc()
        doc["screens"][0]["body"] = {"type": "", "id": "e1"}
        result = validate_forge_document(doc)
        self.assertFalse(result.valid)
        self.assertTrue(any(e.rule == "unknown_widget" for e in result.errors))

    def test_unknown_widget_type_is_number(self):
        doc = _minimal_doc()
        doc["screens"][0]["body"] = {"type": 123, "id": "n1"}
        result = validate_forge_document(doc)
        self.assertFalse(result.valid)
        self.assertTrue(any(e.rule == "unknown_widget" for e in result.errors))


# ---------------------------------------------------------------------------
# Unknown Property (additionalProperties違反)
# ---------------------------------------------------------------------------

class TestUnknownProperty(unittest.TestCase):
    def test_unknown_property_on_screen(self):
        doc = _minimal_doc()
        doc["screens"][0]["subtitle"] = "not allowed"
        result = validate_forge_document(doc)
        self.assertFalse(result.valid)
        self.assertTrue(any(e.rule == "additional_properties" for e in result.errors))

    def test_unknown_property_on_root(self):
        doc = _minimal_doc()
        doc["author"] = "someone"
        result = validate_forge_document(doc)
        self.assertFalse(result.valid)
        self.assertTrue(any(e.rule == "additional_properties" for e in result.errors))

    def test_unknown_property_on_action(self):
        doc = _minimal_doc()
        doc["screens"][0]["body"] = {
            "type": "button", "id": "b1", "label": "OK",
            "action": {"type": "go_back", "confirm_first": True},
        }
        result = validate_forge_document(doc)
        self.assertFalse(result.valid)
        self.assertTrue(any(e.rule == "additional_properties" for e in result.errors))

    def test_unknown_property_on_state_value(self):
        doc = _minimal_doc()
        doc["screens"][0]["state"] = {"x": {"type": "string", "value": "a", "readonly": True}}
        result = validate_forge_document(doc)
        self.assertFalse(result.valid)
        self.assertTrue(any(e.rule == "additional_properties" for e in result.errors))

    def test_unknown_property_on_checklist_item(self):
        doc = _minimal_doc()
        doc["screens"][0]["state"] = {
            "items": {"type": "checklist", "value": [{"id": "i1", "text": "x", "done": False, "priority": 1}]}
        }
        result = validate_forge_document(doc)
        self.assertFalse(result.valid)
        self.assertTrue(any(e.rule == "additional_properties" for e in result.errors))

    def test_unknown_property_on_app(self):
        doc = _minimal_doc()
        doc["app"] = {"title": "My App", "icon": "rocket"}
        result = validate_forge_document(doc)
        self.assertFalse(result.valid)
        self.assertTrue(any(e.rule == "additional_properties" for e in result.errors))


# ---------------------------------------------------------------------------
# Missing Property(必須項目の体系的な網羅)
# ---------------------------------------------------------------------------

class TestMissingProperty(unittest.TestCase):
    def test_text_missing_value(self):
        doc = _minimal_doc()
        doc["screens"][0]["body"] = {"type": "text", "id": "t1"}
        result = validate_forge_document(doc)
        self.assertFalse(result.valid)

    def test_text_field_missing_state_ref(self):
        doc = _minimal_doc()
        doc["screens"][0]["body"] = {"type": "text_field", "id": "tf1"}
        result = validate_forge_document(doc)
        self.assertFalse(result.valid)
        self.assertTrue(any(e.rule == "required" for e in result.errors))

    def test_button_missing_label(self):
        doc = _minimal_doc()
        doc["screens"][0]["body"] = {"type": "button", "id": "b1", "action": {"type": "go_back"}}
        result = validate_forge_document(doc)
        self.assertFalse(result.valid)

    def test_column_missing_children(self):
        doc = _minimal_doc()
        doc["screens"][0]["body"] = {"type": "column", "id": "c1"}
        result = validate_forge_document(doc)
        self.assertFalse(result.valid)
        self.assertTrue(any(e.rule == "array_bounds" for e in result.errors))

    def test_checklist_missing_state_ref(self):
        doc = _minimal_doc()
        doc["screens"][0]["body"] = {"type": "checklist", "id": "cl1"}
        result = validate_forge_document(doc)
        self.assertFalse(result.valid)
        self.assertTrue(any(e.rule == "required" for e in result.errors))

    def test_screen_missing_id(self):
        doc = _minimal_doc()
        del doc["screens"][0]["id"]
        result = validate_forge_document(doc)
        self.assertFalse(result.valid)

    def test_screen_missing_title(self):
        doc = _minimal_doc()
        del doc["screens"][0]["title"]
        result = validate_forge_document(doc)
        self.assertFalse(result.valid)

    def test_root_missing_screens(self):
        doc = _minimal_doc()
        del doc["screens"]
        result = validate_forge_document(doc)
        self.assertFalse(result.valid)

    def test_root_missing_initial_screen_id(self):
        doc = _minimal_doc()
        del doc["initial_screen_id"]
        result = validate_forge_document(doc)
        self.assertFalse(result.valid)

    def test_navigate_missing_target_screen_id(self):
        doc = _minimal_doc()
        doc["screens"][0]["body"] = {
            "type": "button", "id": "b1", "label": "Go", "action": {"type": "navigate"},
        }
        result = validate_forge_document(doc)
        self.assertFalse(result.valid)

    def test_set_value_missing_value(self):
        doc = _minimal_doc()
        doc["screens"][0]["state"] = {"x": {"type": "string", "value": ""}}
        doc["screens"][0]["body"] = {
            "type": "button", "id": "b1", "label": "Set",
            "action": {"type": "set_value", "state_ref": "x"},
        }
        result = validate_forge_document(doc)
        self.assertFalse(result.valid)

    def test_add_item_missing_source_state_ref(self):
        doc = _minimal_doc()
        doc["screens"][0]["state"] = {"items": {"type": "checklist", "value": []}}
        doc["screens"][0]["body"] = {
            "type": "button", "id": "b1", "label": "Add",
            "action": {"type": "add_item", "target_state_ref": "items"},
        }
        result = validate_forge_document(doc)
        self.assertFalse(result.valid)

    def test_state_value_missing_type(self):
        doc = _minimal_doc()
        doc["screens"][0]["state"] = {"x": {"value": "a"}}
        result = validate_forge_document(doc)
        self.assertFalse(result.valid)

    def test_checklist_item_missing_done(self):
        doc = _minimal_doc()
        doc["screens"][0]["state"] = {
            "items": {"type": "checklist", "value": [{"id": "i1", "text": "x"}]}
        }
        result = validate_forge_document(doc)
        self.assertFalse(result.valid)


# ---------------------------------------------------------------------------
# Invalid Type
# ---------------------------------------------------------------------------

class TestInvalidType(unittest.TestCase):
    def test_text_value_is_number_not_string(self):
        doc = _minimal_doc()
        doc["screens"][0]["body"] = {"type": "text", "id": "t1", "value": 42}
        result = validate_forge_document(doc)
        self.assertFalse(result.valid)

    def test_checklist_item_done_is_string_not_boolean(self):
        doc = _minimal_doc()
        doc["screens"][0]["state"] = {
            "items": {"type": "checklist", "value": [{"id": "i1", "text": "x", "done": "false"}]}
        }
        result = validate_forge_document(doc)
        self.assertFalse(result.valid)

    def test_column_children_is_object_not_array(self):
        doc = _minimal_doc()
        doc["screens"][0]["body"] = {"type": "column", "id": "c1", "children": {"type": "text", "id": "t1", "value": "x"}}
        result = validate_forge_document(doc)
        self.assertFalse(result.valid)

    def test_screens_state_is_array_not_object(self):
        doc = _minimal_doc()
        doc["screens"][0]["state"] = [{"type": "string", "value": "a"}]
        result = validate_forge_document(doc)
        self.assertFalse(result.valid)

    def test_string_list_value_contains_non_string(self):
        doc = _minimal_doc()
        doc["screens"][0]["state"] = {"tags": {"type": "string_list", "value": ["a", 2, "c"]}}
        result = validate_forge_document(doc)
        self.assertFalse(result.valid)

    def test_boolean_state_value_is_string(self):
        doc = _minimal_doc()
        doc["screens"][0]["state"] = {"flag": {"type": "boolean", "value": "true"}}
        result = validate_forge_document(doc)
        self.assertFalse(result.valid)

    def test_button_label_is_array(self):
        doc = _minimal_doc()
        doc["screens"][0]["body"] = {
            "type": "button", "id": "b1", "label": ["not", "a", "string"],
            "action": {"type": "go_back"},
        }
        result = validate_forge_document(doc)
        self.assertFalse(result.valid)


# ---------------------------------------------------------------------------
# Enum Error
# ---------------------------------------------------------------------------

class TestEnumError(unittest.TestCase):
    def test_text_style_not_in_enum(self):
        doc = _minimal_doc()
        doc["screens"][0]["body"] = {"type": "text", "id": "t1", "value": "x", "style": "huge"}
        result = validate_forge_document(doc)
        self.assertFalse(result.valid)
        self.assertTrue(any(e.rule == "enum" for e in result.errors))

    def test_state_type_not_in_enum(self):
        doc = _minimal_doc()
        doc["screens"][0]["state"] = {"x": {"type": "float", "value": 1.5}}
        result = validate_forge_document(doc)
        self.assertFalse(result.valid)


# ---------------------------------------------------------------------------
# Version Error / Migration Error
# ---------------------------------------------------------------------------

class TestVersionAndMigrationError(unittest.TestCase):
    def test_version_is_future_string(self):
        doc = _minimal_doc()
        doc["version"] = "2.0"
        result = validate_forge_document(doc)
        self.assertFalse(result.valid)
        self.assertTrue(any(e.rule == "version_const" for e in result.errors))

    def test_version_is_number_not_string(self):
        doc = _minimal_doc()
        doc["version"] = 1.0
        result = validate_forge_document(doc)
        self.assertFalse(result.valid)

    def test_hypothetical_future_top_level_field_rejected_cleanly(self):
        """v2で追加されるかもしれない仮の項目(例: global_state)がv1文書に
        混入しても、クラッシュせず明確なSchemaエラーとして拒否されることを確認する
        (Migration/前方互換性のテスト。LANGUAGE_FREEZE.md参照)。"""
        doc = _minimal_doc()
        doc["global_state"] = {"theme": "dark"}
        result = validate_forge_document(doc)
        self.assertFalse(result.valid)
        self.assertTrue(any(e.rule == "additional_properties" for e in result.errors))

    def test_hypothetical_future_widget_type_rejected_cleanly(self):
        """将来追加されるかもしれないWidget type(例: video)が来ても、
        例外を投げずに構造化エラーとして扱えることを確認する。"""
        doc = _minimal_doc()
        doc["screens"][0]["body"] = {"type": "video", "id": "v1", "url": "https://example.com/x.mp4"}
        try:
            result = validate_forge_document(doc)
        except Exception as e:  # noqa: BLE001
            self.fail(f"未知typeの混入で例外が発生した(fail-closedになっていない): {e}")
        self.assertFalse(result.valid)


# ---------------------------------------------------------------------------
# Duplicate ID
# ---------------------------------------------------------------------------

class TestDuplicateId(unittest.TestCase):
    def test_duplicate_widget_id_across_different_screens(self):
        """Widget IDはドキュメント全体でグローバル一意(DECISIONS.md D11)。
        画面をまたいだ重複も検出できることを確認する。"""
        doc = _minimal_doc()
        doc["screens"].append({
            "id": "s2", "title": "Screen 2",
            "body": {"type": "text", "id": "t1", "value": "duplicate of screen1's t1"},
        })
        result = validate_forge_document(doc)
        self.assertFalse(result.valid)
        self.assertTrue(any(e.rule == "duplicate_widget_id" for e in result.errors))

    def test_duplicate_checklist_item_id(self):
        doc = _minimal_doc()
        doc["screens"][0]["state"] = {
            "items": {
                "type": "checklist",
                "value": [
                    {"id": "i1", "text": "a", "done": False},
                    {"id": "i1", "text": "b", "done": False},
                ],
            }
        }
        doc["screens"][0]["body"] = {"type": "checklist", "id": "cl1", "state_ref": "items"}
        # 現在のValidatorはchecklist item id の重複を専用ruleとして検査していない
        # (Schema層・Widget ID層のいずれの対象でもないため)。この既知のギャップを
        # 明示するテストとして残す(TECH_DEBT.md参照)。合格してしまうことを確認する。
        result = validate_forge_document(doc)
        self.assertTrue(result.valid, msg="既知のギャップ: checklist item id の重複は現状検出されない(TECH_DEBT.md参照)")


# ---------------------------------------------------------------------------
# Deep Tree / 境界値
# ---------------------------------------------------------------------------

class TestDeepTreeBoundary(unittest.TestCase):
    def test_exactly_at_max_depth_passes(self):
        doc = _minimal_doc()
        doc["screens"][0]["body"] = _deep_column(MAX_NESTING_DEPTH)
        result = validate_forge_document(doc)
        self.assertTrue(result.valid, msg=result.to_dict())

    def test_one_over_max_depth_fails(self):
        doc = _minimal_doc()
        doc["screens"][0]["body"] = _deep_column(MAX_NESTING_DEPTH + 1)
        result = validate_forge_document(doc)
        self.assertFalse(result.valid)
        self.assertTrue(any(e.rule == "max_nesting_depth" for e in result.errors))

    def test_very_deep_tree_fails_without_hanging(self):
        """50階層のネストでも(妥当な時間で)明確に拒否されることを確認する。
        stack overflow等でクラッシュしないことの確認でもある。"""
        doc = _minimal_doc()
        doc["screens"][0]["body"] = _deep_column(50)
        result = validate_forge_document(doc)
        self.assertFalse(result.valid)
        self.assertTrue(any(e.rule == "max_nesting_depth" for e in result.errors))


# ---------------------------------------------------------------------------
# Recursive Structure / Circular Reference
# ---------------------------------------------------------------------------

class TestCircularReference(unittest.TestCase):
    def test_navigate_cycle_between_two_screens_is_valid(self):
        """A→B→A のようなnavigateの循環は、UXとして正当(行き来する画面)であり
        エラーにしてはならない。真の構造的循環参照(Widgetツリー自体が閉路を持つ)は
        v1のJSON構造上そもそも起こり得ない(Widgetはツリー、Stateはキー参照のみで
        他Widgetを指さないため)。これはRuntime Safety層のコメントとしても
        明記済み。ここではnavigateループが正しく合格することだけを確認する。"""
        doc = {
            "version": "1.0",
            "initial_screen_id": "a",
            "screens": [
                {
                    "id": "a", "title": "A",
                    "body": {
                        "type": "button", "id": "to_b", "label": "B へ",
                        "action": {"type": "navigate", "target_screen_id": "b"},
                    },
                },
                {
                    "id": "b", "title": "B",
                    "body": {
                        "type": "button", "id": "to_a", "label": "A へ",
                        "action": {"type": "navigate", "target_screen_id": "a"},
                    },
                },
            ],
        }
        result = validate_forge_document(doc)
        self.assertTrue(result.valid, msg=result.to_dict())

    def test_self_navigate_is_valid(self):
        """自画面への遷移(リフレッシュ的な用途)も禁止しない。"""
        doc = _minimal_doc()
        doc["screens"][0]["body"] = {
            "type": "button", "id": "refresh", "label": "更新",
            "action": {"type": "navigate", "target_screen_id": "s1"},
        }
        result = validate_forge_document(doc)
        self.assertTrue(result.valid, msg=result.to_dict())


# ---------------------------------------------------------------------------
# Null
# ---------------------------------------------------------------------------

class TestNullValues(unittest.TestCase):
    def test_widget_id_is_null(self):
        doc = _minimal_doc()
        doc["screens"][0]["body"] = {"type": "text", "id": None, "value": "x"}
        result = validate_forge_document(doc)
        self.assertFalse(result.valid)

    def test_text_value_is_null(self):
        doc = _minimal_doc()
        doc["screens"][0]["body"] = {"type": "text", "id": "t1", "value": None}
        result = validate_forge_document(doc)
        self.assertFalse(result.valid)

    def test_action_is_null(self):
        doc = _minimal_doc()
        doc["screens"][0]["body"] = {"type": "button", "id": "b1", "label": "X", "action": None}
        result = validate_forge_document(doc)
        self.assertFalse(result.valid)

    def test_initial_screen_id_is_null(self):
        doc = _minimal_doc()
        doc["initial_screen_id"] = None
        result = validate_forge_document(doc)
        self.assertFalse(result.valid)

    def test_state_ref_is_null(self):
        doc = _minimal_doc()
        doc["screens"][0]["body"] = {"type": "checklist", "id": "cl1", "state_ref": None}
        result = validate_forge_document(doc)
        self.assertFalse(result.valid)

    def test_whole_document_is_null(self):
        result = validate_forge_document(None)
        self.assertFalse(result.valid)
        self.assertTrue(any(e.rule == "root_is_object" for e in result.errors))


# ---------------------------------------------------------------------------
# Array Error(配列長の境界値)
# ---------------------------------------------------------------------------

class TestArrayBounds(unittest.TestCase):
    def test_exactly_max_screens_passes(self):
        doc = _minimal_doc()
        doc["screens"] = [
            {"id": f"s{i}", "title": f"S{i}", "body": {"type": "text", "id": f"t{i}", "value": "x"}}
            for i in range(MAX_SCREENS)
        ]
        doc["initial_screen_id"] = "s0"
        result = validate_forge_document(doc)
        self.assertTrue(result.valid, msg=result.to_dict())

    def test_one_over_max_screens_fails(self):
        doc = _minimal_doc()
        doc["screens"] = [
            {"id": f"s{i}", "title": f"S{i}", "body": {"type": "text", "id": f"t{i}", "value": "x"}}
            for i in range(MAX_SCREENS + 1)
        ]
        doc["initial_screen_id"] = "s0"
        result = validate_forge_document(doc)
        self.assertFalse(result.valid)
        self.assertTrue(any(e.rule == "array_bounds" for e in result.errors))

    def test_column_over_60_children_fails(self):
        doc = _minimal_doc()
        doc["screens"][0]["body"] = {
            "type": "column", "id": "c1",
            "children": [{"type": "text", "id": f"t{i}", "value": "x"} for i in range(61)],
        }
        result = validate_forge_document(doc)
        self.assertFalse(result.valid)

    def test_row_over_20_children_fails(self):
        doc = _minimal_doc()
        doc["screens"][0]["body"] = {
            "type": "row", "id": "r1",
            "children": [{"type": "text", "id": f"t{i}", "value": "x"} for i in range(21)],
        }
        result = validate_forge_document(doc)
        self.assertFalse(result.valid)

    def test_checklist_state_over_max_items_fails(self):
        doc = _minimal_doc()
        doc["screens"][0]["state"] = {
            "items": {
                "type": "checklist",
                "value": [{"id": f"i{i}", "text": "x", "done": False} for i in range(MAX_CHECKLIST_ITEMS + 1)],
            }
        }
        result = validate_forge_document(doc)
        self.assertFalse(result.valid)

    def test_string_list_over_max_items_fails(self):
        doc = _minimal_doc()
        doc["screens"][0]["state"] = {
            "tags": {"type": "string_list", "value": [f"tag{i}" for i in range(MAX_STRING_LIST_ITEMS + 1)]}
        }
        result = validate_forge_document(doc)
        self.assertFalse(result.valid)


# ---------------------------------------------------------------------------
# Object Error(型の取り違え)
# ---------------------------------------------------------------------------

class TestObjectShapeErrors(unittest.TestCase):
    def test_screens_is_object_not_array(self):
        doc = _minimal_doc()
        doc["screens"] = {"id": "s1", "title": "S1", "body": {"type": "text", "id": "t1", "value": "x"}}
        result = validate_forge_document(doc)
        self.assertFalse(result.valid)

    def test_action_is_string_not_object(self):
        doc = _minimal_doc()
        doc["screens"][0]["body"] = {"type": "button", "id": "b1", "label": "X", "action": "navigate"}
        result = validate_forge_document(doc)
        self.assertFalse(result.valid)

    def test_document_is_a_bare_array(self):
        result = validate_forge_document([1, 2, 3])
        self.assertFalse(result.valid)

    def test_document_is_a_bare_string(self):
        result = validate_forge_document("just a string")
        self.assertFalse(result.valid)


# ---------------------------------------------------------------------------
# Action Error(4種類それぞれの追加バリエーション)
# ---------------------------------------------------------------------------

class TestActionErrorsSystematic(unittest.TestCase):
    def test_navigate_target_is_number(self):
        doc = _minimal_doc()
        doc["screens"][0]["body"] = {
            "type": "button", "id": "b1", "label": "X",
            "action": {"type": "navigate", "target_screen_id": 123},
        }
        result = validate_forge_document(doc)
        self.assertFalse(result.valid)

    def test_go_back_with_extra_field(self):
        doc = _minimal_doc()
        doc["screens"][0]["body"] = {
            "type": "button", "id": "b1", "label": "X",
            "action": {"type": "go_back", "animate": False},
        }
        result = validate_forge_document(doc)
        self.assertFalse(result.valid)

    def test_set_value_state_ref_is_number(self):
        doc = _minimal_doc()
        doc["screens"][0]["body"] = {
            "type": "button", "id": "b1", "label": "X",
            "action": {"type": "set_value", "state_ref": 1, "value": "x"},
        }
        result = validate_forge_document(doc)
        self.assertFalse(result.valid)

    def test_add_item_both_refs_missing(self):
        doc = _minimal_doc()
        doc["screens"][0]["body"] = {
            "type": "button", "id": "b1", "label": "X",
            "action": {"type": "add_item"},
        }
        result = validate_forge_document(doc)
        self.assertFalse(result.valid)


# ---------------------------------------------------------------------------
# 正常系・境界値の追加カバレッジ(異常系と均等に)
# ---------------------------------------------------------------------------

class TestPositiveCoverage(unittest.TestCase):
    def test_all_six_widget_types_in_one_document(self):
        doc = {
            "version": "1.0",
            "initial_screen_id": "s1",
            "screens": [{
                "id": "s1", "title": "All Widgets",
                "state": {
                    "note": {"type": "string", "value": ""},
                    "items": {"type": "checklist", "value": [{"id": "i1", "text": "x", "done": False}]},
                },
                "body": {
                    "type": "column", "id": "root",
                    "children": [
                        {"type": "text", "id": "t1", "value": "hello"},
                        {"type": "text_field", "id": "tf1", "state_ref": "note"},
                        {
                            "type": "row", "id": "r1",
                            "children": [
                                {"type": "button", "id": "b1", "label": "Go", "action": {"type": "go_back"}},
                            ],
                        },
                        {"type": "checklist", "id": "cl1", "state_ref": "items"},
                    ],
                },
            }],
        }
        result = validate_forge_document(doc)
        self.assertTrue(result.valid, msg=result.to_dict())

    def test_all_four_state_types_declared(self):
        doc = _minimal_doc()
        doc["screens"][0]["state"] = {
            "s": {"type": "string", "value": "a"},
            "b": {"type": "boolean", "value": True},
            "sl": {"type": "string_list", "value": ["a", "b"]},
            "cl": {"type": "checklist", "value": []},
        }
        result = validate_forge_document(doc)
        self.assertTrue(result.valid, msg=result.to_dict())

    def test_string_list_state_can_be_declared_but_no_widget_binds_to_it(self):
        """既知のギャップ(TECH_DEBT.md参照): v1にはstring_list型のstateを
        表示できるWidgetが無い。宣言自体は合格してしまう(未使用でもエラーにならない)。
        Widget追加は今回禁止のため、ギャップの存在を記録するテストとして残す。"""
        doc = _minimal_doc()
        doc["screens"][0]["state"] = {"tags": {"type": "string_list", "value": ["a", "b", "c"]}}
        result = validate_forge_document(doc)
        self.assertTrue(result.valid)

    def test_three_screen_navigation_web(self):
        doc = {
            "version": "1.0",
            "initial_screen_id": "home",
            "screens": [
                {"id": "home", "title": "Home", "body": {
                    "type": "button", "id": "go1", "label": "About",
                    "action": {"type": "navigate", "target_screen_id": "about"},
                }},
                {"id": "about", "title": "About", "body": {
                    "type": "button", "id": "go2", "label": "Back",
                    "action": {"type": "go_back"},
                }},
                {"id": "settings", "title": "Settings", "body": {
                    "type": "button", "id": "go3", "label": "Home",
                    "action": {"type": "navigate", "target_screen_id": "home"},
                }},
            ],
        }
        result = validate_forge_document(doc)
        self.assertTrue(result.valid, msg=result.to_dict())

    def test_empty_checklist_state_is_valid(self):
        doc = _minimal_doc()
        doc["screens"][0]["state"] = {"items": {"type": "checklist", "value": []}}
        doc["screens"][0]["body"] = {"type": "checklist", "id": "cl1", "state_ref": "items", "empty_state_text": "無いよ"}
        result = validate_forge_document(doc)
        self.assertTrue(result.valid, msg=result.to_dict())

    def test_exactly_max_checklist_items_passes(self):
        doc = _minimal_doc()
        doc["screens"][0]["state"] = {
            "items": {
                "type": "checklist",
                "value": [{"id": f"i{i}", "text": "x", "done": False} for i in range(MAX_CHECKLIST_ITEMS)],
            }
        }
        doc["screens"][0]["body"] = {"type": "checklist", "id": "cl1", "state_ref": "items"}
        result = validate_forge_document(doc)
        self.assertTrue(result.valid, msg=f"{len(result.errors)} errors")

    def test_deep_copy_of_valid_doc_is_still_valid(self):
        """変異(mutation)テストの対照実験: 何も変えなければ合格し続けることを確認する。"""
        doc = copy.deepcopy(_minimal_doc())
        result = validate_forge_document(doc)
        self.assertTrue(result.valid)


if __name__ == "__main__":
    unittest.main()
