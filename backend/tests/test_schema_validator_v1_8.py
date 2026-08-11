"""Language v1.8拡張(Widget Vocabulary Expansion 第3弾)のテスト。

FORGE-AI-QUALITY-001、2026-08-11、CEO「壊れてる?って機能でもどんどん
追加してくれ。あとでなおす。」への対応。`slider`(範囲指定の数値入力)
Widgetを追加する。v1.0〜v1.7との後方互換性はtest_schema_validator*.py
の既存テスト(無改変のまま)が引き続き担保する。

実行方法:
    cd backend
    python -m unittest tests.test_schema_validator_v1_8 -v
"""

from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.ai.validators.schema_validator import validate_forge_document  # noqa: E402


def _v18_doc(body: dict, *, state: dict | None = None) -> dict:
    return {
        "version": "1.8",
        "initial_screen_id": "s1",
        "screens": [{"id": "s1", "title": "S1", "state": state or {}, "body": body}],
    }


class TestVersionGatingV18(unittest.TestCase):
    def test_v1_7_document_cannot_use_slider(self) -> None:
        doc = {
            "version": "1.7", "initial_screen_id": "s1",
            "screens": [{"id": "s1", "title": "S1", "state": {"r": {"type": "number", "value": 1}},
                         "body": {"type": "slider", "id": "sl1", "label": "評価", "state_ref": "r", "min": 1, "max": 5}}],
        }
        result = validate_forge_document(doc)
        self.assertFalse(result.valid)
        self.assertTrue(any(e.rule == "widget_not_allowed_in_version" for e in result.errors))

    def test_v1_8_document_with_only_v1_7_features_still_passes(self) -> None:
        doc = _v18_doc({"type": "date_field", "id": "df1", "label": "日付", "state_ref": "d"},
                        state={"d": {"type": "string", "value": ""}})
        result = validate_forge_document(doc)
        self.assertTrue(result.valid, msg=result.to_dict())


class TestSlider(unittest.TestCase):
    def test_minimal_slider_passes(self) -> None:
        doc = _v18_doc(
            {"type": "slider", "id": "sl1", "label": "評価", "state_ref": "rating", "min": 1, "max": 5},
            state={"rating": {"type": "number", "value": 1}},
        )
        result = validate_forge_document(doc)
        self.assertTrue(result.valid, msg=result.to_dict())

    def test_float_bounds_pass(self) -> None:
        doc = _v18_doc(
            {"type": "slider", "id": "sl1", "label": "満足度", "state_ref": "score", "min": 0.0, "max": 1.0},
            state={"score": {"type": "number", "value": 0.0}},
        )
        result = validate_forge_document(doc)
        self.assertTrue(result.valid, msg=result.to_dict())

    def test_missing_min_is_rejected(self) -> None:
        doc = _v18_doc(
            {"type": "slider", "id": "sl1", "label": "評価", "state_ref": "rating", "max": 5},
            state={"rating": {"type": "number", "value": 1}},
        )
        result = validate_forge_document(doc)
        self.assertFalse(result.valid)

    def test_missing_max_is_rejected(self) -> None:
        doc = _v18_doc(
            {"type": "slider", "id": "sl1", "label": "評価", "state_ref": "rating", "min": 1},
            state={"rating": {"type": "number", "value": 1}},
        )
        result = validate_forge_document(doc)
        self.assertFalse(result.valid)

    def test_min_greater_than_max_is_rejected(self) -> None:
        doc = _v18_doc(
            {"type": "slider", "id": "sl1", "label": "評価", "state_ref": "rating", "min": 5, "max": 1},
            state={"rating": {"type": "number", "value": 1}},
        )
        result = validate_forge_document(doc)
        self.assertFalse(result.valid)
        self.assertTrue(any(e.rule == "range" for e in result.errors))

    def test_min_equal_to_max_is_rejected(self) -> None:
        doc = _v18_doc(
            {"type": "slider", "id": "sl1", "label": "評価", "state_ref": "rating", "min": 3, "max": 3},
            state={"rating": {"type": "number", "value": 3}},
        )
        result = validate_forge_document(doc)
        self.assertFalse(result.valid)

    def test_missing_label_is_rejected(self) -> None:
        doc = _v18_doc(
            {"type": "slider", "id": "sl1", "state_ref": "rating", "min": 1, "max": 5},
            state={"rating": {"type": "number", "value": 1}},
        )
        result = validate_forge_document(doc)
        self.assertFalse(result.valid)

    def test_state_ref_must_point_to_number_state(self) -> None:
        doc = _v18_doc(
            {"type": "slider", "id": "sl1", "label": "評価", "state_ref": "rating", "min": 1, "max": 5},
            state={"rating": {"type": "string", "value": ""}},
        )
        result = validate_forge_document(doc)
        self.assertFalse(result.valid)
        self.assertTrue(any(e.rule == "state_reference_type_mismatch" for e in result.errors))

    def test_slider_counts_as_form_input(self) -> None:
        doc = _v18_doc(
            {"type": "form", "id": "form1", "submit_label": "送信", "submit_action": {"type": "go_back"},
             "children": [{"type": "slider", "id": "sl1", "label": "評価", "state_ref": "rating", "min": 1, "max": 5}]},
            state={"rating": {"type": "number", "value": 1}},
        )
        result = validate_forge_document(doc)
        self.assertTrue(result.valid, msg=result.to_dict())
        self.assertFalse(any(w.rule == "form_without_input" for w in result.warnings))

    def test_bool_is_not_accepted_as_min_or_max(self) -> None:
        """PythonではboolがintのサブクラスであるためTrue/Falseが誤って
        数値として通ってしまう典型的な罠の回帰テスト
        (`isinstance(v, bool)`チェックの確認)。"""
        doc = _v18_doc(
            {"type": "slider", "id": "sl1", "label": "評価", "state_ref": "rating", "min": True, "max": 5},
            state={"rating": {"type": "number", "value": 1}},
        )
        result = validate_forge_document(doc)
        self.assertFalse(result.valid)


class TestV18DoesNotAddNewActionOrStateTypes(unittest.TestCase):
    def test_v1_8_allows_exactly_the_same_action_types_as_v1_7(self) -> None:
        from app.ai.validators.schema_validator import ACTION_TYPES_BY_VERSION

        self.assertEqual(ACTION_TYPES_BY_VERSION["1.8"], ACTION_TYPES_BY_VERSION["1.7"])

    def test_v1_8_allows_exactly_the_same_state_types_as_v1_7(self) -> None:
        from app.ai.validators.schema_validator import STATE_TYPES_BY_VERSION

        self.assertEqual(STATE_TYPES_BY_VERSION["1.8"], STATE_TYPES_BY_VERSION["1.7"])


if __name__ == "__main__":
    unittest.main()
