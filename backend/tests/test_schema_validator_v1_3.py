"""Language v1.3拡張(Record Runtime Phase1)のテスト
(FORGE v0.7開発指示)。

`record_list` State型、`add_record` Action、`record_list_view` Widget
(layout="card"のみ)を検証する。v1.0〜v1.2との後方互換性は
test_schema_validator*.py の既存テスト(無改変のまま)が引き続き担保する。

実行方法:
    cd backend
    python -m unittest tests.test_schema_validator_v1_3 -v
"""

from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.ai.validators.schema_validator import validate_forge_document  # noqa: E402


def _v13_doc(body: dict, state: dict | None = None) -> dict:
    return {
        "version": "1.3",
        "initial_screen_id": "s1",
        "screens": [{"id": "s1", "title": "S1", "state": state or {}, "body": body}],
    }


def _record_form_and_list_body(*, layout: str | None = "card") -> dict:
    record_list_view: dict = {"type": "record_list_view", "id": "rlv1", "state_ref": "records"}
    if layout is not None:
        record_list_view["layout"] = layout
    return {
        "type": "column", "id": "root",
        "children": [
            {
                "type": "form", "id": "f1", "submit_label": "保存",
                "submit_action": {
                    "type": "add_record", "target_state_ref": "records",
                    "field_bindings": {"species": "field_species", "size": "field_size"},
                },
                "children": [
                    {"type": "text_field", "id": "t1", "state_ref": "field_species"},
                    {"type": "text_field", "id": "t2", "state_ref": "field_size"},
                ],
            },
            record_list_view,
        ],
    }


def _default_state() -> dict:
    return {
        "records": {"type": "record_list", "value": []},
        "field_species": {"type": "string", "value": ""},
        "field_size": {"type": "string", "value": ""},
    }


class TestVersionGatingV13(unittest.TestCase):
    """v1.3専用のState/Widget/Actionが、v1.0〜v1.2文書では使えないことを確認する。"""

    def test_v1_2_document_cannot_use_record_list_state(self) -> None:
        doc = {
            "version": "1.2", "initial_screen_id": "s1",
            "screens": [{"id": "s1", "title": "S1",
                         "state": {"records": {"type": "record_list", "value": []}},
                         "body": {"type": "text", "id": "t1", "value": "x"}}],
        }
        result = validate_forge_document(doc)
        self.assertFalse(result.valid)
        self.assertTrue(any(e.rule == "state_type_not_allowed_in_version" for e in result.errors))

    def test_v1_2_document_cannot_use_record_list_view_widget(self) -> None:
        doc = {
            "version": "1.2", "initial_screen_id": "s1",
            "screens": [{"id": "s1", "title": "S1",
                         "state": {"records": {"type": "checklist", "value": []}},
                         "body": {"type": "record_list_view", "id": "rlv1", "state_ref": "records"}}],
        }
        result = validate_forge_document(doc)
        self.assertFalse(result.valid)
        self.assertTrue(any(e.rule == "widget_not_allowed_in_version" for e in result.errors))

    def test_v1_2_document_cannot_use_add_record_action(self) -> None:
        doc = {
            "version": "1.2", "initial_screen_id": "s1",
            "screens": [{
                "id": "s1", "title": "S1",
                "state": {"records": {"type": "checklist", "value": []}, "f": {"type": "string", "value": ""}},
                "body": {"type": "button", "id": "b1", "label": "追加",
                         "action": {"type": "add_record", "target_state_ref": "records",
                                    "field_bindings": {"x": "f"}}},
            }],
        }
        result = validate_forge_document(doc)
        self.assertFalse(result.valid)
        self.assertTrue(any(e.rule == "action_not_allowed_in_version" for e in result.errors))

    def test_v1_3_document_with_only_v1_2_features_still_passes(self) -> None:
        """後方互換性の核心: v1.3文書でも、record系を一切使わなければ
        引き続き合格しなければならない。"""
        doc = _v13_doc(
            {"type": "checklist", "id": "c1", "state_ref": "items"},
            state={"items": {"type": "checklist", "value": []}},
        )
        result = validate_forge_document(doc)
        self.assertTrue(result.valid, msg=result.to_dict())

    def test_v1_3_text_field_can_still_use_validation_property(self) -> None:
        """回帰テスト: v1.2で追加された`validation`プロパティ(text_field/
        checkbox)が、v1.3文書でも引き続き使えることを確認する
        (実装時に発見した実際のバグ: version判定が'== \"1.2\"'のまま
        だったため、v1.3文書でtext_field.validationを使うと
        additional_propertiesエラーになっていた)。"""
        doc = _v13_doc({
            "type": "text_field", "id": "t1", "state_ref": "f1",
            "validation": {"rules": [{"type": "required", "message": "必須です"}]},
        }, state={"f1": {"type": "string", "value": ""}})
        result = validate_forge_document(doc)
        self.assertTrue(result.valid, msg=result.to_dict())


class TestRecordListState(unittest.TestCase):
    def test_valid_record_list_with_multiple_fields_passes(self) -> None:
        doc = _v13_doc(_record_form_and_list_body(), state={
            "records": {"type": "record_list", "value": [
                {"id": "rec_1", "fields": {"species": "アジ", "size": 30, "is_released": False}},
            ]},
            "field_species": {"type": "string", "value": ""},
            "field_size": {"type": "string", "value": ""},
        })
        result = validate_forge_document(doc)
        self.assertTrue(result.valid, msg=result.to_dict())

    def test_empty_record_list_is_valid(self) -> None:
        doc = _v13_doc(_record_form_and_list_body(), state=_default_state())
        result = validate_forge_document(doc)
        self.assertTrue(result.valid, msg=result.to_dict())

    def test_record_item_missing_id_is_rejected(self) -> None:
        state = _default_state()
        state["records"]["value"] = [{"fields": {"species": "アジ"}}]
        doc = _v13_doc(_record_form_and_list_body(), state=state)
        result = validate_forge_document(doc)
        self.assertFalse(result.valid)
        self.assertTrue(any(e.rule == "identifier_format" for e in result.errors))

    def test_record_item_missing_fields_is_rejected(self) -> None:
        state = _default_state()
        state["records"]["value"] = [{"id": "rec_1"}]
        doc = _v13_doc(_record_form_and_list_body(), state=state)
        result = validate_forge_document(doc)
        self.assertFalse(result.valid)

    def test_record_field_with_nested_object_value_is_rejected(self) -> None:
        """Phase1はRecord Fieldの値を文字列・数値・真偽値のみに限定する
        (record_schemas未導入のため、ネスト構造は許可しない)。"""
        state = _default_state()
        state["records"]["value"] = [{"id": "rec_1", "fields": {"species": {"nested": "not allowed"}}}]
        doc = _v13_doc(_record_form_and_list_body(), state=state)
        result = validate_forge_document(doc)
        self.assertFalse(result.valid)

    def test_record_field_with_list_value_is_rejected(self) -> None:
        state = _default_state()
        state["records"]["value"] = [{"id": "rec_1", "fields": {"species": ["アジ", "サバ"]}}]
        doc = _v13_doc(_record_form_and_list_body(), state=state)
        result = validate_forge_document(doc)
        self.assertFalse(result.valid)

    def test_record_field_numeric_value_is_accepted(self) -> None:
        state = _default_state()
        state["records"]["value"] = [{"id": "rec_1", "fields": {"size": 30}}]
        doc = _v13_doc(_record_form_and_list_body(), state=state)
        result = validate_forge_document(doc)
        self.assertTrue(result.valid, msg=result.to_dict())

    def test_record_field_boolean_value_is_accepted(self) -> None:
        state = _default_state()
        state["records"]["value"] = [{"id": "rec_1", "fields": {"is_done": True}}]
        doc = _v13_doc(_record_form_and_list_body(), state=state)
        result = validate_forge_document(doc)
        self.assertTrue(result.valid, msg=result.to_dict())

    def test_invalid_field_name_is_rejected(self) -> None:
        """Field名も`identifier`パターン(小文字スネークケース)に従う必要がある。"""
        state = _default_state()
        state["records"]["value"] = [{"id": "rec_1", "fields": {"Species!": "アジ"}}]
        doc = _v13_doc(_record_form_and_list_body(), state=state)
        result = validate_forge_document(doc)
        self.assertFalse(result.valid)


class TestRecordListViewWidget(unittest.TestCase):
    def test_card_layout_is_accepted(self) -> None:
        doc = _v13_doc(_record_form_and_list_body(layout="card"), state=_default_state())
        result = validate_forge_document(doc)
        self.assertTrue(result.valid, msg=result.to_dict())

    def test_table_layout_is_rejected(self) -> None:
        """指示書の制約: Phase1はtable layoutを実装しない。"""
        doc = _v13_doc(_record_form_and_list_body(layout="table"), state=_default_state())
        result = validate_forge_document(doc)
        self.assertFalse(result.valid)
        self.assertTrue(any(e.rule == "enum" for e in result.errors))

    def test_layout_omitted_is_accepted(self) -> None:
        """layoutは省略可能(既定でcard相当として扱われる、Runtime側の既定値)。"""
        doc = _v13_doc(_record_form_and_list_body(layout=None), state=_default_state())
        result = validate_forge_document(doc)
        self.assertTrue(result.valid, msg=result.to_dict())

    def test_state_ref_must_reference_a_record_list_state(self) -> None:
        """既存の`state_reference_type_mismatch`と同じ仕組みが、record_
        list_viewでも機能することを確認する(checklist型を誤って参照)。"""
        state = _default_state()
        state["records"] = {"type": "checklist", "value": []}
        doc = _v13_doc(_record_form_and_list_body(), state=state)
        result = validate_forge_document(doc)
        self.assertFalse(result.valid)
        self.assertTrue(any(e.rule == "state_reference_type_mismatch" for e in result.errors))

    def test_missing_state_ref_target_is_rejected(self) -> None:
        doc = _v13_doc(
            {"type": "record_list_view", "id": "rlv1", "state_ref": "does_not_exist"},
            state={},
        )
        result = validate_forge_document(doc)
        self.assertFalse(result.valid)
        self.assertTrue(any(e.rule == "state_reference_exists" for e in result.errors))


class TestAddRecordAction(unittest.TestCase):
    def test_valid_add_record_passes(self) -> None:
        doc = _v13_doc(_record_form_and_list_body(), state=_default_state())
        result = validate_forge_document(doc)
        self.assertTrue(result.valid, msg=result.to_dict())

    def test_add_record_target_must_be_record_list(self) -> None:
        state = _default_state()
        state["records"] = {"type": "checklist", "value": []}
        doc = _v13_doc(_record_form_and_list_body(), state=state)
        result = validate_forge_document(doc)
        self.assertFalse(result.valid)
        self.assertTrue(any(e.rule == "state_reference_type_mismatch" for e in result.errors))

    def test_add_record_field_binding_source_must_exist(self) -> None:
        state = _default_state()
        del state["field_size"]
        doc = _v13_doc(_record_form_and_list_body(), state=state)
        result = validate_forge_document(doc)
        self.assertFalse(result.valid)
        self.assertTrue(any(e.rule == "state_reference_exists" for e in result.errors))

    def test_add_record_field_binding_source_must_be_primitive_typed(self) -> None:
        """field_bindingsのsourceがrecord_list/checklist等の複合型だと
        不正(1件分のField値としては使えない)。"""
        state = _default_state()
        state["field_species"] = {"type": "checklist", "value": []}
        doc = _v13_doc(_record_form_and_list_body(), state=state)
        result = validate_forge_document(doc)
        self.assertFalse(result.valid)
        self.assertTrue(any(e.rule == "state_reference_type_mismatch" for e in result.errors))

    def test_add_record_requires_at_least_one_field_binding(self) -> None:
        state = _default_state()
        doc = _v13_doc({
            "type": "button", "id": "b1", "label": "追加",
            "action": {"type": "add_record", "target_state_ref": "records", "field_bindings": {}},
        }, state=state)
        result = validate_forge_document(doc)
        self.assertFalse(result.valid)
        self.assertTrue(any(e.rule == "array_bounds" for e in result.errors))

    def test_add_record_can_be_the_success_action_of_a_button_not_only_a_form(self) -> None:
        """`add_record`自体はAction共通の型のため、formのsubmit_action以外
        (例えばbuttonのaction)からも呼べる(汎用性の確認)。"""
        state = _default_state()
        doc = _v13_doc({
            "type": "column", "id": "root",
            "children": [
                {"type": "text_field", "id": "t1", "state_ref": "field_species"},
                {"type": "button", "id": "b1", "label": "追加",
                 "action": {"type": "add_record", "target_state_ref": "records",
                            "field_bindings": {"species": "field_species"}}},
                {"type": "record_list_view", "id": "rlv1", "state_ref": "records"},
            ],
        }, state=state)
        result = validate_forge_document(doc)
        self.assertTrue(result.valid, msg=result.to_dict())


def _crud_state() -> dict:
    return {
        "records": {"type": "record_list", "value": [{"id": "rec_1", "fields": {"species": "アジ"}}]},
        "selected": {"type": "selected_record", "value": None},
        "field_species": {"type": "string", "value": ""},
    }


def _selectable_list_view(**overrides: object) -> dict:
    node = {
        "type": "record_list_view", "id": "rlv1", "state_ref": "records",
        "selectable": True, "selected_state_ref": "selected",
        "select_field_bindings": {"species": "field_species"},
    }
    node.update(overrides)
    return node


class TestSelectedRecordState(unittest.TestCase):
    """FORGE v0.8(Record Runtime Phase2)。`selected_record` State型。"""

    def test_null_selection_is_valid(self) -> None:
        doc = _v13_doc(_selectable_list_view(), state=_crud_state())
        result = validate_forge_document(doc)
        self.assertTrue(result.valid, msg=result.to_dict())

    def test_selected_record_with_a_record_value_is_valid(self) -> None:
        state = _crud_state()
        state["selected"]["value"] = {"id": "rec_1", "fields": {"species": "アジ"}}
        doc = _v13_doc(_selectable_list_view(), state=state)
        result = validate_forge_document(doc)
        self.assertTrue(result.valid, msg=result.to_dict())

    def test_selected_record_value_missing_id_is_rejected(self) -> None:
        state = _crud_state()
        state["selected"]["value"] = {"fields": {"species": "アジ"}}
        doc = _v13_doc(_selectable_list_view(), state=state)
        result = validate_forge_document(doc)
        self.assertFalse(result.valid)

    def test_v1_2_document_cannot_use_selected_record_state(self) -> None:
        doc = {
            "version": "1.2", "initial_screen_id": "s1",
            "screens": [{"id": "s1", "title": "S1",
                         "state": {"selected": {"type": "selected_record", "value": None}},
                         "body": {"type": "text", "id": "t1", "value": "x"}}],
        }
        result = validate_forge_document(doc)
        self.assertFalse(result.valid)
        self.assertTrue(any(e.rule == "state_type_not_allowed_in_version" for e in result.errors))


class TestRecordListViewSelectable(unittest.TestCase):
    """FORGE v0.8。`record_list_view`の`selectable`関連プロパティ。"""

    def test_selectable_true_with_selected_state_ref_is_valid(self) -> None:
        doc = _v13_doc(_selectable_list_view(), state=_crud_state())
        result = validate_forge_document(doc)
        self.assertTrue(result.valid, msg=result.to_dict())

    def test_selectable_true_without_selected_state_ref_is_rejected(self) -> None:
        node = _selectable_list_view()
        del node["selected_state_ref"]
        doc = _v13_doc(node, state=_crud_state())
        result = validate_forge_document(doc)
        self.assertFalse(result.valid)

    def test_selectable_false_does_not_require_selected_state_ref(self) -> None:
        """`selectable`省略時(既定false相当)は、これまで通りselected_state_ref
        無しで合格する(Phase1からの後方互換)。"""
        doc = _v13_doc({"type": "record_list_view", "id": "rlv1", "state_ref": "records"}, state=_crud_state())
        result = validate_forge_document(doc)
        self.assertTrue(result.valid, msg=result.to_dict())

    def test_selected_state_ref_pointing_to_wrong_type_is_rejected(self) -> None:
        state = _crud_state()
        state["selected"] = {"type": "checklist", "value": []}
        doc = _v13_doc(_selectable_list_view(), state=state)
        result = validate_forge_document(doc)
        self.assertFalse(result.valid)
        self.assertTrue(any(e.rule == "state_reference_type_mismatch" for e in result.errors))

    def test_select_field_bindings_source_must_exist(self) -> None:
        state = _crud_state()
        del state["field_species"]
        doc = _v13_doc(_selectable_list_view(), state=state)
        result = validate_forge_document(doc)
        self.assertFalse(result.valid)
        self.assertTrue(any(e.rule == "state_reference_exists" for e in result.errors))

    def test_select_field_bindings_is_optional(self) -> None:
        node = _selectable_list_view()
        del node["select_field_bindings"]
        doc = _v13_doc(node, state=_crud_state())
        result = validate_forge_document(doc)
        self.assertTrue(result.valid, msg=result.to_dict())


class TestUpdateRecordAction(unittest.TestCase):
    """FORGE v0.8。`update_record` Action。"""

    def _doc_with_update_form(self) -> dict:
        return _v13_doc({
            "type": "column", "id": "root",
            "children": [
                _selectable_list_view(),
                {
                    "type": "form", "id": "edit_form", "submit_label": "更新",
                    "submit_action": {
                        "type": "update_record", "target_state_ref": "records", "record_id_ref": "selected",
                        "field_bindings": {"species": "field_species"},
                    },
                    "children": [{"type": "text_field", "id": "ef1", "state_ref": "field_species"}],
                },
            ],
        }, state=_crud_state())

    def test_valid_update_record_passes(self) -> None:
        result = validate_forge_document(self._doc_with_update_form())
        self.assertTrue(result.valid, msg=result.to_dict())

    def test_update_record_target_must_be_record_list(self) -> None:
        doc = self._doc_with_update_form()
        doc["screens"][0]["state"]["records"] = {"type": "checklist", "value": []}
        result = validate_forge_document(doc)
        self.assertFalse(result.valid)
        self.assertTrue(any(e.rule == "state_reference_type_mismatch" for e in result.errors))

    def test_update_record_id_ref_must_be_selected_record_type(self) -> None:
        doc = self._doc_with_update_form()
        doc["screens"][0]["body"]["children"][1]["submit_action"]["record_id_ref"] = "field_species"
        result = validate_forge_document(doc)
        self.assertFalse(result.valid)
        self.assertTrue(any(e.rule == "state_reference_type_mismatch" for e in result.errors))

    def test_update_record_requires_field_bindings(self) -> None:
        doc = self._doc_with_update_form()
        del doc["screens"][0]["body"]["children"][1]["submit_action"]["field_bindings"]
        result = validate_forge_document(doc)
        self.assertFalse(result.valid)


class TestDeleteRecordAction(unittest.TestCase):
    """FORGE v0.8。`delete_record` Action。"""

    def _doc_with_delete_button(self) -> dict:
        return _v13_doc({
            "type": "column", "id": "root",
            "children": [
                _selectable_list_view(),
                {
                    "type": "button", "id": "delete_btn", "label": "削除",
                    "action": {"type": "delete_record", "target_state_ref": "records", "record_id_ref": "selected"},
                },
            ],
        }, state=_crud_state())

    def test_valid_delete_record_passes(self) -> None:
        result = validate_forge_document(self._doc_with_delete_button())
        self.assertTrue(result.valid, msg=result.to_dict())

    def test_delete_record_target_must_be_record_list(self) -> None:
        doc = self._doc_with_delete_button()
        doc["screens"][0]["state"]["records"] = {"type": "string_list", "value": []}
        result = validate_forge_document(doc)
        self.assertFalse(result.valid)

    def test_delete_record_requires_record_id_ref(self) -> None:
        doc = self._doc_with_delete_button()
        del doc["screens"][0]["body"]["children"][1]["action"]["record_id_ref"]
        result = validate_forge_document(doc)
        self.assertFalse(result.valid)

    def test_v1_2_document_cannot_use_delete_record_action(self) -> None:
        doc = {
            "version": "1.2", "initial_screen_id": "s1",
            "screens": [{
                "id": "s1", "title": "S1",
                "state": {"records": {"type": "checklist", "value": []}, "selected": {"type": "string", "value": ""}},
                "body": {"type": "button", "id": "b1", "label": "削除",
                         "action": {"type": "delete_record", "target_state_ref": "records", "record_id_ref": "selected"}},
            }],
        }
        result = validate_forge_document(doc)
        self.assertFalse(result.valid)
        self.assertTrue(any(e.rule == "action_not_allowed_in_version" for e in result.errors))


class TestSelectRecordActionSchemaCompleteness(unittest.TestCase):
    """FORGE v0.8。`select_record`は通常Compilerが単独JSONとして生成
    しない(Runtimeが動的に組み立てる、schema_validator.pyの
    モジュールdocstring参照)が、Schema/Validatorとしての型定義自体は
    独立して検査できることを確認する。"""

    def test_select_record_as_a_standalone_action_is_schema_valid(self) -> None:
        state = _crud_state()
        doc = _v13_doc({
            "type": "button", "id": "b1", "label": "選択(テスト専用)",
            "action": {
                "type": "select_record", "source_state_ref": "records", "target_state_ref": "selected",
                "field_bindings": {"species": "field_species"},
            },
        }, state=state)
        result = validate_forge_document(doc)
        self.assertTrue(result.valid, msg=result.to_dict())

    def test_select_record_missing_target_state_ref_is_rejected(self) -> None:
        state = _crud_state()
        doc = _v13_doc({
            "type": "button", "id": "b1", "label": "選択",
            "action": {"type": "select_record", "source_state_ref": "records"},
        }, state=state)
        result = validate_forge_document(doc)
        self.assertFalse(result.valid)


if __name__ == "__main__":
    unittest.main()
