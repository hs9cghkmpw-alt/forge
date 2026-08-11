"""Language v1.7拡張(Widget Vocabulary Expansion 第2弾)のテスト。

FORGE-AI-QUALITY-001、2026-08-11、CEO「全て実装してくれ。確認もしなくて
良い、ゴールは示している。つくってくれ。」への対応。`date_field`
(カレンダー選択)・`tab_view`(タブ切り替えコンテナ)の2 Widgetを追加する。
v1.0〜v1.6との後方互換性はtest_schema_validator*.py の既存テスト
(無改変のまま)が引き続き担保する。

実行方法:
    cd backend
    python -m unittest tests.test_schema_validator_v1_7 -v
"""

from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.ai.validators.schema_validator import validate_forge_document  # noqa: E402


def _v17_doc(body: dict, *, state: dict | None = None) -> dict:
    return {
        "version": "1.7",
        "initial_screen_id": "s1",
        "screens": [{"id": "s1", "title": "S1", "state": state or {}, "body": body}],
    }


class TestVersionGatingV17(unittest.TestCase):
    """date_field/tab_viewがv1.7以降でのみ使用でき、v1.6以前では拒否
    されることを確認する。"""

    def test_v1_6_document_cannot_use_date_field(self) -> None:
        doc = {
            "version": "1.6", "initial_screen_id": "s1",
            "screens": [{"id": "s1", "title": "S1", "state": {"d": {"type": "string", "value": ""}},
                         "body": {"type": "date_field", "id": "df1", "label": "日付", "state_ref": "d"}}],
        }
        result = validate_forge_document(doc)
        self.assertFalse(result.valid)
        self.assertTrue(any(e.rule == "widget_not_allowed_in_version" for e in result.errors))

    def test_v1_6_document_cannot_use_tab_view(self) -> None:
        doc = {
            "version": "1.6", "initial_screen_id": "s1",
            "screens": [{"id": "s1", "title": "S1", "state": {},
                         "body": {"type": "tab_view", "id": "tv1", "tab_titles": ["A"],
                                  "children": [{"type": "text", "id": "t1", "value": "x"}]}}],
        }
        result = validate_forge_document(doc)
        self.assertFalse(result.valid)
        self.assertTrue(any(e.rule == "widget_not_allowed_in_version" for e in result.errors))

    def test_v1_7_document_with_only_v1_6_features_still_passes(self) -> None:
        doc = _v17_doc(
            {"type": "choice_field", "id": "cf1", "label": "カテゴリ", "state_ref": "c", "options": ["食費"]},
            state={"c": {"type": "string", "value": ""}},
        )
        result = validate_forge_document(doc)
        self.assertTrue(result.valid, msg=result.to_dict())


class TestDateField(unittest.TestCase):
    """`date_field` Widgetの検証。"""

    def test_minimal_date_field_passes(self) -> None:
        doc = _v17_doc(
            {"type": "date_field", "id": "df1", "label": "日付", "state_ref": "d"},
            state={"d": {"type": "string", "value": ""}},
        )
        result = validate_forge_document(doc)
        self.assertTrue(result.valid, msg=result.to_dict())

    def test_date_field_with_placeholder_passes(self) -> None:
        doc = _v17_doc(
            {"type": "date_field", "id": "df1", "label": "日付", "state_ref": "d", "placeholder": "選択してください"},
            state={"d": {"type": "string", "value": ""}},
        )
        result = validate_forge_document(doc)
        self.assertTrue(result.valid, msg=result.to_dict())

    def test_missing_label_is_rejected(self) -> None:
        doc = _v17_doc(
            {"type": "date_field", "id": "df1", "state_ref": "d"},
            state={"d": {"type": "string", "value": ""}},
        )
        result = validate_forge_document(doc)
        self.assertFalse(result.valid)

    def test_missing_state_ref_is_rejected(self) -> None:
        doc = _v17_doc({"type": "date_field", "id": "df1", "label": "日付"})
        result = validate_forge_document(doc)
        self.assertFalse(result.valid)

    def test_state_ref_must_point_to_string_state(self) -> None:
        doc = _v17_doc(
            {"type": "date_field", "id": "df1", "label": "日付", "state_ref": "d"},
            state={"d": {"type": "boolean", "value": False}},
        )
        result = validate_forge_document(doc)
        self.assertFalse(result.valid)
        self.assertTrue(any(e.rule == "state_reference_type_mismatch" for e in result.errors))

    def test_date_field_counts_as_form_input(self) -> None:
        doc = _v17_doc(
            {"type": "form", "id": "form1", "submit_label": "送信", "submit_action": {"type": "go_back"},
             "children": [{"type": "date_field", "id": "df1", "label": "日付", "state_ref": "d"}]},
            state={"d": {"type": "string", "value": ""}},
        )
        result = validate_forge_document(doc)
        self.assertTrue(result.valid, msg=result.to_dict())
        self.assertFalse(any(w.rule == "form_without_input" for w in result.warnings))


class TestTabView(unittest.TestCase):
    """`tab_view` Widgetの検証。"""

    def _tab(self, tab_id: str, label: str) -> dict:
        return {"type": "column", "id": tab_id, "children": [{"type": "text", "id": f"{tab_id}_t", "value": label}]}

    def test_minimal_tab_view_passes(self) -> None:
        doc = _v17_doc({
            "type": "tab_view", "id": "tv1",
            "tab_titles": ["追加", "一覧"],
            "children": [self._tab("tab1", "追加タブ"), self._tab("tab2", "一覧タブ")],
        })
        result = validate_forge_document(doc)
        self.assertTrue(result.valid, msg=result.to_dict())

    def test_single_tab_passes(self) -> None:
        doc = _v17_doc({
            "type": "tab_view", "id": "tv1", "tab_titles": ["唯一"], "children": [self._tab("tab1", "x")],
        })
        result = validate_forge_document(doc)
        self.assertTrue(result.valid, msg=result.to_dict())

    def test_titles_and_children_length_mismatch_is_rejected(self) -> None:
        doc = _v17_doc({
            "type": "tab_view", "id": "tv1",
            "tab_titles": ["追加", "一覧", "編集"],
            "children": [self._tab("tab1", "x"), self._tab("tab2", "y")],
        })
        result = validate_forge_document(doc)
        self.assertFalse(result.valid)
        self.assertTrue(any(e.rule == "array_length_mismatch" for e in result.errors))

    def test_empty_tab_titles_is_rejected(self) -> None:
        doc = _v17_doc({"type": "tab_view", "id": "tv1", "tab_titles": [], "children": []})
        result = validate_forge_document(doc)
        self.assertFalse(result.valid)

    def test_more_than_six_tabs_is_rejected(self) -> None:
        titles = [f"タブ{i}" for i in range(7)]
        children = [self._tab(f"tab{i}", f"x{i}") for i in range(7)]
        doc = _v17_doc({"type": "tab_view", "id": "tv1", "tab_titles": titles, "children": children})
        result = validate_forge_document(doc)
        self.assertFalse(result.valid)

    def test_invalid_child_widget_inside_a_tab_is_detected(self) -> None:
        """tab_view.childrenの中身も、column/row/card/formと同じく
        再帰的にWidget Schema検証されることを確認する(不正な子Widgetを
        検出できる)。"""
        doc = _v17_doc({
            "type": "tab_view", "id": "tv1", "tab_titles": ["A"],
            "children": [{"type": "column", "id": "tab1", "children": [{"type": "text_field", "id": "tf1"}]}],
        })
        result = validate_forge_document(doc)
        self.assertFalse(result.valid)
        self.assertTrue(any(e.rule == "required" for e in result.errors))

    def test_tab_view_with_form_inside_passes_and_is_reachable_for_form_ref(self) -> None:
        """tab_view内のformが、submit_form(form_ref経由)から正しく
        解決できることを確認する(CONTAINER_WIDGET_TYPESへの追加で
        _walk_widgetsが再帰することの回帰テスト)。"""
        doc = _v17_doc({
            "type": "tab_view", "id": "tv1", "tab_titles": ["追加"],
            "children": [{
                "type": "column", "id": "tab1",
                "children": [{
                    "type": "form", "id": "form1", "submit_label": "保存",
                    "submit_action": {"type": "go_back"},
                    "children": [{"type": "text_field", "id": "tf1", "state_ref": "name"}],
                }],
            }],
        }, state={"name": {"type": "string", "value": ""}})
        result = validate_forge_document(doc)
        self.assertTrue(result.valid, msg=result.to_dict())

    def test_widget_count_inside_tabs_counts_toward_max_widgets_per_screen(self) -> None:
        """tab_view内のWidgetも、既存のMAX_WIDGETS_PER_SCREENの
        カウント対象になることを確認する(_walk_widgets経由の再帰、
        Runtime Safety層の回帰テスト)。columnの上限(60)を超えないよう
        4タブに分散させつつ、合計はMAX_WIDGETS_PER_SCREEN(200)を
        超える件数にする。"""
        def _column_with(n: int, prefix: str) -> dict:
            return {
                "type": "column", "id": f"col_{prefix}",
                "children": [{"type": "text", "id": f"{prefix}_t{i}", "value": "x"} for i in range(n)],
            }

        doc = _v17_doc({
            "type": "tab_view", "id": "tv1", "tab_titles": ["A", "B", "C", "D"],
            "children": [_column_with(55, p) for p in ("a", "b", "c", "d")],
        })
        result = validate_forge_document(doc)
        self.assertFalse(result.valid)
        self.assertTrue(any(e.rule == "max_widgets_per_screen" for e in result.errors))


class TestV17DoesNotAddNewActionOrStateTypes(unittest.TestCase):
    def test_v1_7_allows_exactly_the_same_action_types_as_v1_6(self) -> None:
        from app.ai.validators.schema_validator import ACTION_TYPES_BY_VERSION

        self.assertEqual(ACTION_TYPES_BY_VERSION["1.7"], ACTION_TYPES_BY_VERSION["1.6"])

    def test_v1_7_allows_exactly_the_same_state_types_as_v1_6(self) -> None:
        from app.ai.validators.schema_validator import STATE_TYPES_BY_VERSION

        self.assertEqual(STATE_TYPES_BY_VERSION["1.7"], STATE_TYPES_BY_VERSION["1.6"])


if __name__ == "__main__":
    unittest.main()
