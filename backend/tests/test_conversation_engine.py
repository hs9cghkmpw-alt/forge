"""ConversationEngineのテスト(FORGE-PRODUCT-VISION-002、2026-08-11)。

`GeminiProvider`は実際に外部APIを呼ぶため、ここでは`complete_structured()`
のみを実装するFakeProviderを使う(`MockLLMAdapter`は名前ベースの
ヒューリスティックであり、ASK/BUILD分岐を狙って制御できないため、
このテストの目的には合わない——`GenerationOptionsDTO`の"mock"provider
とは無関係な、このテストファイル専用の道具)。
"""

from __future__ import annotations

import os
import sys
import unittest
from typing import Any

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from app.ai.runtime.conversation_engine import ConversationEngine  # noqa: E402
from app.ai.runtime.conversation_store import MAX_CONVERSATION_TURNS  # noqa: E402
from app.ai.runtime.conversation_types import (  # noqa: E402
    ConversationAction,
    ConversationSession,
    ConversationTurn,
)


class _FakeProvider:
    """毎回同じ辞書を返す、完全に決定的なテスト用Provider。"""

    def __init__(self, response: dict[str, Any]) -> None:
        self._response = response
        self.last_prompt: str | None = None

    def complete_structured(self, prompt: str, response_schema: dict[str, Any]) -> dict[str, Any]:
        self.last_prompt = prompt
        return self._response


def _session_with_user_text(*texts: str) -> ConversationSession:
    session = ConversationSession(session_id="s1")
    for i, text in enumerate(texts):
        role = "user" if i % 2 == 0 else "forge"
        session = session.with_turn(ConversationTurn(role=role, text=text))
    return session


class TestConversationEngineAsk(unittest.TestCase):
    def test_llm_asks_and_unknown_important_is_nonempty_yields_ask(self) -> None:
        provider = _FakeProvider({
            "problem": "買い物で何を買うか忘れる",
            "known": ["家で追加、店で消す"],
            "unknown_important": ["家族も使うか"],
            "safe_assumptions": ["削除操作は標準的なものでよい"],
            "confidence": 0.6,
            "next_action": "ask",
            "question": "家族も追加できた方がいい?",
            "build_brief": "",
        })
        session = _session_with_user_text("買い物行くと、いつも何買うか忘れるんだよね")
        result = ConversationEngine(provider).step(session)

        self.assertEqual(result.action, ConversationAction.ASK)
        self.assertEqual(result.question, "家族も追加できた方がいい?")
        self.assertIsNone(result.build_brief)
        self.assertEqual(result.need_model.unknown_important, ("家族も使うか",))

    def test_prompt_includes_full_conversation_history(self) -> None:
        provider = _FakeProvider({
            "problem": "p", "known": [], "unknown_important": ["x"], "safe_assumptions": [],
            "confidence": 0.5, "next_action": "ask", "question": "q?", "build_brief": "",
        })
        session = _session_with_user_text("買い物で忘れる", "店で見ながら消す感じ?", "そうそう")
        ConversationEngine(provider).step(session)

        assert provider.last_prompt is not None
        self.assertIn("買い物で忘れる", provider.last_prompt)
        self.assertIn("店で見ながら消す感じ?", provider.last_prompt)
        self.assertIn("そうそう", provider.last_prompt)

    def test_step_requires_the_last_turn_to_be_from_the_user(self) -> None:
        provider = _FakeProvider({
            "problem": "p", "known": [], "unknown_important": [], "safe_assumptions": [],
            "confidence": 0.9, "next_action": "build", "question": "", "build_brief": "b",
        })
        session = _session_with_user_text("買い物で忘れる", "店で見ながら消す感じ?")
        with self.assertRaises(ValueError):
            ConversationEngine(provider).step(session)


class TestConversationEngineBuild(unittest.TestCase):
    def test_llm_says_build_and_unknown_important_is_empty_yields_build(self) -> None:
        provider = _FakeProvider({
            "problem": "買い物で何を買うか忘れる",
            "known": ["家で追加、店で消す", "自分だけで使う"],
            "unknown_important": [],
            "safe_assumptions": ["削除操作は標準的なものでよい"],
            "confidence": 0.9,
            "next_action": "build",
            "question": "",
            "build_brief": "買い物リストを作りたい。家で思いついた時に追加して、店で見ながら消していく。自分だけで使う。",
        })
        session = _session_with_user_text("買い物行くと、いつも何買うか忘れるんだよね", "うん", "いや、自分だけでいいかな")
        result = ConversationEngine(provider).step(session)

        self.assertEqual(result.action, ConversationAction.BUILD)
        self.assertIsNone(result.question)
        self.assertIn("買い物リスト", result.build_brief or "")

    def test_unknown_important_empty_forces_build_even_if_llm_says_ask(self) -> None:
        """design doc B.3: LLMの自己申告(next_action)を鵜呑みにしない、
        決定的な上書きルールの回帰テスト。"""
        provider = _FakeProvider({
            "problem": "p", "known": ["k"], "unknown_important": [], "safe_assumptions": [],
            "confidence": 0.3, "next_action": "ask", "question": "まだ何か聞きたい?",
            "build_brief": "買い物リストを作る",
        })
        session = _session_with_user_text("買い物で忘れる")
        result = ConversationEngine(provider).step(session)
        self.assertEqual(result.action, ConversationAction.BUILD)

    def test_turn_limit_forces_build_even_if_unknown_important_is_nonempty(self) -> None:
        """design doc B.3: 無限に聞き続けない、というターン数上限の回帰テスト。"""
        texts = []
        for i in range(MAX_CONVERSATION_TURNS):
            texts.append(f"ユーザー発話{i}")
            if i < MAX_CONVERSATION_TURNS - 1:
                texts.append(f"Forge質問{i}")
        session = _session_with_user_text(*texts)
        user_turns = [t for t in session.turns if t.role == "user"]
        self.assertEqual(len(user_turns), MAX_CONVERSATION_TURNS)

        provider = _FakeProvider({
            "problem": "p", "known": [], "unknown_important": ["まだ不明な点がある"], "safe_assumptions": [],
            "confidence": 0.4, "next_action": "ask", "question": "もう1つ聞きたい",
            "build_brief": "それでも作れるものを作る",
        })
        result = ConversationEngine(provider).step(session)
        self.assertEqual(result.action, ConversationAction.BUILD)

    def test_empty_build_brief_falls_back_to_concatenated_user_turns(self) -> None:
        provider = _FakeProvider({
            "problem": "p", "known": [], "unknown_important": [], "safe_assumptions": [],
            "confidence": 0.9, "next_action": "build", "question": "", "build_brief": "",
        })
        session = _session_with_user_text("買い物で忘れる")
        result = ConversationEngine(provider).step(session)
        self.assertEqual(result.action, ConversationAction.BUILD)
        self.assertIn("買い物で忘れる", result.build_brief or "")

    def test_empty_question_on_ask_falls_back_to_build(self) -> None:
        provider = _FakeProvider({
            "problem": "p", "known": [], "unknown_important": ["まだ不明"], "safe_assumptions": [],
            "confidence": 0.5, "next_action": "ask", "question": "", "build_brief": "",
        })
        session = _session_with_user_text("買い物で忘れる")
        result = ConversationEngine(provider).step(session)
        self.assertEqual(result.action, ConversationAction.BUILD)
        self.assertIn("買い物で忘れる", result.build_brief or "")


class TestConversationEngineUpdate(unittest.TestCase):
    """FORGE-PRODUCT-VISION-002続き(2026-08-11新設)。`has_existing_tool`
    引数によるASK/BUILD/UPDATE分岐の回帰テスト。"""

    def test_llm_says_update_and_has_existing_tool_yields_update(self) -> None:
        provider = _FakeProvider({
            "problem": "p", "known": [], "unknown_important": [], "safe_assumptions": [],
            "confidence": 0.9, "next_action": "update", "question": "",
            "build_brief": "よく買うものを上に置きたい",
        })
        session = _session_with_user_text("よく買うものを上に置きたい")
        result = ConversationEngine(provider).step(session, has_existing_tool=True)

        self.assertEqual(result.action, ConversationAction.UPDATE)
        self.assertEqual(result.build_brief, "よく買うものを上に置きたい")

    def test_llm_says_update_but_no_existing_tool_falls_back_to_build(self) -> None:
        """design doc B.3と同じ思想の決定的な上書きルール: 更新対象が
        無いのにupdateを鵜呑みにしない(has_existing_tool=Falseが既定)。"""
        provider = _FakeProvider({
            "problem": "p", "known": [], "unknown_important": [], "safe_assumptions": [],
            "confidence": 0.9, "next_action": "update", "question": "",
            "build_brief": "よく買うものを上に置きたい",
        })
        session = _session_with_user_text("よく買うものを上に置きたい")
        result = ConversationEngine(provider).step(session, has_existing_tool=False)

        self.assertEqual(result.action, ConversationAction.BUILD)

    def test_prompt_mentions_existing_tool_state_when_true(self) -> None:
        provider = _FakeProvider({
            "problem": "p", "known": [], "unknown_important": [], "safe_assumptions": [],
            "confidence": 0.9, "next_action": "update", "question": "", "build_brief": "b",
        })
        session = _session_with_user_text("変更したい")
        ConversationEngine(provider).step(session, has_existing_tool=True)
        assert provider.last_prompt is not None
        self.assertIn("既に生成済みのツールを使っています", provider.last_prompt)

    def test_prompt_mentions_no_tool_state_when_false(self) -> None:
        provider = _FakeProvider({
            "problem": "p", "known": ["k"], "unknown_important": ["x"], "safe_assumptions": [],
            "confidence": 0.3, "next_action": "ask", "question": "q?", "build_brief": "",
        })
        session = _session_with_user_text("困ってる")
        ConversationEngine(provider).step(session, has_existing_tool=False)
        assert provider.last_prompt is not None
        self.assertIn("まだツールは生成されていません", provider.last_prompt)


if __name__ == "__main__":
    unittest.main()
