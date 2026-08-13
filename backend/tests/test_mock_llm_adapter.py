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

    def test_boolean_type_returns_a_bool_not_a_truthy_string(self) -> None:
        """FORGE-CONVERSATION-READY-001(2026-08-12)で発見した実バグの
        回帰テスト。"boolean"の分岐が無く文字列"mock_result"へ落ちて
        いたため、`bool(...)`変換が**常にTrue**になっていた。"""
        schema = {"type": "object", "properties": {"external_effect": {"type": "boolean"}}}
        result = self.adapter.complete_structured("買い物で忘れる", schema)
        self.assertIsInstance(result["external_effect"], bool)
        self.assertFalse(result["external_effect"])

    def test_boolean_risk_flags_do_not_force_every_mock_conversation_to_confirm(self) -> None:
        """上のバグが実際に引き起こしていた症状の再現テスト:
        `ConversationEngine`のrisk flagが常に立ち、mock providerでの
        会話が毎回CONFIRMへ倒れていた。"""
        schema = {
            "type": "object",
            "properties": {
                "external_effect": {"type": "boolean"},
                "destructive": {"type": "boolean"},
            },
        }
        result = self.adapter.complete_structured("買い物で何を買うか忘れる", schema)
        self.assertFalse(bool(result["external_effect"]) or bool(result["destructive"]))

    def test_number_field_can_be_used_in_float_conversion_without_crashing(self) -> None:
        """`ConversationEngine.step()`の`float(raw.get("confidence", 0.0)
        or 0.0)`と同じ変換をここでも直接確認する(実際のクラッシュ経路の
        再現)。"""
        schema = {"type": "object", "properties": {"confidence": {"type": "number"}}}
        result = self.adapter.complete_structured("x", schema)
        float(result["confidence"] or 0.0)  # 例外を出さないことを確認する


class TestMockLLMAdapterRealism(unittest.TestCase):
    """FORGE-HANDOFF-LOCAL-AI-UX-004 §9/§35(2026-08-13)。

    CEO実機確認: 生成されたToolのチェックリストに`mock_result` `plan`
    `title` `screens`が項目として並び、会話でも「mock resultがあると
    楽そう」と言われた。指示書は「Mockだから内部JSONっぽい画面が
    出てもいい、という考えは禁止」「MockでもUI Flow / Navigation /
    RuntimeをProductionと同じUX契約で検証できること」と明示している。

    Mockは実LLMのふりはしないが、**ユーザーの実際の発話から
    もっともらしい日本語を決定的に組み立てる**こと。乱数は使わない
    (同じ入力なら常に同じ出力)。
    """

    def setUp(self) -> None:
        self.adapter = MockLLMAdapter()

    def _conversation_prompt(self, utterance: str) -> str:
        return f"[SYSTEM]\nあなたはForgeです。\n\n[CONTEXT]\nユーザー: {utterance}\n"

    def test_no_internal_placeholder_leaks_into_any_string_field(self) -> None:
        """`mock_result`という内部の穴埋め文字列が、ユーザーへ見える
        フィールドへ出てはならない。"""
        schema = {
            "type": "object",
            "properties": {
                "problem": {"type": "string"},
                "build_brief": {"type": "string"},
                "question": {"type": "string"},
                "app_title": {"type": "string"},
                "entity_label": {"type": "string"},
                "example_items": {"type": "array", "items": {"type": "string"}},
            },
        }
        result = self.adapter.complete_structured(
            self._conversation_prompt("買い物で何買うか忘れちゃう"), schema
        )
        rendered = str(result)
        self.assertNotIn("mock_result", rendered)

    def test_problem_is_the_users_own_words(self) -> None:
        result = self.adapter.complete_structured(
            self._conversation_prompt("買い物で何買うか忘れちゃう"),
            {"type": "object", "properties": {"problem": {"type": "string"}}},
        )
        self.assertEqual(result["problem"], "買い物で何買うか忘れちゃう")

    def test_example_items_are_plausible_real_values(self) -> None:
        """初期データが「牛乳・卵・パン」のような実在しそうな値になる
        (以前は`plan` `title` `screens`という内部語が項目として並んで
        いた、実機で確認)。"""
        schema = {"type": "object", "properties": {"example_items": {"type": "array", "items": {"type": "string"}}}}
        result = self.adapter.complete_structured(
            self._conversation_prompt("買い物で何買うか忘れちゃう"), schema
        )
        self.assertEqual(result["example_items"], ["牛乳", "卵", "パン"])

    def test_example_items_match_the_topic_even_without_a_raw_utterance(self) -> None:
        """compile段のプロンプトには生の発話が含まれず、話題は
        `build_brief`由来のテキストにしか現れない。話題キーワードの照合は
        プロンプト全体に対して行う(実行して確認した実バグの回帰テスト:
        照合を発話だけに限ると、常に既定値へ落ちていた)。"""
        schema = {"type": "object", "properties": {"example_items": {"type": "array", "items": {"type": "string"}}}}
        compile_prompt = (
            "[SYSTEM]\n画面を組み立ててください。\n\n[CONTEXT]\n"
            "plan.title: 旅行の持ち物を記録・管理するための道具\n"
        )
        result = self.adapter.complete_structured(compile_prompt, schema)
        self.assertEqual(result["example_items"], ["充電器", "着替え", "歯ブラシ"])

    def test_app_title_is_a_short_name_not_a_description(self) -> None:
        """実機で「買い物で何買うかを記録・管理するための道具」が
        そのままアプリ名になっていた。App Storeに並ぶアプリの名前は
        説明文ではなく短い名詞句である。"""
        schema = {"type": "object", "properties": {"app_title": {"type": "string"}}}
        result = self.adapter.complete_structured(
            self._conversation_prompt("買い物で何買うか忘れちゃう"), schema
        )
        self.assertEqual(result["app_title"], "買い物リスト")

    def test_unknown_topic_still_avoids_a_description_length_title(self) -> None:
        """話題テーブルに無い場合でも、説明文の長さのものをアプリ名に
        してはならない。"""
        schema = {"type": "object", "properties": {"app_title": {"type": "string"}}}
        long_utterance = "毎週やっている集まりで誰が何を持ってくるかを決めて共有するのがいつも大変で困ってる"
        result = self.adapter.complete_structured(
            self._conversation_prompt(long_utterance), schema
        )
        self.assertLessEqual(len(result["app_title"]), 14)

    def test_output_is_deterministic(self) -> None:
        """同じ入力なら常に同じ出力(乱数を使わない)。テストが安定する
        ことと、Mock利用時のUXが再現可能であることの両方のため。"""
        schema = {
            "type": "object",
            "properties": {
                "build_brief": {"type": "string"},
                "example_items": {"type": "array", "items": {"type": "string"}},
            },
        }
        prompt = self._conversation_prompt("読んだ本を記録したい")
        self.assertEqual(
            self.adapter.complete_structured(prompt, schema),
            self.adapter.complete_structured(prompt, schema),
        )


if __name__ == "__main__":
    unittest.main()
