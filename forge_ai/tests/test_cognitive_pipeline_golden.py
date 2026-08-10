"""Golden Test(FORGE-MILESTONE-007第一段階)。

`golden_cognitive/*.json`に、CEO指定の6例に対する`run_cognitive_pipeline()`
の出力の主要な特徴(Domain・Template・画面数・データ実体・Empty State/
Validationの有無・Critic結果)を凍結し、再実行結果と比較する
(`backend/tests/test_golden_mock_generator.py`と同じ「凍結して差分を
検出する」手法)。
"""

from __future__ import annotations

import json
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from forge_ai.core.pipeline import run_cognitive_pipeline  # noqa: E402
from forge_ai.core.orchestration.outcomes import CognitivePipelineSuccess  # noqa: E402

_GOLDEN_DIR = os.path.join(os.path.dirname(__file__), "golden_cognitive")

CASES: dict[str, str] = {
    "01_shopping": "買い物リストを作りたい",
    "02_task_management": "今日のタスクを管理したい",
    "03_diary": "日記を記録したい",
    "04_survey": "簡単なアンケートを作りたい",
    "05_schedule": "予定を管理したい",
    "06_inventory": "在庫を管理したい",
}


def _load_golden(name: str) -> dict:
    with open(os.path.join(_GOLDEN_DIR, f"{name}.json"), encoding="utf-8") as f:
        return json.load(f)


def _summarize(outcome: CognitivePipelineSuccess, text: str) -> dict:
    ctx = outcome.context
    return {
        "input": text,
        "domain": ctx.domain_classification.primary_domain.category.value,
        "domain_confidence": round(ctx.domain_classification.confidence, 2),
        "template": ctx.template_selection.template,
        "screen_count": len(ctx.plan.screens),
        "data_entities": sorted(ctx.plan.data_entities),
        "has_empty_state": all(bool(s.empty_state_message) for s in ctx.plan.screens),
        "has_validation": all(bool(s.validation_rules) for s in ctx.plan.screens),
        "critic_release_ready": ctx.critic_report.release_ready,
        "ir_valid_screens": len(outcome.ir.screens),
        "revision_attempt": ctx.revision_attempt,
    }


class TestCognitivePipelineGolden(unittest.TestCase):
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
                        f"forge_ai/tests/golden_cognitive/{name}.json を更新してください。",
                )

    def test_all_six_cases_produce_distinct_domains(self) -> None:
        """6例が、それぞれ異なるDomainへ正しく分類されることを確認する
        (誤って全部Genericへ落ちていないか等の粗い健全性チェック)。"""
        domains = set()
        for text in CASES.values():
            outcome = run_cognitive_pipeline(text)
            assert isinstance(outcome, CognitivePipelineSuccess)
            domains.add(outcome.context.domain_classification.primary_domain.category.value)
        self.assertEqual(len(domains), 6, f"6例が別々のDomainに分類されるべきだが、実際は{domains}")

    def test_pipeline_is_deterministic_across_repeated_calls(self) -> None:
        """Rule-Based実装は決定的であるべき(同じ入力から常に同じ出力)。"""
        for name, text in CASES.items():
            with self.subTest(case=name):
                first = run_cognitive_pipeline(text)
                second = run_cognitive_pipeline(text)
                assert isinstance(first, CognitivePipelineSuccess)
                assert isinstance(second, CognitivePipelineSuccess)
                self.assertEqual(_summarize(first, text), _summarize(second, text))


if __name__ == "__main__":
    unittest.main()
