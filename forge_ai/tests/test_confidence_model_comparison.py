"""Task042-2 Phase B — Shadow Judgment 境界値テスト + 比較レポート。

CEO指示に基づき、以下2種類のテストを実装する。

1. 境界値専用テスト(`TestShadowJudgmentBoundaryValues`): overall_
   confidenceの閾値(0.5・0.8)付近、および各信号の高低の組み合わせを
   個別に構築し、`ShadowJudgment`の計算結果(`comparison_category`・
   `risk_classification`)を検証する。
2. Golden Test全43件(v0.3の37件+複雑入力6件)を実際に`run_cognitive_
   pipeline()`へ通し、現行モデルとShadowモデルを比較するレポートを
   生成する(`TestShadowJudgmentGoldenComparisonReport`)。

**重要(CEO指示の繰り返し)**: このファイルのテストは、Shadow側の
結果を理由に既存のGolden Test期待値(Success/Confirmation・Domain・
Template等)を変更する根拠には**しない**。比較レポートは、一致/不一致
の実態を記録するためのものであり、「不一致が0件であること」を
アサーションでは強制しない。
"""

from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from forge_ai.core.domain_model import DomainCategory, DomainRegistry  # noqa: E402
from forge_ai.core.intent_model import Intent  # noqa: E402
from forge_ai.core.orchestration.cognitive_types import DomainCandidate, DomainClassification  # noqa: E402
from forge_ai.core.orchestration.confidence import ThresholdsUsed, compute_shadow_judgment  # noqa: E402


def _intent(confidence: float) -> Intent:
    return Intent(goal="x", required_concepts=("item",), required_actions=(), constraints=(), confidence=confidence)


def _classification(*, confidence: float, score_margin: float) -> DomainClassification:
    registry = DomainRegistry()
    domain = registry.get(DomainCategory.SHOPPING)
    return DomainClassification(
        primary_domain=domain,
        candidates=(
            DomainCandidate(
                domain=domain, raw_score=2.0, normalized_score=confidence,
                matched_concepts=("item",), matched_actions=(),
            ),
        ),
        confidence=confidence,
        score_margin=score_margin,
        rationale="test",
    )


class TestShadowJudgmentBoundaryValues(unittest.TestCase):
    """CEO指示「境界値専用テスト」。overall_confidence(= intent_
    confidence・domain_confidenceの平均)がちょうど閾値付近になるよう、
    意図的に構成した入力を使う。浮動小数点の丸め誤差を避けるため、
    平均がちょうど境界値になる組み合わせ(両方同じ値)を選んでいる。
    """

    def test_overall_confidence_just_below_0_49(self) -> None:
        judgment = compute_shadow_judgment(_intent(0.49), _classification(confidence=0.49, score_margin=0.5))
        self.assertAlmostEqual(judgment.overall_confidence, 0.49)
        self.assertTrue(judgment.shadow_should_escalate, "0.49は0.5未満のためescalateする")

    def test_overall_confidence_exactly_0_50(self) -> None:
        judgment = compute_shadow_judgment(_intent(0.50), _classification(confidence=0.50, score_margin=0.5))
        self.assertAlmostEqual(judgment.overall_confidence, 0.50)
        self.assertFalse(judgment.shadow_should_escalate, "0.50は閾値以上のためescalateしない(閾値は`<`で判定)")

    def test_overall_confidence_0_79_is_medium_band(self) -> None:
        judgment = compute_shadow_judgment(_intent(0.79), _classification(confidence=0.79, score_margin=0.5))
        self.assertAlmostEqual(judgment.overall_confidence, 0.79)
        self.assertFalse(judgment.shadow_should_escalate)
        self.assertEqual(judgment.risk_classification, "medium_band")

    def test_overall_confidence_0_80_is_high_confidence(self) -> None:
        judgment = compute_shadow_judgment(_intent(0.80), _classification(confidence=0.80, score_margin=0.5))
        self.assertAlmostEqual(judgment.overall_confidence, 0.80)
        self.assertFalse(judgment.shadow_should_escalate)
        self.assertEqual(
            judgment.risk_classification, "high_confidence",
            "0.80はMEDIUM帯の上限(0.8)ちょうどであり、shadow_medium_band_upperは`<`判定のため含まれない",
        )

    def test_intent_low_domain_high(self) -> None:
        judgment = compute_shadow_judgment(_intent(0.3), _classification(confidence=0.9, score_margin=0.5))
        self.assertAlmostEqual(judgment.overall_confidence, 0.6)
        self.assertTrue(judgment.legacy_should_escalate, "現行モデルはintent_confidence<0.5だけでescalateする")
        self.assertFalse(judgment.shadow_should_escalate, "Shadowモデルは平均0.6のためescalateしない")
        self.assertEqual(judgment.comparison_category, "legacy_escalate_shadow_continue")
        self.assertEqual(judgment.risk_classification, "intent_confidence_only_low")

    def test_intent_high_domain_low(self) -> None:
        judgment = compute_shadow_judgment(_intent(0.9), _classification(confidence=0.3, score_margin=0.5))
        self.assertAlmostEqual(judgment.overall_confidence, 0.6)
        self.assertTrue(judgment.legacy_should_escalate, "現行モデルはdomain_coverage<0.5だけでescalateする")
        self.assertFalse(judgment.shadow_should_escalate)
        self.assertEqual(judgment.comparison_category, "legacy_escalate_shadow_continue")
        self.assertEqual(judgment.risk_classification, "domain_confidence_only_low")

    def test_score_margin_only_low(self) -> None:
        """intent・domainはどちらも高いが、score_marginだけが僅差(近い
        同点)の場合、現行モデルは`margin<0.1`条件でescalateするが、
        Shadowモデルの計算にはscore_marginが反映されないため
        escalateしない(Task042-1時点で明記された既知の乖離)。"""
        judgment = compute_shadow_judgment(_intent(0.9), _classification(confidence=0.9, score_margin=0.05))
        self.assertAlmostEqual(judgment.overall_confidence, 0.9)
        self.assertTrue(judgment.legacy_should_escalate, "現行モデルは僅差(margin<0.1)でescalateする")
        self.assertFalse(judgment.shadow_should_escalate, "Shadowモデルはoverall_confidence=0.9のためescalateしない")
        self.assertEqual(judgment.comparison_category, "legacy_escalate_shadow_continue")
        self.assertEqual(judgment.risk_classification, "score_margin_only_low")

    def test_all_signals_high(self) -> None:
        judgment = compute_shadow_judgment(_intent(0.9), _classification(confidence=0.9, score_margin=0.5))
        self.assertFalse(judgment.legacy_should_escalate)
        self.assertFalse(judgment.shadow_should_escalate)
        self.assertEqual(judgment.comparison_category, "both_continue")
        self.assertEqual(judgment.risk_classification, "high_confidence")

    def test_all_signals_low(self) -> None:
        judgment = compute_shadow_judgment(_intent(0.2), _classification(confidence=0.2, score_margin=0.05))
        self.assertTrue(judgment.legacy_should_escalate)
        self.assertTrue(judgment.shadow_should_escalate)
        self.assertEqual(judgment.comparison_category, "both_escalate")
        self.assertEqual(judgment.risk_classification, "multiple_signals_low")
        self.assertGreaterEqual(len(judgment.legacy_reasons), 2, "複数の信号が低いため、複数の理由が記録されるはず")

    def test_thresholds_used_is_recorded_and_matches_defaults(self) -> None:
        judgment = compute_shadow_judgment(_intent(0.9), _classification(confidence=0.9, score_margin=0.5))
        self.assertEqual(judgment.thresholds_used, ThresholdsUsed())

    def test_custom_thresholds_can_be_used_without_touching_legacy_model(self) -> None:
        """Shadow側の閾値だけを実験的に変えられることの確認(現行モデルの
        実装(pipeline_orchestrator.py)には一切触れずに済むことの裏付け)。
        """
        custom = ThresholdsUsed(shadow_overall_confidence_threshold=0.7)
        judgment = compute_shadow_judgment(
            _intent(0.6), _classification(confidence=0.6, score_margin=0.5), thresholds=custom,
        )
        self.assertTrue(judgment.shadow_should_escalate, "カスタム閾値0.7未満のためescalateする")
        self.assertEqual(judgment.thresholds_used.shadow_overall_confidence_threshold, 0.7)


class TestShadowJudgmentGoldenComparisonReport(unittest.TestCase):
    """Golden Test全43件(v0.3の37件+複雑入力6件)を実際にPipelineへ通し、
    現行モデルとShadowモデルを比較するレポートを生成する。

    **このテストは、不一致が0件であることを要求しない**(CEO指示
    「Golden Testの期待値は、Shadow結果だけを理由に変更しない」の
    裏付け)。比較レポートの生成自体が成功し、全43件が確実に4分類の
    いずれかへ分類されることのみを検証する。
    """

    def _all_golden_prompts(self) -> list[tuple[str, str]]:
        """`(text, expected_domain)`のタプルを43件返す。

        **2026-07-22に発見・修正したバグの記録**: `complex_golden.
        CASES`は`{case_name: text}`という辞書であり、`.items()`は
        `(case_name, text)`という順序のタプルを返す。一方
        `v03_golden.SUCCESS_CASES`は`(text, domain)`という順序。
        以前の実装は、この2つを単純に連結して`for text, domain in
        prompts:`のように分解していたため、複雑入力6件については
        **実際の日本語入力ではなく、`"01_shared_shopping"`のような
        ケース名の文字列そのものを`run_cognitive_pipeline()`へ渡して
        いた**(この文字列はDomain語彙と一致せずgenericへ分類され、
        たまたま低リスクGeneric仮設計としてSuccessに到達していたため、
        テスト自体は「エラーにならず」実行できてしまっていた——
        しかし実際に比較していたのは意図した入力ではなかった)。

        今回、複雑入力6件についても、golden fileの`"domain"`フィールド
        (実際に検証されているDomain)を読み、`(実際の日本語入力,
        実際のDomain)`という正しい順序のタプルへ揃えた。
        """
        from forge_ai.tests import test_cognitive_pipeline_complex_golden as complex_golden
        from forge_ai.tests import test_v03_domain_inference_golden as v03_golden

        prompts = list(v03_golden.SUCCESS_CASES)
        for case_name, text in complex_golden.CASES.items():
            golden = complex_golden._load_golden(case_name)
            prompts.append((text, golden["domain"]))
        return prompts

    def test_all_43_golden_cases_are_classified_and_report_is_generated(self) -> None:
        from forge_ai.core.orchestration.outcomes import CognitivePipelineSuccess
        from forge_ai.core.pipeline import run_cognitive_pipeline

        prompts = self._all_golden_prompts()
        # FORGE-AI-CONNECT-001(2026-08-10)でtravel golden caseを1件追加(36->37)。
        self.assertEqual(len(prompts), 43, "Golden Testの総数が43件であることの前提確認")

        category_counts: dict[str, int] = {}
        risk_counts: dict[str, int] = {}
        disagreements: list[tuple[str, object]] = []

        for text, _expected_domain in prompts:
            outcome = run_cognitive_pipeline(text)
            self.assertIsInstance(outcome, CognitivePipelineSuccess, f"{text!r}が既存の期待通りSuccessにならなかった")
            trace_entry = next(
                dt for dt in outcome.context.decision_trace if dt.stage == "overall_confidence_observation"
            )
            judgment = trace_entry.shadow_judgment
            self.assertIsNotNone(judgment, f"{text!r}にshadow_judgmentが記録されていない")

            category_counts[judgment.comparison_category] = category_counts.get(judgment.comparison_category, 0) + 1
            risk_counts[judgment.risk_classification] = risk_counts.get(judgment.risk_classification, 0) + 1
            if not judgment.agrees:
                disagreements.append((text, judgment))

        total = len(prompts)
        agree_count = category_counts.get("both_continue", 0) + category_counts.get("both_escalate", 0)

        # 4分類の合計が総数と一致すること(集計漏れが無いことの確認)。
        self.assertEqual(sum(category_counts.values()), total)

        print(f"\n[Shadow Judgment 比較レポート] 総ケース数={total}")
        print(f"  一致件数={agree_count}, 不一致件数={total - agree_count}, "
              f"一致率={agree_count / total * 100:.1f}%")
        print(f"  分類別件数: {category_counts}")
        print(f"  risk_classification別件数: {risk_counts}")
        for text, judgment in disagreements:
            print(
                f"  [不一致] input={text!r} category={judgment.comparison_category} "
                f"risk={judgment.risk_classification} overall_confidence={judgment.overall_confidence:.2f} "
                f"intent_confidence={judgment.intent_confidence:.2f} "
                f"domain_confidence={judgment.domain_confidence:.2f} "
                f"score_margin={judgment.score_margin:.2f} "
                f"legacy_reasons={judgment.legacy_reasons}"
            )

        # このテスト自体は、生成・集計が完全に行えたことのみを確認する
        # (不一致が0件であることは要求しない、CEO指示)。
        self.assertTrue(True)


if __name__ == "__main__":
    unittest.main()
