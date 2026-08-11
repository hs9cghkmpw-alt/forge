"""Language v1.6拡張(Widget Vocabulary Expansion)のテスト。

FORGE-AI-QUALITY-001、2026-08-11、CEO承認により`docs/spec/LANGUAGE_FREEZE.md`の
Widget追加凍結を解除して着手。`choice_field`(ドロップダウン選択)・
`bar_chart`(record_listの数値Fieldを棒グラフ表示)の2 Widgetを追加する。
v1.0〜v1.5との後方互換性はtest_schema_validator*.py の既存テスト
(無改変のまま)が引き続き担保する。

実行方法:
    cd backend
    python -m unittest tests.test_schema_validator_v1_6 -v
"""

from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.ai.validators.schema_validator import validate_forge_document  # noqa: E402


def _v16_doc(body: dict, *, state: dict | None = None, record_schemas: dict | None = None) -> dict:
    doc: dict = {
        "version": "1.6",
        "initial_screen_id": "s1",
        "screens": [{"id": "s1", "title": "S1", "state": state or {}, "body": body}],
    }
    if record_schemas is not None:
        doc["record_schemas"] = record_schemas
    return doc


class TestVersionGatingV16(unittest.TestCase):
    """choice_field/bar_chartがv1.6以降でのみ使用でき、v1.5以前では
    拒否されることを確認する。"""

    def test_v1_5_document_cannot_use_choice_field(self) -> None:
        doc = {
            "version": "1.5", "initial_screen_id": "s1",
            "screens": [{"id": "s1", "title": "S1", "state": {"c": {"type": "string", "value": ""}},
                         "body": {"type": "choice_field", "id": "cf1", "label": "区分", "state_ref": "c",
                                  "options": ["食費", "交通費"]}}],
        }
        result = validate_forge_document(doc)
        self.assertFalse(result.valid)
        self.assertTrue(any(e.rule == "widget_not_allowed_in_version" for e in result.errors))

    def test_v1_5_document_cannot_use_bar_chart(self) -> None:
        doc = {
            "version": "1.5", "initial_screen_id": "s1",
            "screens": [{"id": "s1", "title": "S1", "state": {"r": {"type": "record_list", "value": []}},
                         "body": {"type": "bar_chart", "id": "bc1", "state_ref": "r",
                                  "value_field": "amount", "label_field": "category"}}],
        }
        result = validate_forge_document(doc)
        self.assertFalse(result.valid)
        self.assertTrue(any(e.rule == "widget_not_allowed_in_version" for e in result.errors))

    def test_v1_6_document_with_only_v1_5_features_still_passes(self) -> None:
        """後方互換性の核心: v1.6文書でも、choice_field/bar_chartを
        一切使わなければ引き続き合格しなければならない。"""
        doc = _v16_doc(
            {"type": "record_list_view", "id": "rlv1", "state_ref": "records"},
            state={"records": {"type": "record_list", "value": []}},
        )
        result = validate_forge_document(doc)
        self.assertTrue(result.valid, msg=result.to_dict())


class TestChoiceField(unittest.TestCase):
    """`choice_field` Widgetの検証。"""

    def test_minimal_choice_field_passes(self) -> None:
        doc = _v16_doc(
            {"type": "choice_field", "id": "cf1", "label": "カテゴリ", "state_ref": "category",
             "options": ["食費", "交通費", "娯楽費"]},
            state={"category": {"type": "string", "value": ""}},
        )
        result = validate_forge_document(doc)
        self.assertTrue(result.valid, msg=result.to_dict())

    def test_choice_field_with_placeholder_passes(self) -> None:
        doc = _v16_doc(
            {"type": "choice_field", "id": "cf1", "label": "カテゴリ", "state_ref": "category",
             "options": ["食費", "交通費"], "placeholder": "選択してください"},
            state={"category": {"type": "string", "value": ""}},
        )
        result = validate_forge_document(doc)
        self.assertTrue(result.valid, msg=result.to_dict())

    def test_missing_options_is_rejected(self) -> None:
        doc = _v16_doc(
            {"type": "choice_field", "id": "cf1", "label": "カテゴリ", "state_ref": "category"},
            state={"category": {"type": "string", "value": ""}},
        )
        result = validate_forge_document(doc)
        self.assertFalse(result.valid)

    def test_empty_options_is_rejected(self) -> None:
        doc = _v16_doc(
            {"type": "choice_field", "id": "cf1", "label": "カテゴリ", "state_ref": "category", "options": []},
            state={"category": {"type": "string", "value": ""}},
        )
        result = validate_forge_document(doc)
        self.assertFalse(result.valid)

    def test_duplicate_options_is_rejected(self) -> None:
        doc = _v16_doc(
            {"type": "choice_field", "id": "cf1", "label": "カテゴリ", "state_ref": "category",
             "options": ["食費", "食費"]},
            state={"category": {"type": "string", "value": ""}},
        )
        result = validate_forge_document(doc)
        self.assertFalse(result.valid)
        self.assertTrue(any(e.rule == "array_uniqueness" for e in result.errors))

    def test_missing_state_ref_is_rejected(self) -> None:
        doc = _v16_doc({"type": "choice_field", "id": "cf1", "label": "カテゴリ", "options": ["食費"]})
        result = validate_forge_document(doc)
        self.assertFalse(result.valid)

    def test_state_ref_must_point_to_string_state(self) -> None:
        doc = _v16_doc(
            {"type": "choice_field", "id": "cf1", "label": "カテゴリ", "state_ref": "category",
             "options": ["食費"]},
            state={"category": {"type": "boolean", "value": False}},
        )
        result = validate_forge_document(doc)
        self.assertFalse(result.valid)
        self.assertTrue(any(e.rule == "state_reference_type_mismatch" for e in result.errors))

    def test_missing_label_is_rejected(self) -> None:
        doc = _v16_doc(
            {"type": "choice_field", "id": "cf1", "state_ref": "category", "options": ["食費"]},
            state={"category": {"type": "string", "value": ""}},
        )
        result = validate_forge_document(doc)
        self.assertFalse(result.valid)

    def test_choice_field_counts_as_form_input(self) -> None:
        """`input_types`に追加した効果: choice_fieldしか無いformでも
        form_without_input警告が出ないこと。"""
        doc = _v16_doc(
            {"type": "form", "id": "form1", "submit_label": "送信",
             "submit_action": {"type": "go_back"},
             "children": [
                 {"type": "choice_field", "id": "cf1", "label": "カテゴリ", "state_ref": "category",
                  "options": ["食費", "交通費"]},
             ]},
            state={"category": {"type": "string", "value": ""}},
        )
        result = validate_forge_document(doc)
        self.assertTrue(result.valid, msg=result.to_dict())
        self.assertFalse(any(w.rule == "form_without_input" for w in result.warnings))


class TestBarChart(unittest.TestCase):
    """`bar_chart` Widgetの検証。"""

    def _budget_schema(self) -> dict:
        return {
            "budget_item": {
                "fields": [
                    {"name": "category", "type": "string", "label": "カテゴリ"},
                    {"name": "amount", "type": "number", "label": "金額"},
                ],
            },
        }

    def test_minimal_bar_chart_passes(self) -> None:
        doc = _v16_doc(
            {"type": "bar_chart", "id": "bc1", "state_ref": "records",
             "value_field": "amount", "label_field": "category"},
            state={"records": {"type": "record_list", "value": [], "schema_ref": "budget_item"}},
            record_schemas=self._budget_schema(),
        )
        result = validate_forge_document(doc)
        self.assertTrue(result.valid, msg=result.to_dict())

    def test_bar_chart_with_title_passes(self) -> None:
        doc = _v16_doc(
            {"type": "bar_chart", "id": "bc1", "state_ref": "records",
             "value_field": "amount", "label_field": "category", "title": "カテゴリ別支出"},
            state={"records": {"type": "record_list", "value": [], "schema_ref": "budget_item"}},
            record_schemas=self._budget_schema(),
        )
        result = validate_forge_document(doc)
        self.assertTrue(result.valid, msg=result.to_dict())

    def test_missing_value_field_is_rejected(self) -> None:
        doc = _v16_doc(
            {"type": "bar_chart", "id": "bc1", "state_ref": "records", "label_field": "category"},
            state={"records": {"type": "record_list", "value": [], "schema_ref": "budget_item"}},
            record_schemas=self._budget_schema(),
        )
        result = validate_forge_document(doc)
        self.assertFalse(result.valid)

    def test_state_ref_must_point_to_record_list(self) -> None:
        doc = _v16_doc(
            {"type": "bar_chart", "id": "bc1", "state_ref": "notes",
             "value_field": "amount", "label_field": "category"},
            state={"notes": {"type": "string", "value": ""}},
        )
        result = validate_forge_document(doc)
        self.assertFalse(result.valid)
        self.assertTrue(any(e.rule == "state_reference_type_mismatch" for e in result.errors))

    def test_value_field_not_in_schema_is_rejected(self) -> None:
        """存在しないFieldでグラフを描こうとした場合を検出する
        (record_list_view.display_fieldsより踏み込んだ検査、詳細は
        schema_validator.py内のコメント参照)。"""
        doc = _v16_doc(
            {"type": "bar_chart", "id": "bc1", "state_ref": "records",
             "value_field": "does_not_exist", "label_field": "category"},
            state={"records": {"type": "record_list", "value": [], "schema_ref": "budget_item"}},
            record_schemas=self._budget_schema(),
        )
        result = validate_forge_document(doc)
        self.assertFalse(result.valid)
        self.assertTrue(any(e.rule == "field_reference_exists" for e in result.errors))

    def test_value_field_of_wrong_type_is_rejected(self) -> None:
        """value_fieldはtype=numberのFieldである必要がある
        (文字列Fieldでは棒の高さを決められない)。"""
        doc = _v16_doc(
            {"type": "bar_chart", "id": "bc1", "state_ref": "records",
             "value_field": "category", "label_field": "category"},
            state={"records": {"type": "record_list", "value": [], "schema_ref": "budget_item"}},
            record_schemas=self._budget_schema(),
        )
        result = validate_forge_document(doc)
        self.assertFalse(result.valid)
        self.assertTrue(any(e.rule == "field_type_mismatch" for e in result.errors))

    def test_label_field_not_in_schema_is_rejected(self) -> None:
        doc = _v16_doc(
            {"type": "bar_chart", "id": "bc1", "state_ref": "records",
             "value_field": "amount", "label_field": "does_not_exist"},
            state={"records": {"type": "record_list", "value": [], "schema_ref": "budget_item"}},
            record_schemas=self._budget_schema(),
        )
        result = validate_forge_document(doc)
        self.assertFalse(result.valid)
        self.assertTrue(any(e.rule == "field_reference_exists" for e in result.errors))


class TestV16DoesNotAddNewActionOrStateTypes(unittest.TestCase):
    """指示書のDesign Policy踏襲: v1.6はv1.5のAction/State型を1つも
    変えていない(choice_fieldは既存の"string"、bar_chartは既存の
    "record_list"を再利用する)。"""

    def test_v1_6_allows_exactly_the_same_action_types_as_v1_5(self) -> None:
        from app.ai.validators.schema_validator import ACTION_TYPES_BY_VERSION

        self.assertEqual(ACTION_TYPES_BY_VERSION["1.6"], ACTION_TYPES_BY_VERSION["1.5"])

    def test_v1_6_allows_exactly_the_same_state_types_as_v1_5(self) -> None:
        from app.ai.validators.schema_validator import STATE_TYPES_BY_VERSION

        self.assertEqual(STATE_TYPES_BY_VERSION["1.6"], STATE_TYPES_BY_VERSION["1.5"])


if __name__ == "__main__":
    unittest.main()
