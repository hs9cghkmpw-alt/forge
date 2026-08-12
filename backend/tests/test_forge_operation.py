"""ForgeOperationEngine(Forming Operation/UPDATE)のテスト
(FORGE-PRODUCT-VISION-002 TD40対応、2026-08-11)。

`GeminiProvider`は実際に外部APIを呼ぶため、ここでは`complete_structured()`
のみを実装するFakeProviderを使う(`test_conversation_engine.py`と同じ
方針)。
"""

from __future__ import annotations

import os
import sys
import unittest
from typing import Any

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from app.ai.runtime.forge_operation import MAX_UPDATE_ATTEMPTS, ForgeOperationEngine  # noqa: E402

_VALID_DOC = {
    "version": "1.0",
    "initial_screen_id": "s1",
    "app": {"title": "買い物メモ"},
    "screens": [{
        "id": "s1", "title": "買い物メモ",
        "state": {
            "items": {"type": "checklist", "value": []},
            "new_item_text": {"type": "string", "value": ""},
        },
        "body": {
            "type": "column", "id": "root",
            "children": [
                {"type": "checklist", "id": "list_view", "state_ref": "items", "empty_state_text": "まだありません"},
                {"type": "row", "id": "add_row", "children": [
                    {"type": "text_field", "id": "add_field", "state_ref": "new_item_text", "placeholder": "追加"},
                    {"type": "button", "id": "add_button", "label": "追加",
                     "action": {"type": "add_item", "target_state_ref": "items", "source_state_ref": "new_item_text"}},
                ]},
            ],
        },
    }],
}


class _ScriptedProvider:
    """呼び出しごとに、あらかじめ用意した応答を順に返すFakeProvider。"""

    def __init__(self, responses: list[Any]) -> None:
        self._responses = list(responses)
        self.prompts: list[str] = []

    def complete_structured(self, prompt: str, response_schema: dict[str, Any]) -> Any:
        self.prompts.append(prompt)
        self.last_schema = response_schema
        return self._responses.pop(0)


class TestForgeOperationEngineSuccess(unittest.TestCase):
    def test_valid_first_response_succeeds_on_first_attempt(self) -> None:
        updated = {**_VALID_DOC, "app": {"title": "買い物メモ(更新版)"}}
        provider = _ScriptedProvider([updated])
        result = ForgeOperationEngine(provider).apply_update(_VALID_DOC, "タイトルを変えたい")

        self.assertTrue(result.success)
        self.assertEqual(result.attempts, 1)
        assert result.forge_document is not None
        self.assertEqual(result.forge_document["app"]["title"], "買い物メモ(更新版)")
        assert result.validation is not None
        self.assertTrue(result.validation.valid)

    def test_prompt_includes_current_document_and_change_request(self) -> None:
        provider = _ScriptedProvider([_VALID_DOC])
        ForgeOperationEngine(provider).apply_update(_VALID_DOC, "予算も管理したい")
        self.assertIn("予算も管理したい", provider.prompts[0])
        self.assertIn("買い物メモ", provider.prompts[0])

    def test_calls_complete_structured_with_empty_schema_for_freeform_output(self) -> None:
        """TD40: responseSchemaを送らずフリーフォームJSONとして生成させる
        (再帰的なWidget木をresponseSchemaで強制すると内容が失われる、
        実機検証で確認した問題への対処)ことの回帰テスト。"""
        provider = _ScriptedProvider([_VALID_DOC])
        ForgeOperationEngine(provider).apply_update(_VALID_DOC, "x")
        self.assertEqual(provider.last_schema, {})


class TestForgeOperationEngineRepair(unittest.TestCase):
    def test_invalid_first_response_retries_once_and_succeeds(self) -> None:
        invalid = {"version": "1.0"}  # screens等が欠落、Validator不合格のはず
        provider = _ScriptedProvider([invalid, _VALID_DOC])
        result = ForgeOperationEngine(provider).apply_update(_VALID_DOC, "x")

        self.assertTrue(result.success)
        self.assertEqual(result.attempts, 2)
        # 2回目のプロンプトには、1回目の失敗理由が含まれているはず。
        self.assertIn("直前の出力の問題点", provider.prompts[1])

    def test_non_dict_response_is_treated_as_invalid_and_retried(self) -> None:
        provider = _ScriptedProvider(["not a dict", _VALID_DOC])
        result = ForgeOperationEngine(provider).apply_update(_VALID_DOC, "x")
        self.assertTrue(result.success)
        self.assertEqual(result.attempts, 2)

    def test_still_invalid_after_max_attempts_returns_failure(self) -> None:
        invalid = {"version": "1.0"}
        provider = _ScriptedProvider([invalid] * MAX_UPDATE_ATTEMPTS)
        result = ForgeOperationEngine(provider).apply_update(_VALID_DOC, "x")

        self.assertFalse(result.success)
        self.assertEqual(result.attempts, MAX_UPDATE_ATTEMPTS)
        self.assertIsNotNone(result.error_message)
        self.assertEqual(len(provider.prompts), MAX_UPDATE_ATTEMPTS)

    def test_provider_exception_yields_failure_without_crashing(self) -> None:
        class _RaisingProvider:
            def complete_structured(self, prompt: str, response_schema: dict[str, Any]) -> Any:
                raise RuntimeError("network down")

        result = ForgeOperationEngine(_RaisingProvider()).apply_update(_VALID_DOC, "x")
        self.assertFalse(result.success)
        assert result.error_message is not None
        self.assertIn("network down", result.error_message)


if __name__ == "__main__":
    unittest.main()
