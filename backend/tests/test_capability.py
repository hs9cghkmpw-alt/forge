"""Capability Layerのテスト(FORGE-ARCHITECTURE-REVIEW-AND-IMPLEMENT-005
§32 Vertical Slice、2026-08-13新設)。

`docs/spec/FORGE-SELF-EXTENSION-ARCH-REVIEW.md` §8のテスト戦略に対応する:

* CapabilityResolverは純粋関数 → LLM無しで単体テスト
* §33の実例(釣果を地図で → 「違う、色を濃く」→ heatmap)をGolden
  Conversationとして固定
* 既存50セッションに対してMISSINGが誤検出されないことを回帰確認
"""

from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from app.ai.gateway.conversation_dataset import SCRIPTED_SESSIONS  # noqa: E402
from app.ai.runtime.capability import (  # noqa: E402
    CAPABILITY_REGISTRY,
    CapabilityLayer,
    CorrectionTarget,
    build_hypothesis,
    classify_correction,
    detect_capabilities,
    has_buildable_gap,
    missing_capabilities,
    revise_hypothesis,
)
from app.ai.runtime.conversation_types import (  # noqa: E402
    ConversationAction,
    ConversationSession,
    ConversationTurn,
)
from app.ai.validators.schema_validator import WIDGET_TYPES_ALL  # noqa: E402


class TestRegistryIntegrity(unittest.TestCase):
    """Registryは人手管理の静的テーブルである。AIが書き換えないこと・
    Widget Registryと食い違わないことを、機械的に担保する。"""

    def test_supported_capabilities_map_to_real_widget_types(self) -> None:
        """`supported=True`と書いてあるのに、実際にはRuntimeが知らない
        Widget型を指している、という嘘を防ぐ。

        TD37(Registryへの登録漏れで4種のWidgetが描画不能だった実バグ)と
        同じ種類の事故を、この層でも起こさないための回帰テスト。
        """
        for capability in CAPABILITY_REGISTRY.values():
            if not capability.supported:
                continue
            with self.subTest(capability=capability.id):
                self.assertTrue(
                    capability.widget_types,
                    "supported=True なら、対応するWidget型を必ず書くこと",
                )
                for widget_type in capability.widget_types:
                    self.assertIn(widget_type, WIDGET_TYPES_ALL, f"{capability.id} -> {widget_type}")

    def test_unsupported_capabilities_claim_no_widget_types(self) -> None:
        """未実装のものが、実装済みのふりをしていないこと(レビュー F3)。"""
        for capability in CAPABILITY_REGISTRY.values():
            if capability.supported:
                continue
            with self.subTest(capability=capability.id):
                self.assertEqual(capability.widget_types, ())

    def test_only_effect_layer_requires_confirmation(self) -> None:
        """安全審査の対象はEffectだけ、という3層分割の意味(レビュー §3.1)を
        構造として固定する。Data/Viewに確認を要求するものが紛れ込むと、
        「何を記録するか」を聞くたびに確認が出る会話になってしまう。"""
        for capability in CAPABILITY_REGISTRY.values():
            if capability.requires_confirmation:
                with self.subTest(capability=capability.id):
                    self.assertIs(capability.layer, CapabilityLayer.EFFECT)

    def test_nearest_supported_alternative_actually_exists_and_is_supported(self) -> None:
        for capability in CAPABILITY_REGISTRY.values():
            if capability.nearest_supported_id is None:
                continue
            with self.subTest(capability=capability.id):
                alternative = CAPABILITY_REGISTRY.get(capability.nearest_supported_id)
                self.assertIsNotNone(alternative)
                self.assertTrue(alternative.supported, "代替として提案する先が未実装では意味が無い")


class TestDetection(unittest.TestCase):
    def test_detects_a_missing_view_capability(self) -> None:
        detected = detect_capabilities("釣った魚を地図で見たい")
        self.assertIn("view.map", [c.id for c in detected])
        self.assertEqual([c.id for c in missing_capabilities(detected)], ["view.map"])

    def test_detects_nothing_for_an_ordinary_request(self) -> None:
        """普通の依頼でMISSINGが出ないこと。誤検出だけが害になる
        (検出漏れは「今までどおりの経路」に落ちるだけ)。"""
        self.assertEqual(missing_capabilities(detect_capabilities("買い物で何買うか忘れちゃう")), ())

    def test_detection_is_deterministic(self) -> None:
        text = "釣果を地図で見て、写真も残したい"
        self.assertEqual(detect_capabilities(text), detect_capabilities(text))

    def test_empty_text_detects_nothing(self) -> None:
        self.assertEqual(detect_capabilities(""), ())


class TestHypothesis(unittest.TestCase):
    def test_no_missing_capability_means_no_hypothesis(self) -> None:
        """レビュー §6の核心: MISSINGが無ければ`None`を返し、既存の
        BUILD経路に一切触れない。この機能は「作れないものを頼まれた
        ときにだけ」会話へ現れる。"""
        self.assertIsNone(build_hypothesis("買い物リストを作りたい"))

    def test_hypothesis_says_what_it_cannot_do_first(self) -> None:
        """作れるふりをしてから実は作れない、という順序にしない。"""
        hypothesis = build_hypothesis("釣った魚を地図で見たい")
        self.assertIsNotNone(hypothesis)
        message = hypothesis.to_message()
        self.assertTrue(message.startswith("地図で見るは、今のForgeではまだ作れません。"), message)
        self.assertIn("代わりに", message)

    def test_hypothesis_offers_the_nearest_buildable_shape(self) -> None:
        hypothesis = build_hypothesis("釣った魚を地図で見たい")
        self.assertIn("view.list", [c.id for c in hypothesis.view])

    def test_effect_only_gaps_do_not_produce_a_conversation_turn(self) -> None:
        """安全判定が先、Capabilityの話は後(`has_buildable_gap`参照)。
        共有は既存のCONFIRM Policyが捕まえているため、Capability層が
        割り込むと確認と仮説が二重に出る。"""
        hypothesis = build_hypothesis("作ったリストを家族にも共有したい")
        self.assertIsNotNone(hypothesis)
        self.assertEqual([c.id for c in hypothesis.missing], ["effect.share"])
        self.assertFalse(has_buildable_gap(hypothesis))


class TestCorrectionClassification(unittest.TestCase):
    def setUp(self) -> None:
        self.hypothesis = build_hypothesis("釣った魚を地図で見たい")

    def test_correction_naming_a_view_targets_the_view_layer(self) -> None:
        self.assertIs(
            classify_correction("違う、色を濃くして分布が見たい", self.hypothesis),
            CorrectionTarget.VIEW,
        )

    def test_correction_naming_data_targets_the_data_layer(self) -> None:
        self.assertIs(
            classify_correction("サイズも記録したい", self.hypothesis), CorrectionTarget.DATA
        )

    def test_misunderstood_problem_is_classified_separately(self) -> None:
        """`PROBLEM`だけは会話を巻き戻す。ここが違うなら、data/viewを
        いくら差し替えても無駄だから(レビュー §3.4)。"""
        self.assertIs(
            classify_correction("そもそもそういうことじゃなくて", self.hypothesis),
            CorrectionTarget.PROBLEM,
        )

    def test_bare_negation_is_unclear_not_a_guess(self) -> None:
        """どこが違うか分からないときに、勝手に推測して作り直さない。"""
        self.assertIs(classify_correction("違う", self.hypothesis), CorrectionTarget.UNCLEAR)

    def test_acceptance_is_not_treated_as_a_correction(self) -> None:
        self.assertIs(classify_correction("それでいいです", self.hypothesis), CorrectionTarget.ACCEPTED)


class TestRevision(unittest.TestCase):
    def test_problem_correction_returns_none_so_the_caller_rewinds(self) -> None:
        hypothesis = build_hypothesis("釣った魚を地図で見たい")
        self.assertIsNone(
            revise_hypothesis(hypothesis, "そもそも違う", CorrectionTarget.PROBLEM)
        )

    def test_revision_replaces_only_the_corrected_layer(self) -> None:
        """「見せ方が違う」と言われたときに、記録する項目まで作り直さない
        ——それは訂正ではなく作り直しであり、ユーザーがまだ言っていない
        ことを勝手に変えることになる。"""
        hypothesis = build_hypothesis("釣った魚のサイズを地図で見たい")
        self.assertEqual([c.id for c in hypothesis.missing], ["view.map"])
        before_data = hypothesis.data
        self.assertTrue(before_data, "この発話ではDataが検出されている前提のテスト")

        revised = revise_hypothesis(hypothesis, "カレンダーで見たい", CorrectionTarget.VIEW)
        self.assertEqual(revised.data, before_data, "Viewの訂正でDataまで作り直さないこと")
        # 訂正が反映されたことは`missing`で確認する。`view`側は、地図も
        # カレンダーも代替が同じ`view.list`であるため**同じ値のままで正しい**
        # (最初これを「変化するはず」と書いてテストが落ち、代替表を見て
        # テスト側の前提が誤りだと分かった)。
        self.assertEqual([c.id for c in revised.missing], ["view.calendar"])

    def test_revision_loop_stops_after_three_rounds(self) -> None:
        """レビュー F2:「違う」ループが終わらない事態を防ぐ。既存の
        `QuestionStrategy` Escalationと同じ考え方。"""
        hypothesis = build_hypothesis("釣った魚を地図で見たい")
        for _ in range(3):
            hypothesis = revise_hypothesis(hypothesis, "カレンダーで見たい", CorrectionTarget.VIEW)
            self.assertIsNotNone(hypothesis)
        self.assertIsNone(revise_hypothesis(hypothesis, "カレンダーで見たい", CorrectionTarget.VIEW))


class TestGoldenConversationSection33(unittest.TestCase):
    """指示書005 §33の実例をGolden Conversationとして固定する。

        ユーザー: 釣果を地図で見たい
        Forge  : 地図は作れない。一覧で見る形なら作れる。
        ユーザー: 違う、色を濃くして分布が見たい(= heatmap)
        Forge  : ヒートマップも作れない。棒グラフなら作れる。

    **この会話の要点は「できないと言えること」である。** 地図もヒート
    マップも実装が無い。それを「できます」と言わずに、毎回できない
    ことを名指しした上で、実際に作れる形を出し続ける。
    """

    def test_full_conversation(self) -> None:
        first = build_hypothesis("釣果を地図で見たい")
        self.assertIsNotNone(first)
        self.assertTrue(has_buildable_gap(first))
        self.assertEqual([c.id for c in first.missing], ["view.map"])
        self.assertIn("地図で見るは、今のForgeではまだ作れません。", first.to_message())

        correction = "違う、色を濃くして分布が見たい"
        target = classify_correction(correction, first)
        self.assertIs(target, CorrectionTarget.VIEW)

        second = revise_hypothesis(first, correction, target)
        self.assertIsNotNone(second)
        self.assertEqual(second.revision, 1)
        # 差し替え先も未実装。**できないものが1つ減ったふりをしない**。
        self.assertEqual([c.id for c in second.missing], ["view.heatmap"])
        message = second.to_message()
        self.assertIn("濃淡で分布を見るは、今のForgeではまだ作れません。", message)
        self.assertIn("棒グラフで見る", message)
        # 実装が無いものを、実装済みとして提案していないこと。
        self.assertNotIn("ヒートマップができる形なら", message)


class TestNoFalseMissingOnExistingSessions(unittest.TestCase):
    """レビュー §8: 既存50セッションに対してMISSINGが誤検出されないこと
    (既存経路を壊していないことの担保)。"""

    def test_only_the_three_sharing_sessions_report_a_gap(self) -> None:
        flagged = {
            session.name
            for session in SCRIPTED_SESSIONS
            for message in session.user_messages
            if build_hypothesis(message) is not None
        }
        self.assertEqual(flagged, {"schedule_shared", "share_1", "risky_1"})

    def test_no_scripted_session_produces_a_conversation_turn(self) -> None:
        """上の3件はいずれもEffectのみなので、会話には割り込まない
        ——つまり50セッションの挙動は**1つも変わらない**。"""
        for session in SCRIPTED_SESSIONS:
            for message in session.user_messages:
                with self.subTest(session=session.name, message=message):
                    self.assertFalse(has_buildable_gap(build_hypothesis(message)))


class TestConversationIntegration(unittest.TestCase):
    """`ConversationEngine`へ実際に接続されていること(§32の
    Vertical Sliceは「型だけ作って繋がっていない」では意味が無い)。"""

    def setUp(self) -> None:
        from app.ai.runtime.conversation_engine import ConversationEngine

        class _AlwaysBuildLLM:
            """Capability層が無ければ即BUILDへ進むProvider。これで
            「Capability層が実際に割り込んでいる」ことだけを分離して測れる。"""

            def complete_structured(self, prompt: str, response_schema: dict) -> dict:
                return {
                    "problem": "釣果を地図で見たい", "known": [], "unknowns": [], "assumptions": [],
                    "confidence": 0.9, "next_action": "build", "question": "",
                    "question_key": "", "build_brief": "釣果を記録する道具",
                    "external_effect": False, "destructive": False,
                }

        self.engine = ConversationEngine(_AlwaysBuildLLM())

    def _session(self, *user_texts: str, asked: tuple[str, ...] = ()) -> ConversationSession:
        return ConversationSession(
            session_id="s1",
            turns=tuple(ConversationTurn(role="user", text=t) for t in user_texts),
            asked_question_keys=asked,
        )

    def test_missing_capability_interrupts_an_otherwise_ready_build(self) -> None:
        result = self.engine.step(self._session("釣果を地図で見たい"))
        self.assertIs(result.action, ConversationAction.ASK)
        self.assertIn("地図で見るは、今のForgeではまだ作れません。", result.question)
        self.assertEqual(result.question_key, "capability_gap:view.map")

    def test_ordinary_request_is_untouched(self) -> None:
        """MISSINGが無ければ、今までどおりBUILDへ進む。"""
        result = self.engine.step(self._session("買い物リストを作りたい"))
        self.assertIs(result.action, ConversationAction.BUILD)

    def test_the_same_gap_is_not_presented_twice(self) -> None:
        result = self.engine.step(
            self._session("釣果を地図で見たい", asked=("capability_gap:view.map",))
        )
        self.assertIs(result.action, ConversationAction.BUILD)

    def test_correction_presents_the_revised_hypothesis_once(self) -> None:
        """訂正で不足が変わると別のkeyになるため、訂正後の仮説は
        ちゃんと1回だけ提示される(§33のGolden Conversationの2ターン目)。"""
        result = self.engine.step(self._session(
            "釣果を地図で見たい", "違う、色を濃くして分布が見たい",
            asked=("capability_gap:view.map",),
        ))
        self.assertIs(result.action, ConversationAction.ASK)
        self.assertEqual(result.question_key, "capability_gap:view.heatmap")

    def test_presentation_stops_after_three_rounds(self) -> None:
        """レビュー F2: 無理に正解へ辿り着こうとせず、通常の会話へ戻す。"""
        result = self.engine.step(self._session(
            "地図で見たい",
            asked=(
                "capability_gap:view.calendar",
                "capability_gap:view.heatmap",
                "capability_gap:view.line_chart",
            ),
        ))
        self.assertIs(result.action, ConversationAction.BUILD)


if __name__ == "__main__":
    unittest.main()
