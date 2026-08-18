"""Semantic Design Critic の検査(FORGE-R1-CLOSURE-015 §3、2026-08-17)。

---

## このファイルが要る理由（配線破壊試験で判明した）

§3を実装した直後に配線破壊試験をしたところ、**Criticへ軸を合流させる
処理を外しても、テストが1件も落ちなかった**。決定のTraceだけを見て
いて、`CriticReport`そのものを誰も検査していなかったためである。

つまり「Criticが評価している」と報告できる状態ではなかった。
`CLAUDE.md` §3が言う置物そのものである。

## 何を検査するか

**「roleがある」ことを評価しない**、が要点である。

```
❌ style_roleが存在する → PASS
```

では、10個すべてが`metric.primary`でもPASSする。それは
「一番大事なものが10個ある」という、階層が消えた状態である。

Criticが**悪いDesignを悪いと言えること**を確かめる。
"""

from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))  # forge_ai/ はrepoルート直下

from forge_ai.core.critic.semantic_design_critic import evaluate_semantic_design  # noqa: E402
from forge_ai.core.pipeline import run_cognitive_pipeline  # noqa: E402


def _document(children: list[dict]) -> dict:
    return {
        "version": "1.12",
        "initial_screen_id": "s1",
        "screens": [{
            "id": "s1", "title": "画面",
            "state": {},
            "body": {"type": "column", "id": "root", "children": children},
        }],
    }


def _metric(widget_id: str, role: str) -> dict:
    return {"type": "metric_view", "id": widget_id, "state_ref": "records",
            "value_field": "v", "aggregate": "sum", "style_role": role}


class TestTheCriticSeesTheHierarchyNotJustThePresence(unittest.TestCase):
    """**§3.2の本体。** roleの存在ではなく階層を見る。"""

    def test_a_sound_hierarchy_passes(self) -> None:
        finding = evaluate_semantic_design(_document([
            {"type": "section_header", "id": "h", "title": "見出し",
             "style_role": "text.headline"},
            _metric("hero", "metric.primary"),
            _metric("sub", "metric.secondary"),
        ]))
        self.assertEqual(finding.issues, ())
        self.assertEqual(finding.score, 1.0)

    def test_ten_primary_metrics_do_not_pass(self) -> None:
        """**style_roleは全部に付いているのに失敗する。**

        これが「あるだけ」を弾くという判定である。
        """
        finding = evaluate_semantic_design(_document(
            [_metric(f"m{i}", "metric.primary") for i in range(10)]
        ))
        self.assertTrue(finding.has_blocking_issue, "主KPIが10個あるのに通ってしまう")
        self.assertIn("metric.primary", finding.evidence.duplicated_singular_roles)
        self.assertLess(finding.score, 1.0)

    def test_two_primary_actions_do_not_pass(self) -> None:
        finding = evaluate_semantic_design(_document([
            {"type": "button", "id": "a", "label": "保存", "style_role": "button.primary",
             "action": {"type": "go_back"}},
            {"type": "button", "id": "b", "label": "送信", "style_role": "button.primary",
             "action": {"type": "go_back"}},
        ]))
        self.assertIn("button.primary", finding.evidence.duplicated_singular_roles)
        self.assertTrue(finding.has_blocking_issue)

    def test_a_document_without_any_role_is_blocking(self) -> None:
        finding = evaluate_semantic_design(_document([
            {"type": "section_header", "id": "h", "title": "見出し"},
        ]))
        self.assertTrue(finding.has_blocking_issue)

    def test_missing_roles_on_structural_widgets_are_reported(self) -> None:
        finding = evaluate_semantic_design(_document([
            _metric("hero", "metric.primary"),
            {"type": "section_header", "id": "h1", "title": "A"},
            {"type": "section_header", "id": "h2", "title": "B"},
            {"type": "section_header", "id": "h3", "title": "C"},
        ]))
        self.assertLess(finding.evidence.role_coverage_ratio, 0.8)
        self.assertTrue(any(i.severity == "medium" for i in finding.issues))

    def test_lifting_every_surface_is_reported(self) -> None:
        """**全部を持ち上げると階層が消える。**"""
        finding = evaluate_semantic_design(_document([
            {"type": "card", "id": f"c{i}", "style_role": "surface.elevated", "children": []}
            for i in range(5)
        ]))
        self.assertEqual(finding.evidence.elevated_surface_count, 5)
        self.assertTrue(finding.issues)

    def test_mixing_finance_and_state_colours_is_reported(self) -> None:
        """**支出はエラーではない。** 兼用していれば言う。"""
        finding = evaluate_semantic_design(_document([
            _metric("income", "finance.income"),
            {"type": "text", "id": "err", "value": "x", "style_role": "state.danger"},
        ]))
        self.assertTrue(finding.evidence.finance_state_conflict)
        self.assertTrue(finding.issues)


class TestTheCriticReportCarriesTheAxis(unittest.TestCase):
    """**本番のCriticReportへ合流していること。**

    配線破壊試験で、合流を外しても何も落ちない状態だったので追加した。
    """

    def _report(self, need: str):  # noqa: ANN202
        return run_cognitive_pipeline(need).context.critic_report

    def test_the_axis_is_listed_as_evaluated(self) -> None:
        report = self._report("家計の支出をカテゴリ別に管理したい")
        self.assertIn("semantic_design", report.evaluated_axes)
        self.assertNotIn("semantic_design", report.unevaluated_axes)

    def test_the_coverage_ratio_counts_the_new_axis(self) -> None:
        report = self._report("家計の支出をカテゴリ別に管理したい")
        self.assertAlmostEqual(report.coverage_ratio, len(report.evaluated_axes) / 14)

    def test_the_score_reflects_the_new_axis(self) -> None:
        """軸を足したのにscoreへ効いていない＝合流していない。"""
        report = self._report("家計の支出をカテゴリ別に管理したい")
        self.assertGreater(report.score, 0.0)
        self.assertLessEqual(report.score, 1.0)
        # 11軸の平均になっているはず（10軸の平均ではない）。
        self.assertEqual(len(report.evaluated_axes), 11)


class TestABrokenHierarchyIsNotReleaseReady(unittest.TestCase):
    """**Criticが悪いDesignを悪いと言えること**(§20-9)。"""

    def test_a_blocking_semantic_issue_clears_release_ready(self) -> None:
        import dataclasses

        from forge_ai.core.orchestration.pipeline_orchestrator import _merged_critic_report

        healthy = run_cognitive_pipeline("家計の支出をカテゴリ別に管理したい").context.critic_report
        self.assertTrue(healthy.release_ready)

        broken = evaluate_semantic_design(_document(
            [_metric(f"m{i}", "metric.primary") for i in range(3)]
        ))
        merged = _merged_critic_report(dataclasses.replace(healthy), broken)
        self.assertFalse(
            merged.release_ready,
            "意味の階層が壊れているのにrelease_readyのまま",
        )


if __name__ == "__main__":
    unittest.main()
