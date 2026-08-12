"""MockLLMAdapterのテスト(FORGE-PRODUCT-VISION-002続き、2026-08-11新設)。

これまでこのクラスの`_synthesize_field()`(フィールド型ごとの値合成)を
直接検証する専用テストが無かった。`ConversationEngine`が"number"型
フィールド(`confidence`)を持つschemaで`mock` Providerを実機(uvicorn+
TestClient)経由で呼んだ際に発見した実バグ(`"number"`型の分岐が無く、
文字列"mock_result"が返り、呼び出し側の`float(...)`変換で
`ValueError`になっていた)の回帰テスト。
"""

from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from app.ai.foundation.providers import MockLLMAdapter  # noqa: E402


class TestMockLLMAdapterFieldSynthesis(unittest.TestCase):
    def setUp(self) -> None:
        self.adapter = MockLLMAdapter()

    def test_number_type_returns_a_float_not_a_string(self) -> None:
        schema = {"type": "object", "properties": {"confidence": {"type": "number"}}}
        result = self.adapter.complete_structured("何か困ってる", schema)
        self.assertIsInstance(result["confidence"], float)

    def test_integer_type_still_returns_zero(self) -> None:
        """既存の挙動("integer"→0)が変わっていないことの回帰テスト。"""
        schema = {"type": "object", "properties": {"count": {"type": "integer"}}}
        result = self.adapter.complete_structured("何か", schema)
        self.assertEqual(result["count"], 0)

    def test_array_type_still_returns_a_list(self) -> None:
        schema = {"type": "object", "properties": {"tags": {"type": "array", "items": {"type": "string"}}}}
        result = self.adapter.complete_structured("買い物 追加する", schema)
        self.assertIsInstance(result["tags"], list)

    def test_number_field_can_be_used_in_float_conversion_without_crashing(self) -> None:
        """`ConversationEngine.step()`の`float(raw.get("confidence", 0.0)
        or 0.0)`と同じ変換をここでも直接確認する(実際のクラッシュ経路の
        再現)。"""
        schema = {"type": "object", "properties": {"confidence": {"type": "number"}}}
        result = self.adapter.complete_structured("x", schema)
        float(result["confidence"] or 0.0)  # 例外を出さないことを確認する


if __name__ == "__main__":
    unittest.main()
