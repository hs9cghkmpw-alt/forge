"""Stateful User Correction Loop の E2E テスト
(FORGE-USER-GUIDED-SELF-EXTENSION-006 §38 / §39、2026-08-13新設)。

指示書§38は「`classify_correction()`が存在するだけでは完了としない」と
明示している。要求されているE2Eは:

    User Need → Hypothesis v1 → Sessionに保存 → User Correction
      → Previous Hypothesisを参照 → CorrectionTarget判定
      → 該当部分だけ更新 → Hypothesis v2 → Sessionへ保存
      → User ACCEPT → Accepted Spec → BUILD

したがってこのファイルは`capability.py`の関数を直接呼ぶのではなく、
**`ConversationEngine` + `ConversationStore`を通した往復**で検証する。
関数単体のテストは`test_capability.py`が担当する。

§39のCase A〜Eをすべて含む。
"""

from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from app.ai.runtime.conversation_engine import ConversationEngine  # noqa: E402
from app.ai.runtime.conversation_store import ConversationStore  # noqa: E402
from app.ai.runtime.conversation_types import (  # noqa: E402
    ConversationAction,
    ConversationTurn,
    HypothesisState,
)


class _ScriptedLLM:
    """Product Flowの検証にAI性能を混ぜないためのProvider(指示書§42)。

    常に「作れる」と報告する。こうしておくと、会話が止まったり分岐したり
    した場合、その原因が**Capability層以外にあり得ない**——測りたいものだけ
    が動く状態を作る。
    """

    def __init__(self, problem: str = "困りごと") -> None:
        self._problem = problem

    def complete_structured(self, prompt: str, response_schema: dict) -> dict:
        return {
            "problem": self._problem, "known": [], "unknowns": [], "assumptions": [],
            "confidence": 0.9, "next_action": "build", "question": "",
            "question_key": "", "build_brief": f"{self._problem}のための道具",
            "external_effect": False, "destructive": False,
        }


class _Conversation:
    """Store付きの会話を1本回すヘルパ。実際のRouterと同じ順序で
    「発話を足す → step → 状態を永続化」を行う。"""

    def __init__(self, problem: str = "困りごと") -> None:
        self.store = ConversationStore()
        self.engine = ConversationEngine(_ScriptedLLM(problem))
        self.session = self.store.create()

    def say(self, text: str):
        self.store.add_turn(self.session.session_id, ConversationTurn(role="user", text=text))
        session = self.store.get(self.session.session_id)
        result = self.engine.step(session)
        # Routerと同じ永続化(`app/routers/ai.py`参照)。
        self.store.record_hypothesis_event(
            self.session.session_id,
            event=result.hypothesis_event,
            hypothesis=result.hypothesis,
            correction_target=result.correction_target,
        )
        if result.question_key:
            self.store.mark_question_asked(self.session.session_id, result.question_key)
        if result.question:
            self.store.add_turn(
                self.session.session_id, ConversationTurn(role="forge", text=result.question)
            )
        return result

    @property
    def state(self):
        return self.store.get(self.session.session_id)

    def hypothesis(self):
        return self.state.current_hypothesis


def ids(capabilities) -> list[str]:
    return [c.id for c in capabilities]


class TestCaseA_ViewOnlyCorrection(unittest.TestCase):
    """§39 Case A: Viewだけ訂正。

    期待: fish / size / location のdataは保持され、map markerだけが
    置き換わる。**これが以前は壊れていた**(§12)。
    """

    def test_data_survives_a_view_correction(self) -> None:
        c = _Conversation("釣果を記録したい")

        first = c.say("釣った魚とサイズと場所を記録して、地図で見たい")
        self.assertIs(first.action, ConversationAction.ASK)
        self.assertEqual(first.hypothesis_event, "present")
        v1 = c.hypothesis()
        self.assertEqual(ids(v1.missing), ["view.map"])
        data_before = ids(v1.data)
        self.assertTrue(data_before, "この発話ではDataが検出されている前提")

        second = c.say("違う、よく釣れる場所ほど色を濃くしたい")
        self.assertEqual(second.correction_target, "view")
        v2 = c.hypothesis()

        # ---- 本題: 訂正されていない層が保持されていること ----
        self.assertEqual(ids(v2.data), data_before, "Viewの訂正でDataが消えてはならない")
        # 訂正された層は変わっていること。
        self.assertEqual(ids(v2.missing), ["view.heatmap"])
        self.assertEqual(v2.revision, 1)

    def test_regression_the_stateless_version_lost_the_data(self) -> None:
        """回帰テスト。以前の実装(最新発話だけから作り直す)を再現し、
        **今の実装と結果が違う**ことを固定する。

        これを書いておくと、将来誰かが「毎回作り直す方が単純だ」と
        戻したときに、必ずここが落ちる。
        """
        from app.ai.runtime.capability import build_hypothesis

        stateless = build_hypothesis("違う、よく釣れる場所ほど色を濃くしたい")
        self.assertEqual(ids(stateless.data), [], "旧実装ではDataが空になっていた(記録)")

        c = _Conversation("釣果を記録したい")
        c.say("釣った魚とサイズと場所を記録して、地図で見たい")
        c.say("違う、よく釣れる場所ほど色を濃くしたい")
        self.assertNotEqual(ids(c.hypothesis().data), [], "今の実装では保持されること")


class TestCaseB_DataOnlyCorrection(unittest.TestCase):
    """§39 Case B: Dataだけ訂正。期待は「view等は保持、dataへ追加」。

    「脈拍**も**記録したい」は**追加**であって置き換えではない
    (`_is_additive_correction()`参照)。
    """

    def test_data_is_added_not_replaced_and_view_survives(self) -> None:
        c = _Conversation("血圧を記録したい")

        c.say("血圧の値を記録して、地図で見たい")
        v1 = c.hypothesis()
        self.assertIsNotNone(v1)
        view_before = ids(v1.view)
        data_before = ids(v1.data)

        c.say("日付も記録したい")
        v2 = c.hypothesis()

        self.assertEqual(ids(v2.view), view_before, "Dataの訂正でViewが消えてはならない")
        for existing in data_before:
            self.assertIn(existing, ids(v2.data), "既存のDataが消えている(追加のはずが置換になっている)")
        self.assertIn("data.date", ids(v2.data), "新しく言われた項目が足されていない")


class TestCaseC_ProblemCorrection(unittest.TestCase):
    """§39 Case C: Problem自体が違う。

    期待: 単なるView Correctionとして扱わず、Problem理解まで巻き戻す。
    §15は「`revise_hypothesis()`が`None`を返すだけでは十分ではない。
    呼び出し側が実際にどうState Transitionするかまで必要」と明示している。
    """

    def test_rewinds_the_session_instead_of_swapping_a_layer(self) -> None:
        c = _Conversation("家族の予定を整理したい")

        c.say("家族の予定をカレンダーで見たい")
        self.assertIsNotNone(c.hypothesis())

        result = c.say("そうじゃない。子供の送り迎えの担当だけ決めたい")

        self.assertEqual(result.correction_target, "problem")
        self.assertEqual(result.hypothesis_event, "rewind")
        self.assertIs(result.action, ConversationAction.ASK)

        state = c.state
        self.assertIsNone(state.current_hypothesis, "仮説が捨てられていない")
        self.assertIs(state.hypothesis_state, HypothesisState.REWOUND)
        self.assertEqual(state.rewind_count, 1)
        # 巻き戻しは「聞き直す」ところまでが1セットである。
        self.assertIn("もう一度教えて", result.question)

    def test_rewind_keeps_what_the_user_already_answered(self) -> None:
        """巻き戻したからといって、既に答えたことを聞き直さない。"""
        c = _Conversation("家族の予定を整理したい")
        c.say("家族の予定をカレンダーで見たい")
        asked_before = c.state.asked_question_keys
        c.say("そうじゃない。子供の送り迎えの担当だけ決めたい")
        for key in asked_before:
            self.assertIn(key, c.state.asked_question_keys)


class TestCaseD_AmbiguousNegation(unittest.TestCase):
    """§39 Case D: 「違う」だけ。

    期待: 過去Hypothesisを保持。即捨てない。必要なら短い1問だけ聞く。
    """

    def test_bare_negation_keeps_the_hypothesis_and_asks_once(self) -> None:
        c = _Conversation("釣果を記録したい")

        c.say("釣った魚とサイズを地図で見たい")
        v1 = c.hypothesis()
        self.assertIsNotNone(v1)

        result = c.say("違う")

        self.assertEqual(result.correction_target, "unclear")
        self.assertEqual(result.hypothesis_event, "clarify")
        self.assertIs(c.hypothesis(), v1, "「違う」だけで仮説を捨ててはならない")
        # 丸投げの「どこが違いますか？」にしない(§14)。
        self.assertNotIn("どこが違い", result.question)
        self.assertTrue(result.question)

    def test_does_not_turn_into_an_interrogation(self) -> None:
        """2回目の「違う」で、また同じ聞き返しをしない(質問攻めにしない)。"""
        c = _Conversation("釣果を記録したい")
        c.say("釣った魚とサイズを地図で見たい")
        c.say("違う")
        second = c.say("違う")
        self.assertNotEqual(second.hypothesis_event, "clarify")


class TestCaseE_Acceptance(unittest.TestCase):
    """§39 Case E: 「それでいい」。

    期待: same hypothesisを再提示せず、BUILDへ進む。
    §16はこの接続をE2Eで確認せよと明示している。
    """

    def test_acceptance_proceeds_to_build_without_re_presenting(self) -> None:
        c = _Conversation("釣果を記録したい")

        first = c.say("釣った魚とサイズを地図で見たい")
        presented_question = first.question

        result = c.say("それでいい")

        self.assertIs(result.action, ConversationAction.BUILD, "ACCEPTがBUILDへ繋がっていない")
        self.assertNotEqual(result.question, presented_question, "同じ仮説を再提示している")
        self.assertIs(c.state.hypothesis_state, HypothesisState.ACCEPTED)

    def test_accepted_spec_actually_reaches_the_build_brief(self) -> None:
        """§16の核心。合意した内容がbuild_briefへ載らなければ、訂正の
        往復で仕様を育てた意味が無い(Compilerまで届かない)。"""
        c = _Conversation("釣果を記録したい")
        c.say("釣った魚とサイズを地図で見たい")
        result = c.say("それでいい")

        self.assertIsNotNone(result.build_brief)
        self.assertIn("ユーザーと合意した形", result.build_brief)

    def test_corrected_then_accepted_carries_the_revised_spec(self) -> None:
        """訂正 → 合意の順でも、**改訂後の**内容がBUILDへ届くこと。"""
        c = _Conversation("釣果を記録したい")
        c.say("釣った魚とサイズを地図で見たい")
        c.say("違う、色を濃くして分布が見たい")
        revised = c.hypothesis()
        result = c.say("それでいい")

        self.assertIs(result.action, ConversationAction.BUILD)
        # **作れるものだけ**がbriefへ載ること。作れないもの(この時点では
        # ヒートマップ)をCompilerへ指示すると、実現できないか、実現した
        # ふりになる。段の分離ができてから初めて意味を持つ確認である。
        for capability in revised.buildable:
            self.assertIn(capability.label_ja, result.build_brief)
        for capability in revised.missing:
            self.assertNotIn(
                capability.label_ja, result.build_brief,
                "作れないものを生成指示へ載せている",
            )


class TestCorrectionHistory(unittest.TestCase):
    """§17: 履歴は単なるログにしない。用途を2つに限定している。"""

    def test_history_records_what_changed_not_the_raw_utterance(self) -> None:
        c = _Conversation("釣果を記録したい")
        c.say("釣った魚とサイズを地図で見たい")
        c.say("違う、色を濃くして分布が見たい")

        history = c.state.correction_history
        self.assertEqual(len(history), 1)
        record = history[0]
        self.assertEqual(record.target, "view")
        self.assertEqual(record.from_missing, ("view.map",))
        self.assertEqual(record.to_missing, ("view.heatmap",))
        # 発話全文は`turns`に既にあるため、履歴側では持たない
        # (Storage肥大化とPrivacyへの配慮、§17末尾)。
        self.assertFalse(hasattr(record, "user_text"))


class TestExistingBehaviourUnchanged(unittest.TestCase):
    """Capability層が関与しない会話は、今までと完全に同じであること。"""

    def test_ordinary_request_never_touches_hypothesis_state(self) -> None:
        c = _Conversation("買い物で忘れる")
        result = c.say("買い物で何買うか忘れちゃう")

        self.assertIs(result.action, ConversationAction.BUILD)
        self.assertIsNone(result.hypothesis_event)
        self.assertIsNone(c.state.current_hypothesis)
        self.assertIs(c.state.hypothesis_state, HypothesisState.NONE)
        self.assertEqual(c.state.correction_history, ())


if __name__ == "__main__":
    unittest.main()


class TestPhaseOrdering(unittest.TestCase):
    """指摘1の回帰テスト(2026-08-13)。

    Capability層は「CONFIRMの後、ASKの前」という**行の位置**で差し込まれて
    いたため、Problem/NeedにBLOCKINGな未知が残っていても仮説提示が先に
    出ていた。Problem Discovery → Need → Solution という順序に反する。

    優先順位は`conversation_policy.select_phase()`が決める。
    """

    def _engine_with_blocking_unknown(self):
        class _BlockingLLM:
            def complete_structured(self, prompt: str, schema: dict) -> dict:
                return {
                    "problem": "地図で見たい", "known": [],
                    "unknowns": [{
                        "key": "what_to_record", "impact": "blocking",
                        "reason": "何を記録するのか分からないと作れない",
                    }],
                    "assumptions": [], "confidence": 0.3, "next_action": "ask",
                    "question": "何を記録したいですか？", "question_key": "what_to_record",
                    "build_brief": "", "external_effect": False, "destructive": False,
                }

        c = _Conversation()
        c.engine = ConversationEngine(_BlockingLLM())
        return c

    def test_blocking_need_is_asked_before_any_capability_hypothesis(self) -> None:
        c = self._engine_with_blocking_unknown()
        result = c.say("地図で見たい")

        self.assertEqual(result.question, "何を記録したいですか？")
        self.assertIsNone(
            result.hypothesis_event,
            "BLOCKINGな未知が残っているのに仮説を提示している(指摘1の再発)",
        )
        self.assertIsNone(c.state.current_hypothesis)

    def test_pending_hypothesis_reply_still_wins_over_a_blocking_need(self) -> None:
        """既に仮説を提示している場合、その返事の処理が先である。

        Forge自身が直前に問いを出しているのだから、答えを聞かずに
        別の質問へ移るのは会話として破綻している。
        """
        c = _Conversation("釣果を記録したい")
        c.say("釣った魚とサイズを地図で見たい")
        self.assertIsNotNone(c.hypothesis())

        # ここからBLOCKINGな未知を報告するProviderへ差し替える。
        class _BlockingLLM:
            def complete_structured(self, prompt: str, schema: dict) -> dict:
                return {
                    "problem": "釣果", "known": [],
                    "unknowns": [{"key": "what_to_record", "impact": "blocking", "reason": "x"}],
                    "assumptions": [], "confidence": 0.3, "next_action": "ask",
                    "question": "何を記録したいですか？", "question_key": "what_to_record",
                    "build_brief": "", "external_effect": False, "destructive": False,
                }

        c.engine = ConversationEngine(_BlockingLLM())
        result = c.say("違う、色を濃くして分布が見たい")

        self.assertEqual(result.correction_target, "view", "仮説への返事が無視されている")
        self.assertEqual(result.hypothesis_event, "present")

    def test_safety_still_outranks_everything(self) -> None:
        """CONFIRMは何よりも先。会話の都合で後回しにしない。"""
        class _RiskyLLM:
            def complete_structured(self, prompt: str, schema: dict) -> dict:
                return {
                    "problem": "共有したい", "known": [], "unknowns": [], "assumptions": [],
                    "confidence": 0.9, "next_action": "build", "question": "",
                    "question_key": "", "build_brief": "共有する道具",
                    "external_effect": True, "destructive": False,
                }

        c = _Conversation()
        c.engine = ConversationEngine(_RiskyLLM())
        result = c.say("地図で見たいものを家族に共有したい")

        self.assertIs(result.action, ConversationAction.CONFIRM)
        self.assertIsNone(result.hypothesis_event, "安全確認より先に仮説が出ている")


class TestAcceptanceIsNotMisreadAsCorrection(unittest.TestCase):
    """指摘3の回帰テスト(2026-08-13)。

    肯定文にCapability語が含まれるだけで訂正へ倒れていた。
    「うん、地図でいい」の「地図」は**合意の対象**であって変更要求ではない。
    """

    def _pending(self) -> _Conversation:
        c = _Conversation("釣果を記録したい")
        c.say("釣った魚を地図で見たい")
        self.assertIsNotNone(c.hypothesis())
        return c

    def test_natural_acceptances_with_capability_words_proceed_to_build(self) -> None:
        for utterance in (
            "うん、地図でいい",
            "はい、その地図の感じで",
            "いいよ、地図で",
            "そうそう、一覧で大丈夫",
            "うん、そのカレンダーでいい",
        ):
            with self.subTest(utterance=utterance):
                c = self._pending()
                result = c.say(utterance)
                self.assertIs(
                    result.action, ConversationAction.BUILD,
                    f"{utterance!r} が訂正として扱われている(指摘3の再発)",
                )
                self.assertIs(c.state.hypothesis_state, HypothesisState.ACCEPTED)

    def test_affirmation_with_a_contrast_marker_is_still_a_correction(self) -> None:
        """「うん、でも地図じゃなくて一覧がいい」は肯定語を含むが訂正である。
        ACCEPT判定を単に最上位へ動かすだけでは、これを取りこぼす。"""
        c = self._pending()
        result = c.say("うん、でも地図じゃなくて一覧がいい")
        self.assertEqual(result.correction_target, "view")
        self.assertIsNot(c.state.hypothesis_state, HypothesisState.ACCEPTED)

    def test_plain_negation_with_a_capability_is_still_a_correction(self) -> None:
        c = self._pending()
        result = c.say("違う、色の濃さで見たい")
        self.assertEqual(result.correction_target, "view")


class TestMissingSurvivesUnrelatedCorrections(unittest.TestCase):
    """指摘2の回帰テスト(2026-08-13)。

    `missing`をフィールドとして保存し、訂正対象層のMissingで全体を置換して
    いたため、訂正していない層のMissingが消えていた。導出値は保存しない。
    """

    def test_photo_gap_survives_a_view_correction(self) -> None:
        c = _Conversation("釣果を記録したい")
        c.say("写真を記録して地図で見たい")
        v1 = c.hypothesis()
        self.assertEqual(ids(v1.missing), ["data.photo", "view.map"])

        c.say("違う、色の濃さで見たい")
        v2 = c.hypothesis()

        self.assertIn(
            "data.photo", ids(v2.missing),
            "訂正していない層のMissingが消えている(指摘2の再発)",
        )
        self.assertIn("view.heatmap", ids(v2.missing), "訂正した層が反映されていない")
        self.assertNotIn("view.map", ids(v2.missing), "古いMissingが残っている")

    def test_missing_is_always_derived_never_stored(self) -> None:
        """構造としての担保。`missing`がフィールドに戻ったら落ちる。"""
        from dataclasses import fields

        from app.ai.runtime.capability import SolutionHypothesis

        self.assertNotIn(
            "missing", {f.name for f in fields(SolutionHypothesis)},
            "missingがフィールドとして保存されている(部分更新で壊れる形に戻っている)",
        )
