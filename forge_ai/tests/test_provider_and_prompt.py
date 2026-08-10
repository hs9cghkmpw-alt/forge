"""mock_provider.py と prompt_builder.py のテスト。"""

from __future__ import annotations

import unittest

from forge_ai.prompt.prompt_builder import Prompt, PromptBuilder
from forge_ai.provider.mock_provider import MockProvider
from forge_ai.provider.provider_interface import AIProvider, ProviderResponse


class TestPromptBuilder(unittest.TestCase):
    def setUp(self) -> None:
        self.builder = PromptBuilder()

    def test_prompt_is_structured_not_a_single_string(self) -> None:
        """指示書7章「文字列連結は禁止」の回帰テスト: Promptはsystem/instruction/
        contextに分離されたフィールドを持ち、1本の連結済み文字列ではないことを
        確認する。"""
        prompt = self.builder.build_meaning_prompt(user_text="test", domain_name="shopping")
        self.assertIsInstance(prompt, Prompt)
        self.assertIsInstance(prompt.system, str)
        self.assertIsInstance(prompt.instruction, str)
        self.assertIsInstance(prompt.context, dict)
        # instructionとsystemは別個のフィールドであり、userの生テキストを
        # 含んで連結されていない(userテキストはcontext側にのみ存在する)。
        self.assertNotIn("test", prompt.system)
        self.assertNotIn("test", prompt.instruction)
        self.assertEqual(prompt.context["user_text"], "test")

    def test_all_five_stage_builders_exist_and_return_prompt(self) -> None:
        meaning = self.builder.build_meaning_prompt(user_text="x", domain_name="shopping")
        intent = self.builder.build_intent_prompt(meaning_summary={}, domain_name="shopping")
        planning = self.builder.build_planning_prompt(intent_summary={})
        compile_p = self.builder.build_compile_prompt(plan_summary={})
        repair = self.builder.build_repair_prompt(ir_summary={}, issues=())
        for p in (meaning, intent, planning, compile_p, repair):
            self.assertIsInstance(p, Prompt)

    def test_prompt_stage_field_matches_builder_method(self) -> None:
        self.assertEqual(self.builder.build_meaning_prompt(user_text="x", domain_name="d").stage, "meaning")
        self.assertEqual(self.builder.build_intent_prompt(meaning_summary={}, domain_name="d").stage, "intent")
        self.assertEqual(self.builder.build_planning_prompt(intent_summary={}).stage, "planning")
        self.assertEqual(self.builder.build_compile_prompt(plan_summary={}).stage, "compile")
        self.assertEqual(self.builder.build_repair_prompt(ir_summary={}, issues=()).stage, "repair")


class TestMockProvider(unittest.TestCase):
    def setUp(self) -> None:
        self.provider = MockProvider()
        self.builder = PromptBuilder()

    def test_satisfies_ai_provider_protocol(self) -> None:
        self.assertIsInstance(self.provider, AIProvider)

    def test_complete_returns_provider_response(self) -> None:
        prompt = self.builder.build_meaning_prompt(user_text="add item", domain_name="shopping")
        response = self.provider.complete(prompt)
        self.assertIsInstance(response, ProviderResponse)

    def test_meaning_stage_extracts_whitespace_separated_tokens(self) -> None:
        prompt = self.builder.build_meaning_prompt(user_text="add item track price", domain_name="shopping")
        response = self.provider.complete(prompt)
        self.assertIn("add", response.structured["mentioned_concepts"])
        self.assertIn("item", response.structured["mentioned_concepts"])

    def test_meaning_stage_handles_empty_text_without_crashing(self) -> None:
        prompt = self.builder.build_meaning_prompt(user_text="", domain_name="shopping")
        response = self.provider.complete(prompt)
        self.assertEqual(response.structured["mentioned_concepts"], ())

    def test_intent_stage_produces_goal_and_actions(self) -> None:
        prompt = self.builder.build_intent_prompt(
            meaning_summary={"mentioned_concepts": ["item"], "mentioned_actions": ["add"]},
            domain_name="shopping",
        )
        response = self.provider.complete(prompt)
        self.assertIn("goal", response.structured)
        self.assertIn("required_actions", response.structured)

    def test_planning_stage_produces_at_least_one_screen(self) -> None:
        prompt = self.builder.build_planning_prompt(
            intent_summary={"goal": "manage items", "required_concepts": ["item"]}
        )
        response = self.provider.complete(prompt)
        self.assertGreaterEqual(len(response.structured["screens"]), 1)

    def test_unknown_stage_does_not_crash(self) -> None:
        bad_prompt = Prompt(stage="not_a_real_stage", system="x", instruction="y", context={})
        response = self.provider.complete(bad_prompt)
        self.assertIsInstance(response, ProviderResponse)

    def test_provider_never_imports_or_calls_real_llm(self) -> None:
        """MockProviderのソースに実LLM APIへの言及が無いことを確認する
        (静的な文字列チェック。禁止事項8章の回帰テスト)。"""
        import inspect

        source = inspect.getsource(MockProvider)
        forbidden = ["openai", "anthropic", "claude", "gemini", "ollama", "requests.post", "httpx"]
        lowered = source.lower()
        for term in forbidden:
            self.assertNotIn(term, lowered, f"MockProviderに'{term}'への言及が見つかりました")


if __name__ == "__main__":
    unittest.main()
