"""conversation_policy.py のテスト(FORGE-CONVERSATION-READY-001、2026-08-12)。

Policyは`ConversationEngine`から切り離された純粋関数群であるため、
LLMを一切介さずに、判断ルールそのものを直接検証できる。
"""

from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from app.ai.runtime.conversation_policy import (  # noqa: E402
    assumptions_for_unasked,
    classify_build_failure,
    detect_risk_signals,
    evaluate_readiness,
    requires_confirmation,
    resolve_action,
    select_question,
)
from app.ai.runtime.conversation_store import MAX_CONVERSATION_TURNS  # noqa: E402
from app.ai.runtime.conversation_types import (  # noqa: E402
    ConversationAction,
    ConversationReadiness,
    DecisionContext,
    NeedModel,
    UnknownImpact,
    UnknownItem,
)


def _need(*unknowns: UnknownItem) -> NeedModel:
    return NeedModel(problem="p", unknowns=unknowns)


def _u(key: str, impact: UnknownImpact) -> UnknownItem:
    return UnknownItem(key=key, impact=impact, reason="テスト用")


class TestReadinessDoesNotTrustTheLLM(unittest.TestCase):
    """指示書2章: LLMの自己申告confidenceだけでBUILD判断をしない。"""

    def test_high_confidence_does_not_make_a_blocking_unknown_disappear(self) -> None:
        need = NeedModel(problem="p", confidence=0.99, unknowns=(_u("what", UnknownImpact.BLOCKING),))
        decision = evaluate_readiness(need, DecisionContext())
        self.assertEqual(decision.readiness, ConversationReadiness.NEEDS_QUESTION)

    def test_zero_confidence_does_not_block_a_build_when_nothing_is_unknown(self) -> None:
        need = NeedModel(problem="p", confidence=0.0)
        decision = evaluate_readiness(need, DecisionContext())
        self.assertEqual(decision.readiness, ConversationReadiness.BUILD_READY)


class TestReadinessMatrix(unittest.TestCase):
    def test_no_unknowns_is_build_ready(self) -> None:
        self.assertEqual(
            evaluate_readiness(_need(), DecisionContext()).readiness,
            ConversationReadiness.BUILD_READY,
        )

    def test_blocking_unknown_needs_question(self) -> None:
        self.assertEqual(
            evaluate_readiness(_need(_u("what", UnknownImpact.BLOCKING)), DecisionContext()).readiness,
            ConversationReadiness.NEEDS_QUESTION,
        )

    def test_high_unknown_needs_question(self) -> None:
        self.assertEqual(
            evaluate_readiness(_need(_u("shared", UnknownImpact.HIGH)), DecisionContext()).readiness,
            ConversationReadiness.NEEDS_QUESTION,
        )

    def test_low_unknown_is_safe_to_assume(self) -> None:
        self.assertEqual(
            evaluate_readiness(_need(_u("sort", UnknownImpact.LOW)), DecisionContext()).readiness,
            ConversationReadiness.SAFE_TO_ASSUME,
        )

    def test_cosmetic_unknown_is_safe_to_assume(self) -> None:
        self.assertEqual(
            evaluate_readiness(_need(_u("color", UnknownImpact.COSMETIC)), DecisionContext()).readiness,
            ConversationReadiness.SAFE_TO_ASSUME,
        )

    def test_asked_blocking_unknown_is_insufficient_information_not_build(self) -> None:
        decision = evaluate_readiness(
            _need(_u("what", UnknownImpact.BLOCKING)),
            DecisionContext(asked_question_keys=("what",)),
        )
        self.assertEqual(decision.readiness, ConversationReadiness.INSUFFICIENT_INFORMATION)

    def test_asked_high_unknown_becomes_safe_to_assume(self) -> None:
        decision = evaluate_readiness(
            _need(_u("shared", UnknownImpact.HIGH)),
            DecisionContext(asked_question_keys=("shared",)),
        )
        self.assertEqual(decision.readiness, ConversationReadiness.SAFE_TO_ASSUME)

    def test_confirmation_outranks_everything_else(self) -> None:
        decision = evaluate_readiness(
            _need(_u("what", UnknownImpact.BLOCKING)),
            DecisionContext(external_effect=True),
        )
        self.assertEqual(decision.readiness, ConversationReadiness.NEEDS_CONFIRMATION)


class TestTurnThresholdChangesStrategyNotOutcome(unittest.TestCase):
    """指示書1章: ターン上限はBUILD条件ではなく質問戦略の閾値。"""

    def _at_limit(self, **kwargs) -> DecisionContext:
        return DecisionContext(user_turn_count=MAX_CONVERSATION_TURNS, **kwargs)

    def test_blocking_still_asks_at_the_threshold(self) -> None:
        decision = evaluate_readiness(_need(_u("what", UnknownImpact.BLOCKING)), self._at_limit())
        self.assertEqual(decision.readiness, ConversationReadiness.NEEDS_QUESTION)

    def test_blocking_still_asks_far_beyond_the_threshold(self) -> None:
        decision = evaluate_readiness(
            _need(_u("what", UnknownImpact.BLOCKING)),
            DecisionContext(user_turn_count=MAX_CONVERSATION_TURNS * 10),
        )
        self.assertEqual(decision.readiness, ConversationReadiness.NEEDS_QUESTION)

    def test_high_stops_being_asked_at_the_threshold(self) -> None:
        decision = evaluate_readiness(_need(_u("shared", UnknownImpact.HIGH)), self._at_limit())
        self.assertEqual(decision.readiness, ConversationReadiness.SAFE_TO_ASSUME)

    def test_high_is_asked_below_the_threshold(self) -> None:
        decision = evaluate_readiness(
            _need(_u("shared", UnknownImpact.HIGH)),
            DecisionContext(user_turn_count=MAX_CONVERSATION_TURNS - 1),
        )
        self.assertEqual(decision.readiness, ConversationReadiness.NEEDS_QUESTION)


class TestQuestionPolicy(unittest.TestCase):
    def test_blocking_is_preferred_over_high(self) -> None:
        need = _need(_u("shared", UnknownImpact.HIGH), _u("what", UnknownImpact.BLOCKING))
        selected = select_question(need, DecisionContext())
        assert selected is not None
        self.assertEqual(selected.key, "what")

    def test_low_and_cosmetic_are_never_selected(self) -> None:
        need = _need(_u("sort", UnknownImpact.LOW), _u("color", UnknownImpact.COSMETIC))
        self.assertIsNone(select_question(need, DecisionContext()))

    def test_already_asked_keys_are_never_selected(self) -> None:
        need = _need(_u("shared", UnknownImpact.HIGH))
        self.assertIsNone(select_question(need, DecisionContext(asked_question_keys=("shared",))))

    def test_a_second_unasked_unknown_is_selected_instead_of_repeating(self) -> None:
        need = _need(_u("shared", UnknownImpact.HIGH), _u("notify", UnknownImpact.HIGH))
        selected = select_question(need, DecisionContext(asked_question_keys=("shared",)))
        assert selected is not None
        self.assertEqual(selected.key, "notify")

    def test_resolved_unknowns_are_not_selected(self) -> None:
        need = _need(UnknownItem(key="x", impact=UnknownImpact.BLOCKING, reason="r", status="resolved"))
        self.assertIsNone(select_question(need, DecisionContext()))


class TestSafeAssumptionReasons(unittest.TestCase):
    """指示書6章: 仮定に「なぜ」を残す。"""

    def test_low_impact_unknown_becomes_an_assumption_with_a_reason(self) -> None:
        assumptions = assumptions_for_unasked(_need(_u("sort", UnknownImpact.LOW)), DecisionContext())
        self.assertEqual(len(assumptions), 1)
        self.assertEqual(assumptions[0].key, "sort")
        self.assertTrue(assumptions[0].reason)

    def test_blocking_unknown_never_becomes_an_assumption(self) -> None:
        assumptions = assumptions_for_unasked(_need(_u("what", UnknownImpact.BLOCKING)), DecisionContext())
        self.assertEqual(assumptions, ())

    def test_already_asked_high_records_that_it_was_asked(self) -> None:
        assumptions = assumptions_for_unasked(
            _need(_u("shared", UnknownImpact.HIGH)),
            DecisionContext(asked_question_keys=("shared",)),
        )
        self.assertEqual(len(assumptions), 1)
        self.assertIn("繰り返し質問せず", assumptions[0].reason)

    def test_high_past_the_threshold_records_the_conversation_length_reason(self) -> None:
        assumptions = assumptions_for_unasked(
            _need(_u("shared", UnknownImpact.HIGH)),
            DecisionContext(user_turn_count=MAX_CONVERSATION_TURNS),
        )
        self.assertEqual(len(assumptions), 1)
        self.assertIn("会話が長くなった", assumptions[0].reason)


class TestRiskSignalDetection(unittest.TestCase):
    def test_sharing_words_are_detected_as_external_effect(self) -> None:
        for text in ("家族に送って", "みんなに共有したい", "ネットに公開したい", "LINEで通知して"):
            with self.subTest(text=text):
                external, _ = detect_risk_signals(text)
                self.assertTrue(external, text)

    def test_destructive_words_are_detected(self) -> None:
        for text in ("全部削除したい", "支払いを管理", "パスワードを保存", "アカウントを消したい"):
            with self.subTest(text=text):
                _, destructive = detect_risk_signals(text)
                self.assertTrue(destructive, text)

    def test_ordinary_local_requests_trigger_nothing(self) -> None:
        for text in (
            "買い物で何買うか忘れる",
            "仕事のTodoを作りたい",
            "読んだ本を記録したい",
            "家族で予定を管理したい",
        ):
            with self.subTest(text=text):
                self.assertEqual(detect_risk_signals(text), (False, False), text)

    def test_empty_text_is_safe(self) -> None:
        self.assertEqual(detect_risk_signals(""), (False, False))


class TestConfirmationPolicy(unittest.TestCase):
    def test_external_effect_requires_confirmation(self) -> None:
        self.assertTrue(requires_confirmation(DecisionContext(external_effect=True)))

    def test_destructive_requires_confirmation(self) -> None:
        self.assertTrue(requires_confirmation(DecisionContext(destructive=True)))

    def test_neither_does_not_require_confirmation(self) -> None:
        self.assertFalse(requires_confirmation(DecisionContext()))

    def test_reason_is_always_present_when_required(self) -> None:
        for context in (
            DecisionContext(external_effect=True),
            DecisionContext(destructive=True),
            DecisionContext(external_effect=True, destructive=True),
        ):
            decision = requires_confirmation(context)
            self.assertTrue(decision.required)
            self.assertTrue(decision.reason)


class TestResolveAction(unittest.TestCase):
    def test_needs_confirmation_becomes_confirm(self) -> None:
        self.assertEqual(
            resolve_action(ConversationReadiness.NEEDS_CONFIRMATION, DecisionContext()),
            ConversationAction.CONFIRM,
        )

    def test_needs_question_and_insufficient_information_both_become_ask(self) -> None:
        for readiness in (
            ConversationReadiness.NEEDS_QUESTION,
            ConversationReadiness.INSUFFICIENT_INFORMATION,
        ):
            self.assertEqual(
                resolve_action(readiness, DecisionContext()), ConversationAction.ASK
            )

    def test_update_requires_an_existing_tool_as_a_system_fact(self) -> None:
        """指示書3章: existing_toolがない → UPDATE不可。"""
        context = DecisionContext(llm_proposed_action="update", has_existing_tool=False)
        self.assertEqual(
            resolve_action(ConversationReadiness.BUILD_READY, context), ConversationAction.BUILD
        )

    def test_update_is_allowed_when_the_tool_actually_exists(self) -> None:
        context = DecisionContext(llm_proposed_action="update", has_existing_tool=True)
        self.assertEqual(
            resolve_action(ConversationReadiness.BUILD_READY, context), ConversationAction.UPDATE
        )

    def test_unknown_llm_action_falls_back_to_build(self) -> None:
        context = DecisionContext(llm_proposed_action="teleport", has_existing_tool=True)
        self.assertEqual(
            resolve_action(ConversationReadiness.SAFE_TO_ASSUME, context), ConversationAction.BUILD
        )


class TestBuildFailureClassification(unittest.TestCase):
    """指示書8章: AIの失敗とユーザー情報不足を混同しない。"""

    def test_understanding_stage_failures_are_recoverable_by_asking(self) -> None:
        for stage in ("domain_classification", "intent_recognition", "meaning_extraction"):
            with self.subTest(stage=stage):
                self.assertTrue(classify_build_failure(stage=stage, sub_reason=None))

    def test_generation_stage_failures_are_internal_not_the_users_fault(self) -> None:
        for stage in ("validation", "repair", "compilation", "runtime"):
            with self.subTest(stage=stage):
                self.assertFalse(classify_build_failure(stage=stage, sub_reason=None))

    def test_provider_outages_are_not_presented_as_missing_information(self) -> None:
        self.assertFalse(
            classify_build_failure(stage="domain_classification", sub_reason="rate_limited")
        )
        self.assertFalse(
            classify_build_failure(stage="domain_classification", sub_reason="unavailable")
        )

    def test_missing_stage_defaults_to_internal_failure(self) -> None:
        self.assertFalse(classify_build_failure(stage=None, sub_reason=None))


if __name__ == "__main__":
    unittest.main()
