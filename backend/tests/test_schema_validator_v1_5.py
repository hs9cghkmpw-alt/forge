"""Language v1.5拡張(Product Quality Sprint1)のテスト
(FORGE v1.0開発指示)。

`design_tokens`(色・角丸・余白)・`section_header` Widget・
`record_list_view.layout`への`"grid"`追加を検証する。v1.0〜v1.4との
後方互換性はtest_schema_validator*.py の既存テスト(無改変のまま)が
引き続き担保する。

実行方法:
    cd backend
    python -m unittest tests.test_schema_validator_v1_5 -v
"""

from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.ai.validators.schema_validator import validate_forge_document  # noqa: E402


def _v15_doc(body: dict, *, state: dict | None = None, design_tokens: dict | None = None) -> dict:
    doc: dict = {
        "version": "1.5",
        "initial_screen_id": "s1",
        "screens": [{"id": "s1", "title": "S1", "state": state or {}, "body": body}],
    }
    if design_tokens is not None:
        doc["design_tokens"] = design_tokens
    return doc


def _full_design_tokens() -> dict:
    return {
        "color_scheme": {"primary": "#6366F1", "secondary": "#8B5CF6", "success": "#10B981", "error": "#EF4444"},
        "corner_radius": {"small": 8, "medium": 12, "large": 20},
        "spacing_scale": {"xs": 4, "sm": 8, "md": 16, "lg": 24, "xl": 32},
    }


class TestVersionGatingV15(unittest.TestCase):
    """design_tokens/section_header/grid layoutがv1.5以降でのみ使用でき、
    v1.4以前では拒否されることを確認する。"""

    def test_v1_4_document_cannot_use_design_tokens(self) -> None:
        doc = {
            "version": "1.4", "initial_screen_id": "s1",
            "screens": [{"id": "s1", "title": "S1", "state": {}, "body": {"type": "text", "id": "t1", "value": "x"}}],
            "design_tokens": _full_design_tokens(),
        }
        result = validate_forge_document(doc)
        self.assertFalse(result.valid)
        self.assertTrue(any(e.rule == "field_not_allowed_in_version" for e in result.errors))

    def test_v1_4_document_cannot_use_section_header(self) -> None:
        doc = {
            "version": "1.4", "initial_screen_id": "s1",
            "screens": [{"id": "s1", "title": "S1", "state": {},
                         "body": {"type": "section_header", "id": "sec1", "title": "見出し"}}],
        }
        result = validate_forge_document(doc)
        self.assertFalse(result.valid)
        self.assertTrue(any(e.rule == "widget_not_allowed_in_version" for e in result.errors))

    def test_v1_4_document_cannot_use_grid_layout(self) -> None:
        doc = {
            "version": "1.4", "initial_screen_id": "s1",
            "screens": [{"id": "s1", "title": "S1", "state": {"r": {"type": "record_list", "value": []}},
                         "body": {"type": "record_list_view", "id": "rlv1", "state_ref": "r", "layout": "grid"}}],
        }
        result = validate_forge_document(doc)
        self.assertFalse(result.valid)
        self.assertTrue(any(e.rule == "enum" for e in result.errors))

    def test_v1_5_document_with_only_v1_4_features_still_passes(self) -> None:
        """後方互換性の核心: v1.5文書でも、design_tokens/section_header/
        gridを一切使わなければ引き続き合格しなければならない。"""
        doc = _v15_doc(
            {"type": "record_list_view", "id": "rlv1", "state_ref": "records"},
            state={"records": {"type": "record_list", "value": []}},
        )
        result = validate_forge_document(doc)
        self.assertTrue(result.valid, msg=result.to_dict())


class TestDesignTokens(unittest.TestCase):
    """design_tokens構造の検証。"""

    def test_full_design_tokens_pass(self) -> None:
        doc = _v15_doc({"type": "text", "id": "t1", "value": "x"}, design_tokens=_full_design_tokens())
        result = validate_forge_document(doc)
        self.assertTrue(result.valid, msg=result.to_dict())

    def test_color_scheme_with_only_primary_passes(self) -> None:
        doc = _v15_doc({"type": "text", "id": "t1", "value": "x"},
                        design_tokens={"color_scheme": {"primary": "#000000"}})
        result = validate_forge_document(doc)
        self.assertTrue(result.valid, msg=result.to_dict())

    def test_color_scheme_missing_primary_is_rejected(self) -> None:
        doc = _v15_doc({"type": "text", "id": "t1", "value": "x"},
                        design_tokens={"color_scheme": {"secondary": "#000000"}})
        result = validate_forge_document(doc)
        self.assertFalse(result.valid)

    def test_invalid_hex_color_is_rejected(self) -> None:
        doc = _v15_doc({"type": "text", "id": "t1", "value": "x"},
                        design_tokens={"color_scheme": {"primary": "blue"}})
        result = validate_forge_document(doc)
        self.assertFalse(result.valid)
        self.assertTrue(any(e.rule == "color_format" for e in result.errors))

    def test_unknown_color_role_is_rejected(self) -> None:
        doc = _v15_doc({"type": "text", "id": "t1", "value": "x"},
                        design_tokens={"color_scheme": {"primary": "#000000", "unknown_role": "#111111"}})
        result = validate_forge_document(doc)
        self.assertFalse(result.valid)

    def test_negative_corner_radius_is_rejected(self) -> None:
        doc = _v15_doc({"type": "text", "id": "t1", "value": "x"},
                        design_tokens={"corner_radius": {"small": -1}})
        result = validate_forge_document(doc)
        self.assertFalse(result.valid)

    def test_negative_spacing_is_rejected(self) -> None:
        doc = _v15_doc({"type": "text", "id": "t1", "value": "x"},
                        design_tokens={"spacing_scale": {"md": -4}})
        result = validate_forge_document(doc)
        self.assertFalse(result.valid)

    def test_empty_corner_radius_is_rejected(self) -> None:
        doc = _v15_doc({"type": "text", "id": "t1", "value": "x"}, design_tokens={"corner_radius": {}})
        result = validate_forge_document(doc)
        self.assertFalse(result.valid)

    def test_unknown_top_level_design_token_key_is_rejected(self) -> None:
        doc = _v15_doc({"type": "text", "id": "t1", "value": "x"},
                        design_tokens={"color_scheme": {"primary": "#000000"}, "unknown_block": {}})
        result = validate_forge_document(doc)
        self.assertFalse(result.valid)

    def test_design_tokens_are_independent_of_record_schemas(self) -> None:
        """design_tokensはrecord_schemasとは無関係に、単体でも使用できる。"""
        doc = _v15_doc({"type": "text", "id": "t1", "value": "hello"}, design_tokens=_full_design_tokens())
        result = validate_forge_document(doc)
        self.assertTrue(result.valid, msg=result.to_dict())


class TestSectionHeader(unittest.TestCase):
    """`section_header` Widgetの検証。"""

    def test_title_only_passes(self) -> None:
        doc = _v15_doc({"type": "section_header", "id": "sec1", "title": "記録の追加"})
        result = validate_forge_document(doc)
        self.assertTrue(result.valid, msg=result.to_dict())

    def test_title_and_subtitle_pass(self) -> None:
        doc = _v15_doc({"type": "section_header", "id": "sec1", "title": "記録の追加", "subtitle": "新しい記録を入力してください"})
        result = validate_forge_document(doc)
        self.assertTrue(result.valid, msg=result.to_dict())

    def test_missing_title_is_rejected(self) -> None:
        doc = _v15_doc({"type": "section_header", "id": "sec1"})
        result = validate_forge_document(doc)
        self.assertFalse(result.valid)

    def test_empty_title_is_rejected(self) -> None:
        doc = _v15_doc({"type": "section_header", "id": "sec1", "title": ""})
        result = validate_forge_document(doc)
        self.assertFalse(result.valid)

    def test_section_header_inside_column_passes(self) -> None:
        doc = _v15_doc({
            "type": "column", "id": "root",
            "children": [
                {"type": "section_header", "id": "sec1", "title": "一覧"},
                {"type": "text", "id": "t1", "value": "内容"},
            ],
        })
        result = validate_forge_document(doc)
        self.assertTrue(result.valid, msg=result.to_dict())


class TestRecordListViewGridLayout(unittest.TestCase):
    """`record_list_view.layout: "grid"`の検証。"""

    def test_grid_layout_passes(self) -> None:
        doc = _v15_doc(
            {"type": "record_list_view", "id": "rlv1", "state_ref": "records", "layout": "grid"},
            state={"records": {"type": "record_list", "value": []}},
        )
        result = validate_forge_document(doc)
        self.assertTrue(result.valid, msg=result.to_dict())

    def test_card_layout_still_passes(self) -> None:
        """既存のcard layoutが引き続き合格すること(後方互換)。"""
        doc = _v15_doc(
            {"type": "record_list_view", "id": "rlv1", "state_ref": "records", "layout": "card"},
            state={"records": {"type": "record_list", "value": []}},
        )
        result = validate_forge_document(doc)
        self.assertTrue(result.valid, msg=result.to_dict())

    def test_table_layout_is_still_rejected(self) -> None:
        """指示書の制約: table layoutは今回も実装しない。"""
        doc = _v15_doc(
            {"type": "record_list_view", "id": "rlv1", "state_ref": "records", "layout": "table"},
            state={"records": {"type": "record_list", "value": []}},
        )
        result = validate_forge_document(doc)
        self.assertFalse(result.valid)

    def test_layout_omitted_still_passes(self) -> None:
        doc = _v15_doc(
            {"type": "record_list_view", "id": "rlv1", "state_ref": "records"},
            state={"records": {"type": "record_list", "value": []}},
        )
        result = validate_forge_document(doc)
        self.assertTrue(result.valid, msg=result.to_dict())


class TestV15DoesNotAffectIRVersionOfOtherContracts(unittest.TestCase):
    """指示書のDesign Policy「既存CRUD、Atomicity、Legacy互換性を壊さ
    ない」の裏付け: v1.5はv1.4のAction/State型を1つも変えていない。"""

    def test_v1_5_allows_exactly_the_same_action_types_as_v1_4(self) -> None:
        from app.ai.validators.schema_validator import ACTION_TYPES_BY_VERSION

        self.assertEqual(ACTION_TYPES_BY_VERSION["1.5"], ACTION_TYPES_BY_VERSION["1.4"])

    def test_v1_5_allows_exactly_the_same_state_types_as_v1_4(self) -> None:
        from app.ai.validators.schema_validator import STATE_TYPES_BY_VERSION

        self.assertEqual(STATE_TYPES_BY_VERSION["1.5"], STATE_TYPES_BY_VERSION["1.4"])


if __name__ == "__main__":
    unittest.main()
