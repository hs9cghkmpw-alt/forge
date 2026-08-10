"""Language v1.2 拡張(Runtime契約)のテスト(FORGE-MILESTONE-003)。

number State型、5つの新規Action(set_state/toggle_state/reset_state/
submit_form/composite)、text_field/checkboxのvalidationプロパティ、
composite再帰深度制限を検証する。v1.0/v1.1との後方互換性は
test_schema_validator.py 等の既存135件が(無改変のまま)引き続き担保する。

実行方法:
    cd backend
    python -m unittest tests.test_schema_validator_v1_2 -v
"""

from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.ai.validators.schema_validator import validate_forge_document  # noqa: E402


def _v12_doc(body: dict, state: dict | None = None, extra_screens: list[dict] | None = None) -> dict:
    screens = [{"id": "s1", "title": "S1", "state": state or {}, "body": body}]
    if extra_screens:
        screens.extend(extra_screens)
    return {"version": "1.2", "initial_screen_id": "s1", "screens": screens}


class TestVersionGatingV12(unittest.TestCase):
    def test_v1_1_document_cannot_use_toggle_state_action(self):
        doc = {
            "version": "1.1",
            "initial_screen_id": "s1",
            "screens": [{
                "id": "s1", "title": "S1", "state": {"flag": {"type": "boolean", "value": False}},
                "body": {"type": "button", "id": "b1", "label": "X",
                         "action": {"type": "toggle_state", "state_ref": "flag"}},
            }],
        }
        result = validate_forge_document(doc)
        self.assertFalse(result.valid)
        self.assertTrue(any(e.rule == "action_not_allowed_in_version" for e in result.errors))

    def test_v1_1_document_cannot_use_number_state(self):
        doc = {
            "version": "1.1",
            "initial_screen_id": "s1",
            "screens": [{"id": "s1", "title": "S1", "state": {"n": {"type": "number", "value": 1}},
                         "body": {"type": "text", "id": "t1", "value": "x"}}],
        }
        result = validate_forge_document(doc)
        self.assertFalse(result.valid)
        self.assertTrue(any(e.rule == "state_type_not_allowed_in_version" for e in result.errors))

    def test_v1_2_document_with_only_v1_0_actions_still_passes(self):
        """後方互換性の核心: v1.2文書でも、古いAction(set_value/navigate等)だけを
        使う分には引き続き合格しなければならない。"""
        doc = _v12_doc({
            "type": "button", "id": "b1", "label": "X",
            "action": {"type": "set_value", "state_ref": "note", "value": "hi"},
        }, state={"note": {"type": "string", "value": ""}})
        result = validate_forge_document(doc)
        self.assertTrue(result.valid, msg=result.to_dict())

    def test_v1_0_documents_still_all_pass_after_v1_2_rewrite(self):
        doc = {
            "version": "1.0",
            "initial_screen_id": "s1",
            "screens": [{"id": "s1", "title": "S1", "body": {"type": "text", "id": "t1", "value": "hello"}}],
        }
        result = validate_forge_document(doc)
        self.assertTrue(result.valid, msg=result.to_dict())


class TestNumberState(unittest.TestCase):
    def test_valid_number_state(self):
        doc = _v12_doc({"type": "text", "id": "t1", "value": "x"}, state={"age": {"type": "number", "value": 30}})
        self.assertTrue(validate_forge_document(doc).valid)

    def test_number_state_accepts_float(self):
        doc = _v12_doc({"type": "text", "id": "t1", "value": "x"}, state={"price": {"type": "number", "value": 19.99}})
        self.assertTrue(validate_forge_document(doc).valid)

    def test_number_state_rejects_string(self):
        doc = _v12_doc({"type": "text", "id": "t1", "value": "x"}, state={"age": {"type": "number", "value": "30"}})
        self.assertFalse(validate_forge_document(doc).valid)

    def test_number_state_rejects_boolean(self):
        """PythonのboolはintのサブクラスなのでValidatorが誤ってTrueを数値として
        受理しないことを確認する回帰テスト。"""
        doc = _v12_doc({"type": "text", "id": "t1", "value": "x"}, state={"flag": {"type": "number", "value": True}})
        self.assertFalse(validate_forge_document(doc).valid)


class TestSetStateAction(unittest.TestCase):
    def test_set_state_equivalent_to_set_value(self):
        doc = _v12_doc({
            "type": "button", "id": "b1", "label": "X",
            "action": {"type": "set_state", "state_ref": "note", "value": "hi"},
        }, state={"note": {"type": "string", "value": ""}})
        self.assertTrue(validate_forge_document(doc).valid, msg=validate_forge_document(doc).to_dict())

    def test_set_state_missing_value(self):
        doc = _v12_doc({
            "type": "button", "id": "b1", "label": "X",
            "action": {"type": "set_state", "state_ref": "note"},
        }, state={"note": {"type": "string", "value": ""}})
        self.assertFalse(validate_forge_document(doc).valid)


class TestToggleStateAction(unittest.TestCase):
    def test_valid_toggle_state(self):
        doc = _v12_doc({
            "type": "button", "id": "b1", "label": "X",
            "action": {"type": "toggle_state", "state_ref": "flag"},
        }, state={"flag": {"type": "boolean", "value": False}})
        self.assertTrue(validate_forge_document(doc).valid, msg=validate_forge_document(doc).to_dict())

    def test_toggle_state_on_non_boolean_fails(self):
        doc = _v12_doc({
            "type": "button", "id": "b1", "label": "X",
            "action": {"type": "toggle_state", "state_ref": "note"},
        }, state={"note": {"type": "string", "value": ""}})
        result = validate_forge_document(doc)
        self.assertFalse(result.valid)
        self.assertTrue(any(e.rule == "state_reference_type_mismatch" for e in result.errors))

    def test_toggle_state_missing_state_ref_key_fails_schema(self):
        doc = _v12_doc({
            "type": "button", "id": "b1", "label": "X",
            "action": {"type": "toggle_state"},
        })
        self.assertFalse(validate_forge_document(doc).valid)


class TestResetStateAction(unittest.TestCase):
    def test_valid_reset_state(self):
        doc = _v12_doc({
            "type": "button", "id": "b1", "label": "X",
            "action": {"type": "reset_state", "state_ref": "note"},
        }, state={"note": {"type": "string", "value": "初期値"}})
        self.assertTrue(validate_forge_document(doc).valid, msg=validate_forge_document(doc).to_dict())

    def test_reset_state_unknown_ref_fails(self):
        doc = _v12_doc({
            "type": "button", "id": "b1", "label": "X",
            "action": {"type": "reset_state", "state_ref": "does_not_exist"},
        })
        result = validate_forge_document(doc)
        self.assertFalse(result.valid)
        self.assertTrue(any(e.rule == "state_reference_exists" for e in result.errors))


class TestSubmitFormAction(unittest.TestCase):
    def _form_doc(self, form_ref_in_action: str = "profile_form") -> dict:
        return _v12_doc({
            "type": "column", "id": "root", "children": [
                {
                    "type": "form", "id": "profile_form",
                    "children": [{"type": "text_field", "id": "name_field", "state_ref": "name"}],
                    "submit_label": "送信",
                    "submit_action": {
                        "type": "submit_form", "form_ref": form_ref_in_action,
                        "success_action": {"type": "navigate", "target_screen_id": "s2"},
                    },
                },
            ],
        }, state={"name": {"type": "string", "value": ""}}, extra_screens=[
            {"id": "s2", "title": "S2", "body": {"type": "text", "id": "t2", "value": "done"}},
        ])

    def test_valid_submit_form(self):
        result = validate_forge_document(self._form_doc())
        self.assertTrue(result.valid, msg=result.to_dict())

    def test_submit_form_unknown_form_ref_fails(self):
        result = validate_forge_document(self._form_doc(form_ref_in_action="nonexistent_form"))
        self.assertFalse(result.valid)
        self.assertTrue(any(e.rule == "form_reference_exists" for e in result.errors))

    def test_submit_form_success_action_target_must_exist(self):
        doc = _v12_doc({
            "type": "form", "id": "form1",
            "children": [{"type": "text_field", "id": "f1", "state_ref": "x"}],
            "submit_label": "OK",
            "submit_action": {
                "type": "submit_form", "form_ref": "form1",
                "success_action": {"type": "navigate", "target_screen_id": "nowhere"},
            },
        }, state={"x": {"type": "string", "value": ""}})
        result = validate_forge_document(doc)
        self.assertFalse(result.valid)
        self.assertTrue(any(e.rule == "navigation_target_exists" for e in result.errors))


class TestCompositeAction(unittest.TestCase):
    def test_valid_composite(self):
        doc = _v12_doc({
            "type": "button", "id": "b1", "label": "X",
            "action": {
                "type": "composite",
                "actions": [
                    {"type": "set_state", "state_ref": "submitted", "value": True},
                    {"type": "navigate", "target_screen_id": "s2"},
                ],
            },
        }, state={"submitted": {"type": "boolean", "value": False}}, extra_screens=[
            {"id": "s2", "title": "S2", "body": {"type": "text", "id": "t2", "value": "done"}},
        ])
        result = validate_forge_document(doc)
        self.assertTrue(result.valid, msg=result.to_dict())

    def test_composite_empty_actions_fails(self):
        doc = _v12_doc({
            "type": "button", "id": "b1", "label": "X",
            "action": {"type": "composite", "actions": []},
        })
        self.assertFalse(validate_forge_document(doc).valid)

    def test_composite_inner_action_error_propagates(self):
        doc = _v12_doc({
            "type": "button", "id": "b1", "label": "X",
            "action": {"type": "composite", "actions": [{"type": "toggle_state", "state_ref": "missing"}]},
        })
        result = validate_forge_document(doc)
        self.assertFalse(result.valid)
        self.assertTrue(any(e.rule == "state_reference_exists" for e in result.errors))

    def test_composite_depth_exactly_at_limit_passes(self):
        """MAX_COMPOSITE_DEPTH=3。composite→composite→composite→leaf、で
        ちょうど3段のネストは許可される。"""
        action = {"type": "go_back"}
        for _ in range(3):
            action = {"type": "composite", "actions": [action]}
        doc = _v12_doc({"type": "button", "id": "b1", "label": "X", "action": action})
        result = validate_forge_document(doc)
        self.assertTrue(result.valid, msg=result.to_dict())

    def test_composite_depth_one_over_limit_fails(self):
        action = {"type": "go_back"}
        for _ in range(4):
            action = {"type": "composite", "actions": [action]}
        doc = _v12_doc({"type": "button", "id": "b1", "label": "X", "action": action})
        result = validate_forge_document(doc)
        self.assertFalse(result.valid)
        self.assertTrue(any(e.rule == "max_composite_depth" for e in result.errors))

    def test_composite_too_many_actions_fails(self):
        doc = _v12_doc({
            "type": "button", "id": "b1", "label": "X",
            "action": {"type": "composite", "actions": [{"type": "go_back"}] * 11},
        })
        self.assertFalse(validate_forge_document(doc).valid)


class TestValidationRules(unittest.TestCase):
    def test_valid_text_field_with_required_and_max_length(self):
        doc = _v12_doc({
            "type": "text_field", "id": "tf1", "state_ref": "name",
            "validation": {"rules": [
                {"type": "required", "message": "必須です"},
                {"type": "max_length", "value": 50, "message": "50文字以内です"},
            ]},
        }, state={"name": {"type": "string", "value": ""}})
        self.assertTrue(validate_forge_document(doc).valid, msg=validate_forge_document(doc).to_dict())

    def test_validation_rule_missing_message_fails(self):
        doc = _v12_doc({
            "type": "text_field", "id": "tf1", "state_ref": "name",
            "validation": {"rules": [{"type": "required"}]},
        }, state={"name": {"type": "string", "value": ""}})
        self.assertFalse(validate_forge_document(doc).valid)

    def test_min_length_without_numeric_value_fails(self):
        doc = _v12_doc({
            "type": "text_field", "id": "tf1", "state_ref": "name",
            "validation": {"rules": [{"type": "min_length", "message": "短すぎます"}]},
        }, state={"name": {"type": "string", "value": ""}})
        self.assertFalse(validate_forge_document(doc).valid)

    def test_pattern_with_invalid_regex_fails(self):
        doc = _v12_doc({
            "type": "text_field", "id": "tf1", "state_ref": "name",
            "validation": {"rules": [{"type": "pattern", "value": "(unclosed", "message": "形式が不正です"}]},
        }, state={"name": {"type": "string", "value": ""}})
        self.assertFalse(validate_forge_document(doc).valid)

    def test_valid_pattern_regex_passes(self):
        doc = _v12_doc({
            "type": "text_field", "id": "tf1", "state_ref": "email",
            "validation": {"rules": [{"type": "pattern", "value": r"^[^@]+@[^@]+\.[^@]+$", "message": "メール形式が不正です"}]},
        }, state={"email": {"type": "string", "value": ""}})
        self.assertTrue(validate_forge_document(doc).valid, msg=validate_forge_document(doc).to_dict())

    def test_checkbox_with_required_validation(self):
        doc = _v12_doc({
            "type": "checkbox", "id": "cb1", "label": "同意する", "state_ref": "agreed",
            "validation": {"rules": [{"type": "required", "message": "同意が必要です"}]},
        }, state={"agreed": {"type": "boolean", "value": False}})
        self.assertTrue(validate_forge_document(doc).valid, msg=validate_forge_document(doc).to_dict())

    def test_min_length_on_boolean_state_is_warning_not_error(self):
        """State型に適用できないValidationはブロッキングエラーにせず、
        警告として開発ログに残す(指示書5章の方針)。"""
        doc = _v12_doc({
            "type": "checkbox", "id": "cb1", "label": "X", "state_ref": "agreed",
            "validation": {"rules": [{"type": "min_length", "value": 3, "message": "短すぎます"}]},
        }, state={"agreed": {"type": "boolean", "value": False}})
        result = validate_forge_document(doc)
        self.assertTrue(result.valid, msg=result.to_dict())
        self.assertTrue(any(w.rule == "validation_rule_not_applicable" for w in result.warnings))


class TestNoBackNavigationLooksInsideCompositeAndSubmitForm(unittest.TestCase):
    """既存のno_back_navigation警告が、composite/submit_formの中に潜んだ
    navigate/go_backも正しく見つけ、誤検知しないことを確認する。"""

    def test_navigate_inside_composite_prevents_false_warning(self):
        doc = _v12_doc(
            {"type": "text", "id": "t1", "value": "home"},
            extra_screens=[{
                "id": "s2", "title": "S2",
                "body": {
                    "type": "button", "id": "b2", "label": "X",
                    "action": {"type": "composite", "actions": [
                        {"type": "set_state", "state_ref": "x", "value": "y"},
                        {"type": "go_back"},
                    ]},
                },
                "state": {"x": {"type": "string", "value": ""}},
            }],
        )
        result = validate_forge_document(doc)
        self.assertTrue(result.valid, msg=result.to_dict())
        self.assertFalse(any(w.rule == "no_back_navigation" for w in result.warnings))


if __name__ == "__main__":
    unittest.main()
