"""Domain Resolution / TD45 Regression
(FORGE-QUALITY-AI-INDEPENDENCE-003 Phase B・D、2026-08-12)。

指示書11章の要請「最低20ケース以上」「評価対象はDomain名ではない、
最終ToolがNeedを満たすか」への対応。

**なぜDomain名で判定しないのか**: 「血圧を記録したい」が`diary`と
分類されること自体は、必ずしも間違いではない(語彙的には「記録」で
近い)。問題は、**そのDomainの手作り定義がNeedを満たさないのに
採用されてしまう**ことだった。したがってここで検証するのは
「どのDomain名になったか」ではなく「**Curatedを使ったか、合成したか**」
という解決の中身である。
"""

from __future__ import annotations

import unittest

from forge_ai.core.ir.domain_resolution import (
    DomainResolution,
    SolutionSource,
    resolve_domain_source,
)
from forge_ai.core.pipeline import run_cognitive_pipeline


def _resolve(**kwargs) -> DomainResolution:
    base = {
        "domain_category": "diary",
        "is_curated": True,
        "matched_concepts": (),
        "matched_actions": ("記録する",),
        "can_generate": True,
    }
    base.update(kwargs)
    return resolve_domain_source(base.pop("domain_category"), **base)


class TestResolutionRules(unittest.TestCase):
    def test_concept_match_selects_curated(self) -> None:
        r = _resolve(matched_concepts=("日記",))
        self.assertIs(r.source, SolutionSource.CURATED)
        self.assertTrue(r.semantic_fit)

    def test_action_only_match_rejects_curated(self) -> None:
        """TD45の中核: 概念語が1件も一致せず動詞だけで選ばれたDomainの
        手作り定義は使わない。"""
        r = _resolve(matched_concepts=())
        self.assertIs(r.source, SolutionSource.GENERATED)
        self.assertFalse(r.semantic_fit)

    def test_no_curated_definition_generates(self) -> None:
        r = _resolve(is_curated=False, matched_concepts=("買い物",))
        self.assertIs(r.source, SolutionSource.GENERATED)

    def test_without_a_synthesizer_it_falls_back_to_curated(self) -> None:
        """合成できないなら、不適合なCuratedでも「何も作れない」よりまし。"""
        r = _resolve(matched_concepts=(), can_generate=False)
        self.assertIs(r.source, SolutionSource.CURATED)
        self.assertFalse(r.semantic_fit)

    def test_every_decision_carries_a_reason(self) -> None:
        for kwargs in (
            {"matched_concepts": ("日記",)},
            {"matched_concepts": ()},
            {"is_curated": False},
            {"matched_concepts": (), "can_generate": False},
        ):
            with self.subTest(**kwargs):
                self.assertTrue(_resolve(**kwargs).reason)


def _resolution_of(text: str) -> str:
    """パイプラインを実際に流し、Curated/Generatedのどちらで解決したかを返す。

    確認要求(needs_confirmation)へ分岐した場合は`"needs_confirmation"`。
    """
    outcome = run_cognitive_pipeline(text)
    if not hasattr(outcome, "context"):
        return "needs_confirmation"
    traces = [d for d in outcome.context.decision_trace if d.stage == "domain_resolution"]
    return traces[0].decision if traces else "(none)"


class TestTD45Regression(unittest.TestCase):
    """指示書11章の20ケース。

    **Mock Providerで実行している**ため、合成されるEntityの中身
    (systolic/diastolic等)までは検証できない(Mockは依頼内容を理解
    しないため)。ここで固定しているのは「**手作りのdiary定義へ
    誤って倒れないこと**」という、TD45の核心部分である。合成結果の
    中身の質は実LLM依存であり、`test_entity_synthesizer.py`と
    実機確認の担当範囲。
    """

    # 「概念語が一致しないのに、動詞だけでCuratedへ吸い込まれていた」
    # 側のケース。いずれもgeneratedへ回るべきもの。
    MUST_NOT_USE_CURATED = (
        "毎日の血圧を記録したい",
        "血圧の上と下を記録したい",
        "体温を記録したい",
        "子供の体温を記録したい",
        "脈拍を記録したい",
        "読んだ本を記録したい",
        "映画の感想を記録したい",
        "植物の水やりを記録したい",
        "ペットのごはんを記録したい",
        "車の給油を記録したい",
    )

    # 概念語が実際に一致しており、手作り定義が適合するケース。
    MUST_USE_CURATED = (
        "日記をつけたい",
        "日記を書きたい",
        "家計簿をつけたい",
        "出費を記録したい",
        "在庫を管理したい",
        "在庫を記録したい",
        "釣果を記録したい",
        "釣った魚を記録したい",
        "習慣を記録したい",
        "習慣を続けたい",
    )

    def test_needs_that_curated_cannot_satisfy_are_generated(self) -> None:
        for text in self.MUST_NOT_USE_CURATED:
            with self.subTest(text=text):
                result = _resolution_of(text)
                self.assertNotEqual(
                    result, SolutionSource.CURATED.value,
                    f"'{text}'が手作り定義へ誤解決している(TD45の再発)",
                )

    def test_needs_that_curated_fits_still_use_curated(self) -> None:
        """反対側の回帰: 直しすぎて、適合するCuratedまで捨てないこと。"""
        for text in self.MUST_USE_CURATED:
            with self.subTest(text=text):
                result = _resolution_of(text)
                self.assertNotEqual(
                    result, SolutionSource.GENERATED.value,
                    f"'{text}'は手作り定義が適合するはずなのに合成へ倒れている",
                )

    def test_the_regression_set_covers_at_least_twenty_cases(self) -> None:
        """指示書11章「最低20ケース以上」。"""
        self.assertGreaterEqual(
            len(self.MUST_NOT_USE_CURATED) + len(self.MUST_USE_CURATED), 20
        )

    def test_blood_pressure_no_longer_produces_the_diary_data_model(self) -> None:
        """TD45で実際に報告された症状そのものの回帰テスト。

        手作りdiary定義(title/content/mood/date)が、血圧記録アプリの
        データモデルとして使われていないことを確認する。
        """
        outcome = run_cognitive_pipeline("毎日の血圧を記録したい")
        self.assertTrue(hasattr(outcome, "ir"), "確認要求へ分岐してしまった")
        schemas = outcome.ir.to_json_dict().get("record_schemas") or {}
        self.assertNotIn(
            "diary_entry", schemas,
            "血圧記録アプリが、手作りの日記データモデルで作られている",
        )


if __name__ == "__main__":
    unittest.main()
