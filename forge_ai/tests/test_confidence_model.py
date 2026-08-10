"""Confidence Model(ADR-007、Task042-1)のテスト。

`ConfidenceRecord`・`OverallConfidence`(`cognitive_types.py`)と
`compute_overall_confidence()`(`confidence.py`)を検証する。

**Task042-1の位置づけ(最重要、テストでも明示する)**: このモジュール
一式は**観測専用**であり、パイプラインの制御フロー(`if`分岐)には
一切使われていない。本ファイルのテストも、値の計算そのものが正しい
ことだけを検証し、確認要求(`CognitivePipelineNeedsConfirmation`)の
発生有無には関与しない(そちらは`test_cognitive_orchestrator_
integration.py`が既存の3信号モデルのまま検証を続ける)。
"""

from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from forge_ai.core.domain_model import DomainCategory, DomainRegistry  # noqa: E402
from forge_ai.core.intent_model import Intent  # noqa: E402
from forge_ai.core.orchestration.cognitive_types import (  # noqa: E402
    ConfidenceRecord,
    DomainCandidate,
    DomainClassification,
    OverallConfidence,
)
from forge_ai.core.orchestration.confidence import compute_overall_confidence  # noqa: E402


def _domain_classification(*, confidence: float = 0.6, score_margin: float = 0.15) -> DomainClassification:
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


class TestConfidenceRecord(unittest.TestCase):
    def test_value_and_basis_are_held_as_given(self) -> None:
        record = ConfidenceRecord(value=0.75, basis=("根拠A", "根拠B"))
        self.assertEqual(record.value, 0.75)
        self.assertEqual(record.basis, ("根拠A", "根拠B"))

    def test_basis_defaults_to_empty_tuple(self) -> None:
        record = ConfidenceRecord(value=0.5)
        self.assertEqual(record.basis, ())

    def test_is_frozen(self) -> None:
        record = ConfidenceRecord(value=0.5)
        with self.assertRaises(Exception):  # noqa: B017 — frozen dataclassは属性代入でFrozenInstanceErrorを送出する
            record.value = 0.9  # type: ignore[misc]


class TestOverallConfidence(unittest.TestCase):
    def test_value_is_the_average_of_intent_and_domain_when_others_are_none(self) -> None:
        """Task042-1時点では、entity/planning/template confidenceが
        存在しないため、intent・domainの2件だけの単純平均になる。"""
        overall = OverallConfidence(
            intent_confidence=ConfidenceRecord(value=0.8),
            domain_confidence=ConfidenceRecord(value=0.4),
        )
        self.assertAlmostEqual(overall.value, 0.6)
        self.assertEqual(len(overall.available_components), 2)

    def test_entity_planning_template_confidence_default_to_none(self) -> None:
        overall = OverallConfidence(
            intent_confidence=ConfidenceRecord(value=0.8),
            domain_confidence=ConfidenceRecord(value=0.4),
        )
        self.assertIsNone(overall.entity_confidence)
        self.assertIsNone(overall.planning_confidence)
        self.assertIsNone(overall.template_confidence)

    def test_available_components_grows_as_optional_confidences_are_supplied(self) -> None:
        """将来Task042-2以降でentity/planning/template confidenceが
        算出されるようになった場合、自動的に平均へ加わる設計になって
        いることの確認(指定した分だけavailable_componentsが増える)。"""
        overall = OverallConfidence(
            intent_confidence=ConfidenceRecord(value=0.8),
            domain_confidence=ConfidenceRecord(value=0.4),
            entity_confidence=ConfidenceRecord(value=1.0),
        )
        self.assertEqual(len(overall.available_components), 3)
        self.assertAlmostEqual(overall.value, (0.8 + 0.4 + 1.0) / 3)

    def test_value_with_all_five_components_present(self) -> None:
        overall = OverallConfidence(
            intent_confidence=ConfidenceRecord(value=0.8),
            domain_confidence=ConfidenceRecord(value=0.6),
            entity_confidence=ConfidenceRecord(value=0.7),
            planning_confidence=ConfidenceRecord(value=0.9),
            template_confidence=ConfidenceRecord(value=1.0),
        )
        self.assertEqual(len(overall.available_components), 5)
        self.assertAlmostEqual(overall.value, (0.8 + 0.6 + 0.7 + 0.9 + 1.0) / 5)

    def test_intent_and_domain_confidence_are_mandatory_constructor_arguments(self) -> None:
        """`intent_confidence`・`domain_confidence`はOverallConfidence
        の必須フィールド(既定値無し)であり、`available_components`が
        空になるケースは、型として構築不能であることの確認
        (`.value`内の`if not components: return 0.0`という防御的な
        分岐は、現在の型定義上は到達しないコードである、という理解の
        記録)。"""
        with self.assertRaises(TypeError):
            OverallConfidence()  # type: ignore[call-arg]


class TestComputeOverallConfidence(unittest.TestCase):
    def test_wraps_intent_confidence_and_domain_coverage_with_non_empty_basis(self) -> None:
        intent = Intent(goal="x", required_concepts=("item", "price"), required_actions=("add_item",), constraints=())
        classification = _domain_classification(confidence=0.6)

        overall = compute_overall_confidence(intent, classification)

        self.assertEqual(overall.intent_confidence.value, intent.confidence)
        self.assertTrue(overall.intent_confidence.basis, "intent_confidenceのbasisが空であってはならない")
        self.assertEqual(overall.domain_confidence.value, classification.domain_coverage)
        self.assertTrue(overall.domain_confidence.basis, "domain_confidenceのbasisが空であってはならない")

    def test_entity_planning_template_confidence_are_none_at_task042_1(self) -> None:
        intent = Intent(goal="x", required_concepts=("item",), required_actions=(), constraints=())
        classification = _domain_classification()

        overall = compute_overall_confidence(intent, classification)

        self.assertIsNone(overall.entity_confidence)
        self.assertIsNone(overall.planning_confidence)
        self.assertIsNone(overall.template_confidence)

    def test_value_equals_average_of_intent_confidence_and_domain_coverage(self) -> None:
        intent = Intent(goal="x", required_concepts=("item",), required_actions=(), constraints=())
        classification = _domain_classification(confidence=0.4)

        overall = compute_overall_confidence(intent, classification)

        self.assertAlmostEqual(overall.value, (intent.confidence + classification.domain_coverage) / 2)

    def test_domain_confidence_basis_reflects_score_margin(self) -> None:
        """domain_confidenceのbasisに、score_margin(僅差かどうかの
        重要な文脈情報)が含まれていることを確認する(値としては
        overall_confidenceの計算に使わないが、根拠としては保持する、
        というTask042-1の設計方針の裏付け)。"""
        intent = Intent(goal="x", required_concepts=("item",), required_actions=(), constraints=())
        classification = _domain_classification(confidence=0.6, score_margin=0.05)

        overall = compute_overall_confidence(intent, classification)

        self.assertTrue(any("0.05" in b for b in overall.domain_confidence.basis))


class TestOverallConfidenceObservationDoesNotAffectControlFlow(unittest.TestCase):
    """Task042-1の中心的な要件(観測専用)を、実際のPipeline実行で
    end-to-endに確認する。"""

    def test_low_overall_confidence_prompt_that_previously_succeeded_still_succeeds(self) -> None:
        """既存の3信号モデルに基づけばSuccessになるはずの入力について、
        (低いかもしれない)overall_confidenceの値に関わらず、Success
        という結果自体は変わらないことを確認する(overall_confidence
        観測の追加が、既存の確認要求/Success判定へ一切影響しないことの
        直接的な証拠)。"""

        from forge_ai.core.orchestration.outcomes import CognitivePipelineSuccess
        from forge_ai.core.pipeline import run_cognitive_pipeline

        outcome = run_cognitive_pipeline("買い物リストを作りたい")
        self.assertIsInstance(outcome, CognitivePipelineSuccess)
        assert isinstance(outcome, CognitivePipelineSuccess)

        stages = [dt.stage for dt in outcome.context.decision_trace]
        self.assertIn(
            "overall_confidence_observation", stages,
            "overall_confidenceの観測ステップがDecisionTraceに記録されていること",
        )
        # domain_classificationの直後に挿入されていることも確認する
        # (既存の他ステージの並び順を変えていないことの裏付け)。
        domain_idx = stages.index("domain_classification")
        self.assertEqual(stages[domain_idx + 1], "overall_confidence_observation")

    def test_decision_trace_confidence_field_holds_the_observed_overall_confidence_value(self) -> None:
        from forge_ai.core.orchestration.outcomes import CognitivePipelineSuccess
        from forge_ai.core.pipeline import run_cognitive_pipeline

        outcome = run_cognitive_pipeline("買い物リストを作りたい")
        assert isinstance(outcome, CognitivePipelineSuccess)

        trace_entry = next(
            dt for dt in outcome.context.decision_trace if dt.stage == "overall_confidence_observation"
        )
        self.assertIsNotNone(trace_entry.confidence)
        self.assertGreaterEqual(trace_entry.confidence, 0.0)
        self.assertLessEqual(trace_entry.confidence, 1.0)


class TestDecisionTraceConfidenceObservation(unittest.TestCase):
    """CEO指示(2026-07-21、Task042-2着手前の追加分)への対応:
    DecisionTraceが`overall_confidence`・`available_components`・
    `intent_confidence`・`domain_confidence`・各`basis`を、`reason`
    という自由記述文字列の構文解析無しに、構造化データとして直接
    参照できることを確認する(Task042-2の「現行モデル vs overall_
    confidenceモデル」比較実験のための土台)。"""

    def test_decision_trace_has_confidence_observation_field_defaulting_to_none(self) -> None:
        """既存のDecisionTrace構築箇所(confidence_observationを指定
        しないもの)が壊れていないことの確認(後方互換)。"""
        from forge_ai.core.orchestration.cognitive_types import DecisionTrace

        trace = DecisionTrace(stage="x", decision="y", reason="z")
        self.assertIsNone(trace.confidence_observation)

    def test_decision_trace_can_hold_a_structured_overall_confidence(self) -> None:
        from forge_ai.core.orchestration.cognitive_types import DecisionTrace

        overall = OverallConfidence(
            intent_confidence=ConfidenceRecord(value=0.7, basis=("根拠1",)),
            domain_confidence=ConfidenceRecord(value=0.5, basis=("根拠2",)),
        )
        trace = DecisionTrace(stage="x", decision="y", reason="z", confidence_observation=overall)

        # reasonの文字列を一切パースせず、構造化データとして直接参照できる。
        self.assertEqual(trace.confidence_observation.value, 0.6)
        self.assertEqual(len(trace.confidence_observation.available_components), 2)
        self.assertEqual(trace.confidence_observation.intent_confidence.value, 0.7)
        self.assertEqual(trace.confidence_observation.intent_confidence.basis, ("根拠1",))
        self.assertEqual(trace.confidence_observation.domain_confidence.value, 0.5)
        self.assertEqual(trace.confidence_observation.domain_confidence.basis, ("根拠2",))

    def test_pipeline_run_populates_confidence_observation_on_the_trace_entry(self) -> None:
        """実際のPipeline実行で、`overall_confidence_observation`
        ステージのDecisionTraceが、構造化された`confidence_
        observation`を実際に保持していることを確認する(reason文字列
        だけでなく、Task042-2が直接読み取れるオブジェクトとして
        記録されていること)。"""
        from forge_ai.core.orchestration.outcomes import CognitivePipelineSuccess
        from forge_ai.core.pipeline import run_cognitive_pipeline

        outcome = run_cognitive_pipeline("買い物リストを作りたい")
        assert isinstance(outcome, CognitivePipelineSuccess)

        trace_entry = next(
            dt for dt in outcome.context.decision_trace if dt.stage == "overall_confidence_observation"
        )
        observation = trace_entry.confidence_observation
        self.assertIsNotNone(observation)
        self.assertIsInstance(observation, OverallConfidence)
        self.assertAlmostEqual(observation.value, trace_entry.confidence)
        self.assertGreaterEqual(len(observation.available_components), 2)
        self.assertTrue(observation.intent_confidence.basis)
        self.assertTrue(observation.domain_confidence.basis)

    def test_other_existing_decision_trace_stages_do_not_carry_confidence_observation(self) -> None:
        """既存の他ステージ(cognitive_intent_recognition等)は、今回
        新設した`confidence_observation`を持たない(=`None`のまま)
        ことを確認する。Task042-1がこのステージ以外へ影響を与えて
        いないことの裏付け。"""
        from forge_ai.core.orchestration.outcomes import CognitivePipelineSuccess
        from forge_ai.core.pipeline import run_cognitive_pipeline

        outcome = run_cognitive_pipeline("買い物リストを作りたい")
        assert isinstance(outcome, CognitivePipelineSuccess)

        other_stages = [
            dt for dt in outcome.context.decision_trace if dt.stage != "overall_confidence_observation"
        ]
        self.assertTrue(other_stages, "比較対象の他ステージが1件も無い")
        for dt in other_stages:
            self.assertIsNone(dt.confidence_observation)


if __name__ == "__main__":
    unittest.main()
