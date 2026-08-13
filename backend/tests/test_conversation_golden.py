"""Conversation Golden Test(FORGE-CONVERSATION-READY-001、2026-08-12、指示書9章)。

**これまでのGolden Testとの違い**: 既存の
`forge_ai/tests/test_cognitive_pipeline_golden.py`は「最終JSONが正しいか」
を凍結していた。指示書9章は「それだけでは足りない。**会話そのもの**を
評価する」と指示しており、このファイルは会話の進み方
——何回聞いたか、聞くべきことを聞いたか、聞くべきでないことを聞かな
かったか、CONFIRMを正しく出したか——を評価する。

**LLMは使わない**: 会話の質を評価したいのであって、LLMの機嫌を
テストしたいのではない。各ケースは「LLMがこう返したとき」を
`_ScriptedProvider`で固定し、**Forge側のPolicyが正しく振る舞うか**
だけを検証する(LLMが誤った提案をしてもPolicyが正すことこそ、
指示書3章の要求である)。

指示書9章の評価項目のうち、このファイルが機械的に判定するもの:
* action correctness
* unnecessary question count
* missed blocking question
* repeated question
* time-to-build(= BUILDまでのユーザーターン数)
* safe assumption usage
* confirm correctness
"""

from __future__ import annotations

import os
import sys
import unittest
from dataclasses import dataclass, field
from typing import Any

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from app.ai.runtime.conversation_engine import ConversationEngine  # noqa: E402
from app.ai.runtime.conversation_types import (  # noqa: E402
    ConversationAction,
    ConversationSession,
    ConversationTurn,
)


class _ScriptedProvider:
    """ターンごとに、あらかじめ決めた応答を順に返すProvider。"""

    def __init__(self, script: list[dict[str, Any]]) -> None:
        self._script = script
        self._index = 0

    def complete_structured(self, prompt: str, response_schema: dict[str, Any]) -> dict[str, Any]:
        response = self._script[min(self._index, len(self._script) - 1)]
        self._index += 1
        return response


def _llm(
    *,
    action: str = "build",
    unknowns: list[dict[str, Any]] | None = None,
    question: str = "",
    question_key: str = "",
    brief: str = "道具を作る",
    external: bool = False,
    destructive: bool = False,
) -> dict[str, Any]:
    return {
        "problem": "p", "known": [], "unknowns": unknowns or [], "assumptions": [],
        "confidence": 0.7, "next_action": action, "question": question,
        "question_key": question_key, "build_brief": brief,
        "external_effect": external, "destructive": destructive,
    }


def _unknown(key: str, impact: str, reason: str = "テスト用") -> dict[str, Any]:
    return {"key": key, "impact": impact, "reason": reason}


@dataclass
class ConversationTranscript:
    """会話1件を最後まで進めた結果の記録(指示書9章の評価項目)。"""

    actions: list[ConversationAction] = field(default_factory=list)
    questions: list[str] = field(default_factory=list)
    question_keys: list[str] = field(default_factory=list)
    ask_strategies: list[str] = field(default_factory=list)
    readiness: list[str] = field(default_factory=list)
    strategies: list[str] = field(default_factory=list)
    final_assumptions: tuple[str, ...] = ()

    @property
    def question_count(self) -> int:
        return sum(1 for a in self.actions if a == ConversationAction.ASK)

    @property
    def repeated_question_count(self) -> int:
        """**同じUnknownを、同じ聞き方で**繰り返した回数。

        FORGE-QUALITY-AI-INDEPENDENCE-003 §15でStrategy Escalationが
        入ったため、同じkeyへ再び触れること自体は正常な進行になった
        (ASK → REPHRASE → OFFER_DEFAULT)。指示書5章が禁じているのは
        「同じUnknownを**言い換えて**繰り返す」——つまり情報量が増えて
        いないのに同じ段で聞き直すことなので、keyだけでなく段
        (strategy)まで一致した場合だけを繰り返しとして数える。
        """
        pairs = [
            (k, s) for k, s in zip(self.question_keys, self.ask_strategies) if k
        ]
        return len(pairs) - len(set(pairs))

    @property
    def final_action(self) -> ConversationAction:
        return self.actions[-1]

    @property
    def time_to_build(self) -> int:
        """BUILD/UPDATEに至るまでに要したユーザーターン数。"""
        for i, action in enumerate(self.actions):
            if action in (ConversationAction.BUILD, ConversationAction.UPDATE):
                return i + 1
        return len(self.actions)


def run_conversation(
    user_messages: list[str],
    script: list[dict[str, Any]],
    *,
    has_existing_tool: bool = False,
    max_turns: int = 8,
) -> ConversationTranscript:
    """ユーザー発話とLLM応答スクリプトから、会話を最後まで進める。

    `/converse`(HTTP層)が行っている「ASKならquestion_keyを記録して
    次ターンへ」という往復を、Engine層だけで再現する。
    """
    engine = ConversationEngine(_ScriptedProvider(script))
    session = ConversationSession(session_id="golden")
    transcript = ConversationTranscript()

    for message in user_messages[:max_turns]:
        session = session.with_turn(ConversationTurn(role="user", text=message))
        result = engine.step(session, has_existing_tool=has_existing_tool)

        transcript.actions.append(result.action)
        transcript.readiness.append(result.readiness.value)
        transcript.strategies.append(result.strategy.value)
        if result.action == ConversationAction.ASK:
            transcript.questions.append(result.question or "")
            transcript.question_keys.append(result.question_key or "")
            transcript.ask_strategies.append(result.strategy.value)
            session = session.with_turn(ConversationTurn(role="forge", text=result.question or ""))
            if result.question_key:
                session = session.with_asked_key(result.question_key)
        else:
            transcript.final_assumptions = tuple(a.key for a in result.need_model.assumptions)
            break
    return transcript


class TestGoldenCase01ShoppingBuildsFast(unittest.TestCase):
    """指示書9章 例1: 「買い物で何買うか忘れる」→ ASK 0〜1回 → BUILD。"""

    def test_shopping_reaches_build_within_one_question(self) -> None:
        transcript = run_conversation(
            ["買い物で何買うか忘れる", "自分だけで使う"],
            [
                _llm(action="ask", unknowns=[_unknown("shared_usage", "high", "共有で権限が変わる")],
                     question="家族とも使いますか?", question_key="shared_usage"),
                _llm(action="build", brief="買い物リストを作る"),
            ],
        )
        self.assertEqual(transcript.final_action, ConversationAction.BUILD)
        self.assertLessEqual(transcript.question_count, 1)
        self.assertEqual(transcript.repeated_question_count, 0)

    def test_shopping_with_no_unknowns_builds_immediately(self) -> None:
        transcript = run_conversation(
            ["買い物で何買うか忘れる"], [_llm(action="build", brief="買い物リストを作る")],
        )
        self.assertEqual(transcript.final_action, ConversationAction.BUILD)
        self.assertEqual(transcript.question_count, 0)
        self.assertEqual(transcript.time_to_build, 1)


class TestGoldenCase02FamilyScheduleAsksWhatMatters(unittest.TestCase):
    """指示書9章 例2: 「家族で予定を管理したい」→ 必要な質問をする。

    共有前提・誰が追加できるかは、保存場所と権限を変えるHIGHであり、
    聞かずに済ませてはならない。
    """

    def test_shared_usage_is_actually_asked(self) -> None:
        transcript = run_conversation(
            ["家族で予定を管理したい", "みんな追加できていい"],
            [
                _llm(action="ask",
                     unknowns=[_unknown("who_can_add", "high", "誰が追加できるかで権限設計が変わる")],
                     question="ご家族みんなが追加できる方がいいですか?", question_key="who_can_add"),
                _llm(action="build", brief="家族で使える予定管理を作る"),
            ],
        )
        self.assertIn("who_can_add", transcript.question_keys)
        self.assertEqual(transcript.final_action, ConversationAction.BUILD)

    def test_a_blocking_unknown_is_never_skipped(self) -> None:
        """missed blocking question の検出。"""
        transcript = run_conversation(
            ["家族で何か管理したい"],
            [_llm(action="build",
                  unknowns=[_unknown("what_to_track", "blocking", "何を管理するのか未定")],
                  brief="何かを作る")],
        )
        self.assertEqual(transcript.final_action, ConversationAction.ASK)


class TestGoldenCase03WorkTodoAsksNothingCosmetic(unittest.TestCase):
    """指示書9章 例3: 「仕事のTodo作りたい」→ 色やレイアウトを質問しない。"""

    def test_cosmetic_unknowns_produce_zero_questions(self) -> None:
        transcript = run_conversation(
            ["仕事のTodo作りたい"],
            [_llm(action="ask",
                  unknowns=[
                      _unknown("accent_color", "cosmetic", "見た目のみ"),
                      _unknown("delete_button_side", "cosmetic", "配置のみ"),
                      _unknown("list_density", "cosmetic", "余白のみ"),
                  ],
                  question="ボタンの色はどうしますか?", question_key="accent_color",
                  brief="仕事用のTodoを作る")],
        )
        self.assertEqual(transcript.question_count, 0, "cosmeticな項目を質問してはならない")
        self.assertEqual(transcript.final_action, ConversationAction.BUILD)

    def test_cosmetic_unknowns_are_recorded_as_safe_assumptions(self) -> None:
        """safe assumption usage: 聞かずに決めたことは記録に残す。"""
        transcript = run_conversation(
            ["仕事のTodo作りたい"],
            [_llm(action="build",
                  unknowns=[_unknown("accent_color", "cosmetic", "見た目のみ")],
                  brief="仕事用のTodoを作る")],
        )
        self.assertIn("accent_color", transcript.final_assumptions)


class TestGoldenCase04ExternalSendConfirms(unittest.TestCase):
    """指示書9章 例4: 「これを家族にも送って」→ 外部送信ならCONFIRM。"""

    def test_external_send_yields_confirm(self) -> None:
        transcript = run_conversation(
            ["これを家族にも送って"],
            [_llm(action="build", brief="家族へ送る", external=True)],
            has_existing_tool=True,
        )
        self.assertEqual(transcript.final_action, ConversationAction.CONFIRM)

    def test_confirm_correctness_local_only_request_does_not_confirm(self) -> None:
        """confirm correctness の裏側: 安全なローカル生成でCONFIRMしない。"""
        transcript = run_conversation(
            ["読んだ本を記録したい"], [_llm(action="build", brief="読書記録を作る")],
        )
        self.assertEqual(transcript.final_action, ConversationAction.BUILD)


class TestGoldenCase05ExistingToolUpdates(unittest.TestCase):
    """指示書9章 例5: 既存Toolあり + 「期限も追加して」→ UPDATE。"""

    def test_modification_with_existing_tool_yields_update(self) -> None:
        transcript = run_conversation(
            ["期限も追加して"],
            [_llm(action="update", brief="各項目に期限を追加する")],
            has_existing_tool=True,
        )
        self.assertEqual(transcript.final_action, ConversationAction.UPDATE)


class TestGoldenCase06UpdateWithoutToolIsCorrected(unittest.TestCase):
    """指示書9章 例6: 既存Toolなし + LLMがUPDATE提案 → BUILD/ASKへ補正。"""

    def test_update_without_an_existing_tool_becomes_build(self) -> None:
        transcript = run_conversation(
            ["期限も追加して"],
            [_llm(action="update", brief="各項目に期限を追加する")],
            has_existing_tool=False,
        )
        self.assertEqual(transcript.final_action, ConversationAction.BUILD)

    def test_update_without_a_tool_and_with_a_blocking_unknown_becomes_ask(self) -> None:
        transcript = run_conversation(
            ["期限も追加して"],
            [_llm(action="update",
                  unknowns=[_unknown("what_to_track", "blocking", "何の期限か不明")],
                  question="何の期限ですか?", question_key="what_to_track", brief="")],
            has_existing_tool=False,
        )
        self.assertEqual(transcript.final_action, ConversationAction.ASK)


class TestGoldenNoRepeatedQuestions(unittest.TestCase):
    """指示書9章の評価項目「repeated question」。"""

    def test_the_same_unknown_is_never_asked_twice_across_turns(self) -> None:
        """LLMが毎ターン同じUnknownを聞こうとしても、Policyが止める。"""
        insistent = _llm(
            action="ask",
            unknowns=[_unknown("shared_usage", "high", "共有かどうか")],
            question="家族と使いますか?", question_key="shared_usage",
            brief="買い物リストを作る",
        )
        transcript = run_conversation(
            ["買い物で忘れる", "うーん", "どうかな", "まあいいや"], [insistent],
        )
        self.assertEqual(transcript.repeated_question_count, 0)
        self.assertLessEqual(transcript.question_count, 1)
        self.assertEqual(transcript.final_action, ConversationAction.BUILD)


class TestGoldenTurnLimitDoesNotCauseBlindBuild(unittest.TestCase):
    """FORGE-CONVERSATION-READY-001 §16の完了条件を、会話レベルで固定する。

    **FORGE-QUALITY-AI-INDEPENDENCE-003 §14・§15での契約の進化**:
    以前このクラスは「blockingが残る限り**永久にBUILDしない**」ことを
    固定していた。しかしそれは、ユーザーが「分からない」「任せる」と
    答え続けた場合に**無限ASK**になるということでもあった。

    新しい契約は「ターン数だけを理由にBUILDしない」を維持したまま、
    同じUnknownへ向き合った回数に応じて**聞き方の段を上げ**、最後は
    そのUnknownを必要としない**最小の解へ縮退して作る**である
    (Smallest Useful Tool)。したがってここでは:

    * 段を上げずにいきなりBUILDしないこと
    * 縮退してBUILDしたときは、必ず理由付きの仮定が残ること
    * **高リスク(外部作用・不可逆)なら、縮退もせず決してBUILDしない**

    を固定する。
    """

    STUCK_BLOCKING = _llm(
        action="ask",
        unknowns=[_unknown("what_to_track", "blocking", "何を記録するのか決まらない")],
        question="何を記録したいですか?", question_key="what_to_track",
        brief="それでも何か作る",
    )

    def test_it_does_not_build_immediately_while_a_blocking_unknown_stands(self) -> None:
        transcript = run_conversation(["何か作って", "うーん"], [self.STUCK_BLOCKING])
        self.assertNotIn(ConversationAction.BUILD, transcript.actions)

    def test_it_escalates_instead_of_repeating_the_same_question(self) -> None:
        """§15: 同じことを聞き続けない。段が上がる。"""
        transcript = run_conversation(
            ["何か作って", "うーん", "わからない"], [self.STUCK_BLOCKING],
        )
        self.assertEqual(transcript.repeated_question_count, 0)
        self.assertGreater(len(set(transcript.strategies)), 1, "戦略が1段も上がっていない")

    def test_it_eventually_shrinks_to_a_smaller_tool_instead_of_asking_forever(self) -> None:
        """§14: 「作れない」ではなく、Unknownを必要としない最小解へ。"""
        transcript = run_conversation(
            ["何か作って", "うーん", "どうかな", "とりあえず", "なんでもいい", "はい"],
            [self.STUCK_BLOCKING],
        )
        self.assertIn(
            transcript.final_action, (ConversationAction.BUILD, ConversationAction.UPDATE),
            "縮退せず無限にASKし続けている",
        )
        self.assertIn("what_to_track", transcript.final_assumptions)

    def test_delegation_short_circuits_to_offering_a_default(self) -> None:
        """§12: 「任せる」と言われたら、同じことを聞き続けない。"""
        transcript = run_conversation(["何か作って", "任せる"], [self.STUCK_BLOCKING])
        self.assertIn("offer_default", transcript.strategies)

    def test_a_high_risk_blocking_unknown_never_shrinks_into_a_build(self) -> None:
        """§13 HARD_BLOCKING・§31 最低条件C: 高リスクは勝手に仮定しない。"""
        risky = _llm(
            action="ask",
            unknowns=[_unknown("share_scope", "blocking", "誰に公開するか不明")],
            question="どこまで公開しますか?", question_key="share_scope",
            brief="公開する", external=True,
        )
        transcript = run_conversation(
            ["みんなに公開したい", "わからない", "任せる", "どっちでもいい"], [risky],
        )
        self.assertNotIn(ConversationAction.BUILD, transcript.actions)
        self.assertNotIn(ConversationAction.UPDATE, transcript.actions)

    def test_a_high_impact_unknown_does_reach_build_after_the_threshold(self) -> None:
        """BLOCKINGでなければ、会話が長引いた時点でSafe Assumptionで進む。"""
        stuck = _llm(
            action="ask",
            unknowns=[_unknown("shared_usage", "high", "共有かどうか")],
            question="家族と使いますか?", question_key="shared_usage",
            brief="買い物リストを作る",
        )
        transcript = run_conversation(
            ["買い物で忘れる", "うーん", "どうかな", "まあいいや"], [stuck],
        )
        self.assertEqual(transcript.final_action, ConversationAction.BUILD)
        self.assertIn("shared_usage", transcript.final_assumptions)


if __name__ == "__main__":
    unittest.main()


class TestScriptedConversationSet(unittest.TestCase):
    """Scripted Conversation Set(FORGE-QUALITY-AI-INDEPENDENCE-003 §26)。

    実ユーザーデータが無くても会話品質を測り続けるための50セッション。
    **このデータセットは、実際に走らせた時点でPolicyの実バグを3件
    検出した**(下の各テストは、その回帰テストでもある):

    1. 「任せる」検出が`OFFER_DEFAULT`を返し続け、段が上がらなかった
       (15セッションで繰り返し質問、縮退が一度も発動せず)。
    2. BUILD経路で`strategy`を渡し忘れており、縮退した事実が記録に
       残らなかった(`solution_shrink_count`が常に0)。
    3. 委任の判定が最新発話のみだったため、「任せる」→「うん」で
       **委任が忘れられ**、同じ既定提示を繰り返した。
    """

    @classmethod
    def setUpClass(cls) -> None:
        from app.ai.gateway.conversation_dataset import run_all_sessions

        cls.outcomes, cls.metrics = run_all_sessions()

    def test_the_dataset_has_at_least_fifty_sessions(self) -> None:
        self.assertGreaterEqual(self.metrics.sessions, 50)

    def test_it_covers_every_conversation_kind_the_directive_lists(self) -> None:
        from app.ai.gateway.conversation_dataset import session_count_by_category

        categories = session_count_by_category()
        for required in (
            "clear", "ambiguous", "dont_know", "delegated", "whatever",
            "irrelevant", "changed_mind", "update", "high_risk",
        ):
            self.assertIn(required, categories, f"{required}のセッションが無い")

    def test_no_session_repeats_the_same_question_at_the_same_stage(self) -> None:
        offenders = [o.name for o in self.outcomes if o.repeated_question_count]
        self.assertEqual(offenders, [], f"繰り返し質問が発生: {offenders}")

    def test_no_session_ends_unresolved(self) -> None:
        """無限ASKしない(§12)。全セッションがbuild/update/confirmで決着する。"""
        stuck = [
            o.name for o in self.outcomes
            if o.final_action.value not in ("build", "update", "confirm")
        ]
        self.assertEqual(stuck, [], f"決着しなかったセッション: {stuck}")

    def test_unresolvable_sessions_shrink_instead_of_asking_forever(self) -> None:
        """§14 Smallest Useful Tool が実際に発動していること。"""
        self.assertGreater(self.metrics.shrinks, 0, "縮退が一度も発動していない")

    def test_clear_requests_are_built_without_any_question(self) -> None:
        clear = [o for o in self.outcomes if o.category == "clear"]
        self.assertTrue(clear)
        for outcome in clear:
            with self.subTest(session=outcome.name):
                self.assertEqual(outcome.questions_before_build, 0)
                self.assertEqual(outcome.final_action, ConversationAction.BUILD)

    def test_high_risk_sessions_always_confirm_and_never_build(self) -> None:
        """§31 最低条件C: 高リスクを勝手に仮定しない。"""
        risky = [o for o in self.outcomes if o.category == "high_risk"]
        self.assertTrue(risky)
        for outcome in risky:
            with self.subTest(session=outcome.name):
                self.assertEqual(outcome.final_action, ConversationAction.CONFIRM)
                self.assertNotIn(ConversationAction.BUILD, outcome.actions)

    def test_update_sessions_use_update_not_build(self) -> None:
        for outcome in [o for o in self.outcomes if o.category == "update"]:
            with self.subTest(session=outcome.name):
                self.assertEqual(outcome.final_action, ConversationAction.UPDATE)

    def test_the_average_question_count_stays_low(self) -> None:
        """「質問攻めにしない」(§5)を、データセット全体の平均で固定する。"""
        self.assertLessEqual(
            self.metrics.avg_questions_per_session, 2.0,
            f"平均質問数が多すぎる: {self.metrics.avg_questions_per_session}",
        )

    def test_no_session_fails_to_build(self) -> None:
        self.assertEqual(self.metrics.build_failures, 0)

    def test_every_shrunk_build_records_why(self) -> None:
        """§6: 縮退して作ったなら、その理由が必ず仮定として残る。"""
        shrunk = [
            o for o in self.outcomes
            if "shrink_solution" in o.strategies
            and o.final_action is ConversationAction.BUILD
        ]
        self.assertTrue(shrunk)
        for outcome in shrunk:
            with self.subTest(session=outcome.name):
                self.assertGreater(outcome.safe_assumptions, 0)
