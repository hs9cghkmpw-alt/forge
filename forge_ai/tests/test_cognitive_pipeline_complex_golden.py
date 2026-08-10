"""Golden Test — 複雑入力6例(FORGE-MILESTONE-007 Phase 1.2)。

`golden_cognitive_complex/*.json`に、CEO指定の複雑入力6例に対する
`run_cognitive_pipeline()`の出力(Domain・Template・Meaningの主要
Actor/Entity/Action/Condition・Requirement反映・Criticのrelease_ready・
Decision Trace段階)を凍結し、再実行結果と比較する。
"""

from __future__ import annotations

import json
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from forge_ai.core.pipeline import run_cognitive_pipeline  # noqa: E402
from forge_ai.core.orchestration.outcomes import CognitivePipelineSuccess  # noqa: E402

_GOLDEN_DIR = os.path.join(os.path.dirname(__file__), "golden_cognitive_complex")

CASES: dict[str, str] = {
    "01_shared_shopping": "家族で共有できる買い物リストを作りたい",
    "02_photo_mood_diary": "写真と気分を記録できる日記がほしい",
    "03_deadline_priority_task": "期限と優先度を設定できるタスク管理アプリ",
    "04_low_stock_alert": "在庫が少なくなったら分かるようにしたい",
    "05_survey_results_list": "回答後に結果を一覧で確認できるアンケート",
    "06_weekly_monday_schedule": "毎週月曜日の予定を管理したい",
}


def _load_golden(name: str) -> dict:
    with open(os.path.join(_GOLDEN_DIR, f"{name}.json"), encoding="utf-8") as f:
        return json.load(f)


def _summarize(outcome: CognitivePipelineSuccess, text: str) -> dict:
    ctx = outcome.context
    meaning = ctx.meaning
    return {
        "input": text,
        "domain": ctx.domain_classification.primary_domain.category.value,
        "template": ctx.template_selection.template,
        "meaning_actors": sorted(meaning.actors),
        "meaning_entities": sorted(meaning.entities),
        "meaning_actions": sorted(meaning.actions),
        "meaning_constraints": sorted(meaning.constraints),
        "meaning_temporal_conditions": sorted(meaning.temporal_conditions),
        "meaning_state_conditions": sorted(meaning.state_conditions),
        "data_entities": sorted(ctx.plan.data_entities),
        "required_actions": sorted(ctx.plan.screens[0].required_actions),
        "mandatory_unassigned_count": sum(
            1 for r in ctx.requirements.requirements
            if r.mandatory and r.description in ctx.plan.unassigned_requirements
        ),
        "critic_release_ready": ctx.critic_report.release_ready,
        "decision_trace_stages": [dt.stage for dt in ctx.decision_trace],
    }


class TestCognitivePipelineComplexInputGolden(unittest.TestCase):
    def test_all_golden_files_exist(self) -> None:
        for name in CASES:
            self.assertTrue(os.path.isfile(os.path.join(_GOLDEN_DIR, f"{name}.json")), f"golden file が無い: {name}")

    def test_regenerated_output_matches_golden_exactly(self) -> None:
        for name, text in CASES.items():
            with self.subTest(case=name):
                outcome = run_cognitive_pipeline(text)
                self.assertIsInstance(outcome, CognitivePipelineSuccess, f"{text!r}がSUCCESSにならなかった")
                actual = _summarize(outcome, text)
                expected = _load_golden(name)
                self.assertEqual(
                    actual, expected,
                    msg=f"'{name}'の生成結果がgolden fileと一致しません。意図した変更であれば"
                        f"forge_ai/tests/golden_cognitive_complex/{name}.json を更新してください。",
                )

    def test_all_cases_have_no_mandatory_unassigned_requirements(self) -> None:
        """複雑入力6例全てで、Meaning由来の必須情報が実際にPlanへ反映され、
        未割当の必須要件が残っていないことを確認する(CEO指示「未反映の
        mandatory情報がある場合はrelease_ready=Falseとしてください」の
        逆、つまり正しく反映されればrelease_ready=Trueで完了することの
        確認)。"""
        for name, text in CASES.items():
            with self.subTest(case=name):
                outcome = run_cognitive_pipeline(text)
                assert isinstance(outcome, CognitivePipelineSuccess)
                mandatory_unassigned = [
                    r for r in outcome.context.requirements.requirements
                    if r.mandatory and r.description in outcome.context.plan.unassigned_requirements
                ]
                self.assertEqual(mandatory_unassigned, [], f"{name}: 未割当の必須要件が残っている")

    def test_pipeline_is_deterministic_across_repeated_calls(self) -> None:
        for name, text in CASES.items():
            with self.subTest(case=name):
                first = run_cognitive_pipeline(text)
                second = run_cognitive_pipeline(text)
                assert isinstance(first, CognitivePipelineSuccess)
                assert isinstance(second, CognitivePipelineSuccess)
                self.assertEqual(_summarize(first, text), _summarize(second, text))


if __name__ == "__main__":
    unittest.main()
