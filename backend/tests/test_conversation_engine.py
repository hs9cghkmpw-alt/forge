"""ConversationEngineのテスト(FORGE-PRODUCT-VISION-002、2026-08-11、
FORGE-CONVERSATION-READY-001で大幅拡張、2026-08-12)。

`GeminiProvider`は実際に外部APIを呼ぶため、ここでは`complete_structured()`
のみを実装するFakeProviderを使う(`MockLLMAdapter`は名前ベースの
ヒューリスティックであり、ASK/BUILD分岐を狙って制御できないため、
このテストの目的には合わない——`GenerationOptionsDTO`の"mock"provider
とは無関係な、このテストファイル専用の道具)。

**FORGE-CONVERSATION-READY-001での方針転換**: 以前このファイルには、

* `test_turn_limit_forces_build_even_if_unknown_important_is_nonempty`
* `test_empty_question_on_ask_falls_back_to_build`

という、「重要な未知が残っていてもBUILDする」ことを**正しい挙動として
固定していた**テストが2件あった。指示書1章はこれを明確に誤りとしたため
(「質問しすぎない」と「分からなくても作る」は別)、両テストは削除では
なく**期待値を反転**させ、同名の意図を引き継ぐ形で残している
(`TestTurnLimitNoLongerForcesBuild`・`TestEmptyQuestionNeverBecomesBuild`)。
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
    ConversationReadiness,
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


def _unknown(key: str, impact: str = "high", reason: str = "テスト用") -> dict[str, Any]:
    return {"key": key, "impact": impact, "reason": reason}


def _response(**overrides: Any) -> dict[str, Any]:
    """新schemaの既定値。テストは変えたいキーだけ上書きする。"""
    base: dict[str, Any] = {
        "problem": "p",
        "known": [],
        "unknowns": [],
        "assumptions": [],
        "confidence": 0.5,
        "next_action": "build",
        "question": "",
        "question_key": "",
        "build_brief": "何かを作る",
        "external_effect": False,
        "destructive": False,
    }
    base.update(overrides)
    return base


def _session_with_user_text(*texts: str) -> ConversationSession:
    session = ConversationSession(session_id="s1")
    for i, text in enumerate(texts):
        role = "user" if i % 2 == 0 else "forge"
        session = session.with_turn(ConversationTurn(role=role, text=text))
    return session


class TestConversationEngineAsk(unittest.TestCase):
    def test_llm_asks_and_unknown_important_is_nonempty_yields_ask(self) -> None:
        provider = _FakeProvider(_response(
            problem="買い物で何を買うか忘れる",
            known=["家で追加、店で消す"],
            unknowns=[_unknown("shared_usage", "high", "共有すると保存場所と権限が変わる")],
            assumptions=[{"key": "allow_delete", "value": "true", "reason": "標準的で元に戻せる操作のため"}],
            confidence=0.6, next_action="ask",
            question="家族も追加できた方がいい?", question_key="shared_usage", build_brief="",
        ))
        session = _session_with_user_text("買い物行くと、いつも何買うか忘れるんだよね")
        result = ConversationEngine(provider).step(session)

        self.assertEqual(result.action, ConversationAction.ASK)
        self.assertEqual(result.question, "家族も追加できた方がいい?")
        self.assertEqual(result.readiness, ConversationReadiness.NEEDS_QUESTION)
        self.assertIsNone(result.build_brief)
        self.assertEqual(result.need_model.unknown_important, ("shared_usage",))

    def test_ask_reports_the_question_key_for_repeat_suppression(self) -> None:
        provider = _FakeProvider(_response(
            unknowns=[_unknown("shared_usage")], next_action="ask",
            question="家族も使う?", question_key="shared_usage", build_brief="",
        ))
        result = ConversationEngine(provider).step(_session_with_user_text("困ってる"))
        self.assertEqual(result.question_key, "shared_usage")

    def test_prompt_includes_full_conversation_history(self) -> None:
        provider = _FakeProvider(_response(
            unknowns=[_unknown("x")], next_action="ask", question="q?", build_brief="",
        ))
        session = _session_with_user_text("買い物で忘れる", "店で見ながら消す感じ?", "そうそう")
        ConversationEngine(provider).step(session)
        assert provider.last_prompt is not None
        self.assertIn("買い物で忘れる", provider.last_prompt)
        self.assertIn("店で見ながら消す感じ?", provider.last_prompt)
        self.assertIn("そうそう", provider.last_prompt)

    def test_step_requires_the_last_turn_to_be_from_the_user(self) -> None:
        provider = _FakeProvider(_response())
        session = ConversationSession(session_id="s1").with_turn(
            ConversationTurn(role="forge", text="質問です")
        )
        with self.assertRaises(ValueError):
            ConversationEngine(provider).step(session)


class TestConversationEngineBuild(unittest.TestCase):
    def test_no_unknowns_yields_build(self) -> None:
        provider = _FakeProvider(_response(
            problem="買い物で何を買うか忘れる",
            known=["家で追加、店で消す", "自分だけで使う"],
            confidence=0.9, next_action="build",
            build_brief="買い物リストを作りたい。家で思いついた時に追加して、店で見ながら消していく。自分だけで使う。",
        ))
        session = _session_with_user_text("買い物行くと、いつも何買うか忘れるんだよね", "うん", "いや、自分だけでいいかな")
        result = ConversationEngine(provider).step(session)

        self.assertEqual(result.action, ConversationAction.BUILD)
        self.assertEqual(result.readiness, ConversationReadiness.BUILD_READY)
        self.assertIsNone(result.question)
        self.assertIn("買い物リスト", result.build_brief or "")

    def test_no_unknowns_builds_even_if_llm_says_ask(self) -> None:
        """LLMの自己申告(next_action)を鵜呑みにしない(指示書3章)。"""
        provider = _FakeProvider(_response(
            known=["k"], confidence=0.3, next_action="ask",
            question="まだ何か聞きたい?", build_brief="買い物リストを作る",
        ))
        result = ConversationEngine(provider).step(_session_with_user_text("買い物で忘れる"))
        self.assertEqual(result.action, ConversationAction.BUILD)

    def test_low_impact_unknown_only_yields_safe_to_assume_build(self) -> None:
        """指示書14章: low-impact unknownのみ → Safe Assumption可能。"""
        provider = _FakeProvider(_response(
            unknowns=[_unknown("sort_order", "low", "並び順は構造を変えない")],
            next_action="build", build_brief="買い物リストを作る",
        ))
        result = ConversationEngine(provider).step(_session_with_user_text("買い物で忘れる"))
        self.assertEqual(result.action, ConversationAction.BUILD)
        self.assertEqual(result.readiness, ConversationReadiness.SAFE_TO_ASSUME)

    def test_cosmetic_unknowns_are_never_asked(self) -> None:
        """指示書5章: 色・レイアウトはDesign Systemが決める。"""
        provider = _FakeProvider(_response(
            unknowns=[
                _unknown("button_color", "cosmetic", "見た目のみ"),
                _unknown("delete_button_side", "cosmetic", "配置のみ"),
            ],
            next_action="ask", question="ボタンの色は?", build_brief="Todoを作る",
        ))
        result = ConversationEngine(provider).step(_session_with_user_text("仕事のTodo作りたい"))
        self.assertEqual(result.action, ConversationAction.BUILD)

    def test_safe_assumptions_record_a_reason_for_unasked_unknowns(self) -> None:
        """指示書6章: 聞かずに決めたことにも理由を残す。"""
        provider = _FakeProvider(_response(
            unknowns=[_unknown("sort_order", "low", "並び順は構造を変えない")],
            next_action="build", build_brief="b",
        ))
        result = ConversationEngine(provider).step(_session_with_user_text("困ってる"))
        recorded = {a.key: a.reason for a in result.need_model.assumptions}
        self.assertIn("sort_order", recorded)
        self.assertTrue(recorded["sort_order"])

    def test_empty_build_brief_falls_back_to_concatenated_user_turns(self) -> None:
        provider = _FakeProvider(_response(confidence=0.9, next_action="build", build_brief=""))
        result = ConversationEngine(provider).step(_session_with_user_text("買い物で忘れる"))
        self.assertEqual(result.action, ConversationAction.BUILD)
        self.assertIn("買い物で忘れる", result.build_brief or "")


class TestTurnLimitNoLongerForcesBuild(unittest.TestCase):
    """指示書1章の中心的な回帰テスト。

    以前は「ターン上限に達したら重要な未知が残っていてもBUILD」という
    挙動をテストが固定していた。今はその逆を固定する。
    """

    def _session_at_turn_limit(self) -> ConversationSession:
        texts: list[str] = []
        for i in range(MAX_CONVERSATION_TURNS):
            texts.append(f"ユーザー発話{i}")
            if i < MAX_CONVERSATION_TURNS - 1:
                texts.append(f"Forge質問{i}")
        session = _session_with_user_text(*texts)
        self.assertEqual(len([t for t in session.turns if t.role == "user"]), MAX_CONVERSATION_TURNS)
        return session

    def test_turn_limit_does_not_force_build_when_a_blocking_unknown_remains(self) -> None:
        """**完了条件そのもの**(指示書16章): 重要なUnknownが残っているのに、
        ターン数だけを理由にBUILDしない。"""
        provider = _FakeProvider(_response(
            unknowns=[_unknown("what_to_track", "blocking", "何を記録するのか決まっていない")],
            confidence=0.4, next_action="ask",
            question="何を記録したいですか?", question_key="what_to_track",
            build_brief="それでも作れるものを作る",
        ))
        result = ConversationEngine(provider).step(self._session_at_turn_limit())
        self.assertEqual(result.action, ConversationAction.ASK)
        self.assertEqual(result.readiness, ConversationReadiness.NEEDS_QUESTION)

    def test_turn_limit_demotes_high_impact_unknowns_to_safe_assumptions(self) -> None:
        """ターン上限の**新しい意味**(指示書1章): 強制BUILDではなく、
        質問戦略の変更。HIGHは聞かずにSafe Assumptionへ回す。"""
        provider = _FakeProvider(_response(
            unknowns=[_unknown("shared_usage", "high", "共有かどうかで権限が変わる")],
            confidence=0.4, next_action="ask", question="家族も使う?",
            question_key="shared_usage", build_brief="買い物リストを作る",
        ))
        result = ConversationEngine(provider).step(self._session_at_turn_limit())
        self.assertEqual(result.action, ConversationAction.BUILD)
        self.assertEqual(result.readiness, ConversationReadiness.SAFE_TO_ASSUME)
        self.assertIn("shared_usage", {a.key for a in result.need_model.assumptions})

    def test_turn_limit_switches_the_prompt_to_narrowed_questions(self) -> None:
        provider = _FakeProvider(_response(
            unknowns=[_unknown("what_to_track", "blocking", "r")],
            next_action="ask", question="q", question_key="what_to_track", build_brief="",
        ))
        ConversationEngine(provider).step(self._session_at_turn_limit())
        assert provider.last_prompt is not None
        self.assertIn("二択", provider.last_prompt)

    def test_below_the_threshold_the_prompt_has_no_narrowing_guidance(self) -> None:
        provider = _FakeProvider(_response(
            unknowns=[_unknown("x", "high", "r")], next_action="ask",
            question="q", question_key="x", build_brief="",
        ))
        ConversationEngine(provider).step(_session_with_user_text("困ってる"))
        assert provider.last_prompt is not None
        self.assertNotIn("二択", provider.last_prompt)


class TestEmptyQuestionNeverBecomesBuild(unittest.TestCase):
    """以前は「askなのに質問文が空ならBUILDへ倒す」という安全網があった。
    これも「分からなくても作る」であり、指示書1章に反するため反転した。"""

    def test_empty_question_still_asks_using_the_unknown_key(self) -> None:
        provider = _FakeProvider(_response(
            unknowns=[_unknown("what_to_track", "blocking", "何を記録するか未定")],
            next_action="ask", question="", question_key="what_to_track", build_brief="",
        ))
        result = ConversationEngine(provider).step(_session_with_user_text("買い物で忘れる"))
        self.assertEqual(result.action, ConversationAction.ASK)
        self.assertIn("what_to_track", result.question or "")


class TestRepeatedQuestionSuppression(unittest.TestCase):
    """指示書5章: 同じUnknownを言い換えて繰り返し質問しない。"""

    def test_an_already_asked_high_impact_unknown_is_not_asked_again(self) -> None:
        provider = _FakeProvider(_response(
            unknowns=[_unknown("shared_usage", "high", "共有かどうか")],
            next_action="ask", question="家族と使いますか?",
            question_key="shared_usage", build_brief="買い物リストを作る",
        ))
        session = _session_with_user_text("買い物で忘れる").with_asked_key("shared_usage")
        result = ConversationEngine(provider).step(session)
        self.assertEqual(result.action, ConversationAction.BUILD)
        self.assertEqual(result.readiness, ConversationReadiness.SAFE_TO_ASSUME)

    def test_an_already_asked_blocking_unknown_never_becomes_build(self) -> None:
        """BLOCKINGは質問済みでもBUILDにしない
        (`INSUFFICIENT_INFORMATION`として聞き直す)。"""
        provider = _FakeProvider(_response(
            unknowns=[_unknown("what_to_track", "blocking", "何を記録するか未定")],
            next_action="build", build_brief="とりあえず作る",
        ))
        session = _session_with_user_text("困ってる").with_asked_key("what_to_track")
        result = ConversationEngine(provider).step(session)
        self.assertEqual(result.action, ConversationAction.ASK)
        self.assertEqual(result.readiness, ConversationReadiness.INSUFFICIENT_INFORMATION)

    def test_already_asked_keys_are_shown_in_the_prompt(self) -> None:
        provider = _FakeProvider(_response(
            unknowns=[_unknown("other", "high", "r")], next_action="ask",
            question="q", question_key="other", build_brief="",
        ))
        session = _session_with_user_text("困ってる").with_asked_key("shared_usage")
        ConversationEngine(provider).step(session)
        assert provider.last_prompt is not None
        self.assertIn("既に質問済み", provider.last_prompt)
        self.assertIn("shared_usage", provider.last_prompt)


class TestConfirmPolicy(unittest.TestCase):
    """指示書4章: 外部作用・不可逆操作はCONFIRM。"""

    def test_external_effect_reported_by_the_llm_yields_confirm(self) -> None:
        provider = _FakeProvider(_response(
            next_action="build", build_brief="家族へ共有する", external_effect=True,
        ))
        result = ConversationEngine(provider).step(_session_with_user_text("これを家族にも送って"))
        self.assertEqual(result.action, ConversationAction.CONFIRM)
        self.assertEqual(result.readiness, ConversationReadiness.NEEDS_CONFIRMATION)
        self.assertTrue(result.confirm_reason)

    def test_external_effect_detected_from_user_text_even_if_llm_denies_it(self) -> None:
        """指示書3章: LLMが「外部作用は無い」と言っても、System Facts側で
        検出したなら安全側(CONFIRM)へ倒す。"""
        provider = _FakeProvider(_response(
            next_action="build", build_brief="共有する", external_effect=False, destructive=False,
        ))
        result = ConversationEngine(provider).step(_session_with_user_text("できたら家族に共有したい"))
        self.assertEqual(result.action, ConversationAction.CONFIRM)

    def test_destructive_request_yields_confirm(self) -> None:
        provider = _FakeProvider(_response(next_action="build", build_brief="全部消す"))
        result = ConversationEngine(provider).step(_session_with_user_text("古い記録を全部削除したい"))
        self.assertEqual(result.action, ConversationAction.CONFIRM)

    def test_plain_local_tool_creation_does_not_confirm(self) -> None:
        """指示書4章: 単なるUI生成・安全なローカルTool作成で毎回
        CONFIRMしないこと。"""
        provider = _FakeProvider(_response(next_action="build", build_brief="買い物リストを作る"))
        result = ConversationEngine(provider).step(
            _session_with_user_text("買い物で何買うか忘れるからメモしたい")
        )
        self.assertEqual(result.action, ConversationAction.BUILD)

    def test_confirmation_wins_over_a_pending_question(self) -> None:
        """安全性が最優先(未知が残っていてもCONFIRMを先に出す)。"""
        provider = _FakeProvider(_response(
            unknowns=[_unknown("what_to_track", "blocking", "r")],
            next_action="ask", question="q", question_key="what_to_track", build_brief="",
        ))
        result = ConversationEngine(provider).step(_session_with_user_text("記録を全部削除したい"))
        self.assertEqual(result.action, ConversationAction.CONFIRM)


class TestConversationEngineUpdate(unittest.TestCase):
    """FORGE-PRODUCT-VISION-002続き(2026-08-11新設)。`has_existing_tool`
    引数によるASK/BUILD/UPDATE分岐の回帰テスト。"""

    def test_llm_says_update_and_has_existing_tool_yields_update(self) -> None:
        provider = _FakeProvider(_response(
            confidence=0.9, next_action="update", build_brief="よく買うものを上に置きたい",
        ))
        session = _session_with_user_text("よく買うものを上に置きたい")
        result = ConversationEngine(provider).step(session, has_existing_tool=True)

        self.assertEqual(result.action, ConversationAction.UPDATE)
        self.assertEqual(result.build_brief, "よく買うものを上に置きたい")

    def test_llm_says_update_but_no_existing_tool_falls_back_to_build(self) -> None:
        """指示書3章の決定的な上書きルール: 更新対象が無いのにupdateを
        鵜呑みにしない(has_existing_tool=Falseが既定)。"""
        provider = _FakeProvider(_response(
            confidence=0.9, next_action="update", build_brief="よく買うものを上に置きたい",
        ))
        session = _session_with_user_text("よく買うものを上に置きたい")
        result = ConversationEngine(provider).step(session, has_existing_tool=False)

        self.assertEqual(result.action, ConversationAction.BUILD)

    def test_update_is_not_chosen_while_a_blocking_unknown_remains(self) -> None:
        provider = _FakeProvider(_response(
            unknowns=[_unknown("which_part", "blocking", "どこを変えるのか不明")],
            next_action="update", question="どこを変えますか?",
            question_key="which_part", build_brief="",
        ))
        result = ConversationEngine(provider).step(
            _session_with_user_text("ちょっと変えたい"), has_existing_tool=True
        )
        self.assertEqual(result.action, ConversationAction.ASK)

    def test_invalid_llm_action_is_corrected_by_readiness(self) -> None:
        """指示書14章: invalid LLM action補正。"""
        provider = _FakeProvider(_response(next_action="teleport", build_brief="買い物リストを作る"))
        result = ConversationEngine(provider).step(_session_with_user_text("買い物で忘れる"))
        self.assertEqual(result.action, ConversationAction.BUILD)

    def test_prompt_mentions_existing_tool_state_when_true(self) -> None:
        provider = _FakeProvider(_response(confidence=0.9, next_action="update", build_brief="b"))
        ConversationEngine(provider).step(_session_with_user_text("変更したい"), has_existing_tool=True)
        assert provider.last_prompt is not None
        self.assertIn("既に生成済みのツールを使っています", provider.last_prompt)

    def test_prompt_mentions_no_tool_state_when_false(self) -> None:
        provider = _FakeProvider(_response(
            known=["k"], unknowns=[_unknown("x")], confidence=0.3,
            next_action="ask", question="q?", question_key="x", build_brief="",
        ))
        ConversationEngine(provider).step(_session_with_user_text("困ってる"), has_existing_tool=False)
        assert provider.last_prompt is not None
        self.assertIn("まだツールは生成されていません", provider.last_prompt)


class TestMalformedLLMOutput(unittest.TestCase):
    """LLMがschemaを守らなかった場合も、決して落ちない・勝手に作らない。"""

    def test_unknowns_that_are_not_objects_are_ignored(self) -> None:
        provider = _FakeProvider(_response(
            unknowns=["文字列だけ", 42, {"impact": "blocking"}], build_brief="b",
        ))
        result = ConversationEngine(provider).step(_session_with_user_text("困ってる"))
        self.assertEqual(result.need_model.unknowns, ())
        self.assertEqual(result.action, ConversationAction.BUILD)

    def test_unknown_impact_value_falls_back_to_low_not_cosmetic(self) -> None:
        """不正なimpactをCOSMETICへ倒すと未知が完全に無視されるため、
        理由が残るLOWへ倒す。"""
        provider = _FakeProvider(_response(
            unknowns=[{"key": "x", "impact": "とても重要", "reason": "r"}], build_brief="b",
        ))
        result = ConversationEngine(provider).step(_session_with_user_text("困ってる"))
        self.assertEqual(result.need_model.unknowns[0].impact.value, "low")

    def test_duplicate_unknown_keys_are_collapsed(self) -> None:
        provider = _FakeProvider(_response(
            unknowns=[_unknown("x", "high"), _unknown("x", "blocking")],
            next_action="ask", question="q", question_key="x", build_brief="",
        ))
        result = ConversationEngine(provider).step(_session_with_user_text("困ってる"))
        self.assertEqual(len(result.need_model.unknowns), 1)


if __name__ == "__main__":
    unittest.main()
