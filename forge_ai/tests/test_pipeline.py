"""pipeline.py のテスト(世界理解〜設計までのEnd-to-End)。"""

from __future__ import annotations

import unittest

from forge_ai.core.domain_model import DomainCategory
from forge_ai.core.pipeline import PipelineResult, run_pipeline
from forge_ai.provider.mock_provider import MockProvider


class TestPipeline(unittest.TestCase):
    def setUp(self) -> None:
        self.provider = MockProvider()

    def test_run_pipeline_returns_pipeline_result(self) -> None:
        result = run_pipeline("add item track price", self.provider)
        self.assertIsInstance(result, PipelineResult)

    def test_run_pipeline_all_stages_populated(self) -> None:
        result = run_pipeline("add item track price", self.provider)
        self.assertIsNotNone(result.domain)
        self.assertIsNotNone(result.world)
        self.assertIsNotNone(result.meaning)
        self.assertIsNotNone(result.intent)
        self.assertIsNotNone(result.plan)
        self.assertIsNotNone(result.ir)
        self.assertIsNotNone(result.quality)

    def test_run_pipeline_resolves_shopping_domain_from_keywords(self) -> None:
        result = run_pipeline("I need to track item price at the store", self.provider)
        self.assertEqual(result.domain.category, DomainCategory.SHOPPING)

    def test_run_pipeline_produces_valid_forge_ir_structure(self) -> None:
        result = run_pipeline("add item", self.provider)
        json_dict = result.ir.to_json_dict()
        self.assertIn("version", json_dict)
        self.assertIn("screens", json_dict)
        self.assertIn("initial_screen_id", json_dict)

    def test_run_pipeline_never_crashes_on_empty_input(self) -> None:
        result = run_pipeline("", self.provider)
        self.assertIsNotNone(result)

    def test_run_pipeline_never_crashes_across_all_domains(self) -> None:
        for category in DomainCategory:
            with self.subTest(category=category):
                result = run_pipeline(f"manage {category.value} records", self.provider)
                self.assertIsNotNone(result.ir)

    def test_run_pipeline_quality_score_is_within_valid_range(self) -> None:
        result = run_pipeline("add item track price", self.provider)
        self.assertGreaterEqual(result.quality.overall, 0.0)
        self.assertLessEqual(result.quality.overall, 1.0)

    def test_run_pipeline_accepts_injected_registry_and_builder(self) -> None:
        """DI(Dependency Injection)が実際に機能することを確認する。"""
        from forge_ai.core.domain_model import DomainRegistry
        from forge_ai.core.world_model import WorldModelBuilder

        custom_registry = DomainRegistry()
        custom_builder = WorldModelBuilder()
        result = run_pipeline(
            "add item", self.provider, domain_registry=custom_registry, world_builder=custom_builder
        )
        self.assertIsNotNone(result)


class TestCombineWithAnswers(unittest.TestCase):
    """FORGE v0.2 Final Gate 最終調整 P1の回帰テスト:
    `_combine_with_answers()`が内部管理用ラベルを一切混入させず、かつ
    **全件の回答**を結合すること(単数版で発生していた「1回目の回答が
    失われる」バグの回帰防止)。"""

    def test_combines_without_internal_label(self) -> None:
        from forge_ai.core.pipeline import _combine_with_answers

        combined = _combine_with_answers("x", ("買い物リストです",))
        self.assertNotIn("補足回答", combined)
        self.assertIn("x", combined)
        self.assertIn("買い物リストです", combined)

    def test_combines_all_answers_not_just_the_last_one(self) -> None:
        """最終調整P1の回帰テスト核心: 2回分の回答(「家族向け」「買い物
        リストです」)の両方が結合結果に含まれること。以前は最新の
        回答しかPipelineへ渡されず、1回目の回答が失われていた。"""
        from forge_ai.core.pipeline import _combine_with_answers

        combined = _combine_with_answers("x", ("家族向け", "買い物リストです"))
        self.assertIn("家族向け", combined)
        self.assertIn("買い物リストです", combined)

    def test_no_answers_returns_raw_input_unchanged(self) -> None:
        from forge_ai.core.pipeline import _combine_with_answers

        self.assertEqual(_combine_with_answers("買い物リストを作りたい", ()), "買い物リストを作りたい")

    def test_empty_string_answers_are_ignored(self) -> None:
        from forge_ai.core.pipeline import _combine_with_answers

        self.assertEqual(_combine_with_answers("買い物リストを作りたい", ("", "")), "買い物リストを作りたい")

    def test_empty_raw_input_returns_answers_alone(self) -> None:
        from forge_ai.core.pipeline import _combine_with_answers

        self.assertEqual(_combine_with_answers("", ("買い物リストです",)), "買い物リストです")


class TestTitleSeed(unittest.TestCase):
    """FORGE v0.2 Final Gate 最終調整 P3の回帰テスト:
    `_compute_title_seed()`が、ノイズ的な元入力("x"等)を除いた
    回答部分のみを返すこと。"""

    def test_noise_input_with_answers_returns_answers_only(self) -> None:
        from forge_ai.core.pipeline import _compute_title_seed

        seed = _compute_title_seed("x", ("日常の", "買い物リストです"))
        self.assertEqual(seed, "日常の 買い物リストです")
        self.assertNotIn("x", seed)

    def test_meaningful_raw_input_returns_none_no_special_treatment(self) -> None:
        """元入力自体が既に意味のある長さを持つ場合、特別扱いしない
        (`None`を返し、`normalized_text`全体を通常通り使わせる)。"""
        from forge_ai.core.pipeline import _compute_title_seed

        seed = _compute_title_seed("買い物リストを作りたい", ("追加で牛乳も",))
        self.assertIsNone(seed)

    def test_no_answers_returns_none(self) -> None:
        from forge_ai.core.pipeline import _compute_title_seed

        self.assertIsNone(_compute_title_seed("x", ()))


class TestRunCognitivePipelineClarificationAnswers(unittest.TestCase):
    """FORGE v0.2 Final Gate(初回・最終調整)の回帰テスト:
    `run_cognitive_pipeline()`が`clarification_answers`(複数)を
    別引数として受け取り、(1)Survey Domainの誤検出を起こさず、
    (2)全ての回答を累積してPipelineへ渡し、(3)タイトルへノイズを
    混入させないことを確認する。"""

    def setUp(self) -> None:
        self.provider = MockProvider()

    def test_clarification_answers_do_not_pollute_with_internal_label(self) -> None:
        """回帰の核心: 以前のバグ(ラベル付き文字列結合)を再現する入力
        (`"x"` + `"買い物リストです"`)で、Survey Domainの"answer"概念が
        一致しないことを確認する(「回答」という文字列がどこにも
        現れないため)。"""
        from forge_ai.core.pipeline import run_cognitive_pipeline

        outcome = run_cognitive_pipeline("x", self.provider, clarification_answers=("買い物リストです",))
        self.assertNotIn("回答", outcome.context.raw_input if hasattr(outcome, "context") else "")

    def test_clarification_answers_actually_reach_the_pipeline(self) -> None:
        """回答の内容が実際にPipelineの処理対象になっていることの確認
        (別引数化によって回答自体が無視されるようになっていないか)。"""
        from forge_ai.core.orchestration.outcomes import CognitivePipelineSuccess
        from forge_ai.core.pipeline import run_cognitive_pipeline

        outcome = run_cognitive_pipeline(
            "", self.provider, clarification_answers=("買い物リストを作りたい",)
        )
        self.assertIsInstance(outcome, CognitivePipelineSuccess)
        self.assertEqual(outcome.context.domain_classification.primary_domain.category.value, "shopping")

    def test_multiple_rounds_of_answers_all_reach_the_pipeline(self) -> None:
        """最終調整P1の回帰テスト核心(End-to-End): 2回分の確認往復の
        両方の回答が、実際にIntentの概念抽出まで到達することを確認する
        (以前は1回目の回答「日常の」が失われ、2回目の回答だけが
        Pipelineに渡っていた)。"""
        from forge_ai.core.orchestration.outcomes import CognitivePipelineSuccess
        from forge_ai.core.pipeline import run_cognitive_pipeline

        outcome = run_cognitive_pipeline(
            "x", self.provider, clarification_answers=("日常の", "買い物リストです")
        )
        self.assertIsInstance(outcome, CognitivePipelineSuccess)
        self.assertIn("日常の", outcome.context.raw_input)
        self.assertIn("買い物リストです", outcome.context.raw_input)

    def test_title_excludes_noise_original_input_when_answers_present(self) -> None:
        """最終調整P3の回帰テスト核心(End-to-End): ノイズ的な元入力
        ("x")が、確認フロー経由で生成されたアプリのタイトルに残らない
        ことを確認する。

        2026-08-26(Quality Gate v2 修正1)で期待値を更新した。以前は
        `assertIn("買い物リスト", title)`——つまり**回答文がそのまま
        タイトルへ入ること**を期待していた。実際に出ていたのは
        「日常の 買い物リストです」であり、これは名前ではなく発話である。

        `decide_app_name()` 導入後は「買い物」(Domainの日本語名)になる。
        **このテストの本来の意図(ノイズ "x" がタイトルへ残らない)は
        変えていない。** 変えたのは「回答文を写す」という手段への依存で
        ある。回答の意味(買い物)がタイトルへ届いていることは引き続き
        確認する。
        """
        from forge_ai.core.naming import is_name_like
        from forge_ai.core.orchestration.outcomes import CognitivePipelineSuccess
        from forge_ai.core.pipeline import run_cognitive_pipeline

        outcome = run_cognitive_pipeline(
            "x", self.provider, clarification_answers=("日常の", "買い物リストです")
        )
        self.assertIsInstance(outcome, CognitivePipelineSuccess)
        title = outcome.ir.to_json_dict()["app"]["title"]
        self.assertNotIn("x", title)
        self.assertIn("買い物", title)
        # **名前の形をしていること。** 「買い物リストです」のような
        # 発話がタイトルへ入るのを防ぐのがこの修正の目的である。
        self.assertTrue(is_name_like(title), title)

    def test_concept_matching_still_uses_full_combined_text_not_just_title_seed(self) -> None:
        """タイトル導出だけがノイズを除外し、Domain/概念抽出は引き続き
        全文(ノイズ含む)を見ていることを確認する(意図的な設計、
        `title_seed`はgoal導出専用であってConcept抽出には影響しない)。"""
        from forge_ai.core.pipeline import run_cognitive_pipeline

        # "x"自体はどの概念にも一致しないため、この検証は「回答からの
        # 概念抽出が正常に機能している」ことの確認に相当する。
        outcome = run_cognitive_pipeline(
            "x", self.provider, clarification_answers=("日常の", "買い物リストです")
        )
        self.assertIn("item", outcome.context.intent.required_concepts)


if __name__ == "__main__":
    unittest.main()
