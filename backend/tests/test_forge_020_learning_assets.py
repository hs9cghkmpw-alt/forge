"""FORGE-020 §18-§30 — Forge の長期資産の契約回帰。

Base Model は交換可能である。交換しても残るものが、意図した性質を
持っているかを固定する。
"""

from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from app.ai.gateway.learning_events import (  # noqa: E402
    Deployment,
    LearningDataProvenance,
    TrainingUse,
)
from app.ai.learning.adapter import (  # noqa: E402
    AdapterMetadata,
    DatasetSnapshot,
    TrainingStage,
    evaluate_adapter_promotion,
)
from app.ai.learning.dataset_builder import (  # noqa: E402
    DatasetRejection,
    PreferenceReason,
    build_dataset_candidates,
    build_preference_pairs,
    evaluate_episode_for_dataset,
)
from app.ai.learning.episode import (  # noqa: E402
    EpisodeOutcome,
    EpisodeStep,
    EpisodeStore,
    GenerationEpisode,
    RepairRound,
    StepKind,
    VerificationOutcome,
)
from app.ai.learning.gym import (  # noqa: E402
    TaskCategory,
    TaskSplit,
    default_training_gym,
)
from app.ai.learning.knowledge_acquisition import (  # noqa: E402
    AcquisitionRejection,
    ExtractedSkill,
    SkillKind,
    evaluate_knowledge_acquisition,
)
from app.ai.learning.novel_benchmark import (  # noqa: E402
    SCORING_VERSION,
    AxisResult,
    NovelBenchmarkRun,
    NovelBenchmarkSummary,
    score_novel_run,
)
from app.ai.learning.self_extension import (  # noqa: E402
    CapabilityLifecycle,
    CapabilitySpec,
    ExtensionEvidence,
    evaluate_capability_promotion,
)
from app.ai.learning.teacher import (  # noqa: E402
    ComparisonVerdict,
    EvaluationAxis,
    EvaluationScore,
    TeacherCandidate,
    TeacherComparison,
    evaluate_episode,
)

_P = VerificationOutcome.PASSED
_F = VerificationOutcome.FAILED
_U = VerificationOutcome.UNKNOWN


def _episode(**overrides) -> GenerationEpisode:  # noqa: ANN003
    defaults = {
        "task_id": "gym.known.todo",
        "provider": "local", "model": "m",
        "provenance": LearningDataProvenance.CURATED,
        "training_use": TrainingUse.ALLOWED,
        "validator_outcome": _P, "build_outcome": _P, "test_outcome": _P,
        "final_outcome": EpisodeOutcome.SUCCEEDED,
        "generation_evidence_uid": "gen-1",
    }
    defaults.update(overrides)
    return GenerationEpisode(**defaults)


# ---------------------------------------------------------------------------
# §18 Generation Episode
# ---------------------------------------------------------------------------


class TestEpisodeKeepsTrajectoryNotContent(unittest.TestCase):
    def test_the_diagnostic_form_has_no_raw_text(self) -> None:
        """**生の発話も本文も持たない。** 参照だけ。"""
        episode = _episode(intent_reference="need-ref-1")
        episode.record_step(EpisodeStep(
            StepKind.WEB_FETCH, "fetch_url", references=("https://x.test/a",),
        ))
        rendered = repr(episode.to_dict())
        self.assertIn("need-ref-1", rendered)
        self.assertIn("https://x.test/a", rendered)
        for field_name in ("text", "body", "content", "prompt"):
            self.assertNotIn(f"'{field_name}'", rendered)

    def test_training_right_defaults_to_refused(self) -> None:
        """`UNKNOWN` は学習の重みを持たない（§18 / §40）。"""
        self.assertFalse(GenerationEpisode().has_usable_training_right)

    def test_known_provenance_and_allowed_right_is_usable(self) -> None:
        self.assertTrue(_episode().has_usable_training_right)

    def test_allowed_right_without_provenance_is_still_refused(self) -> None:
        episode = _episode(provenance=LearningDataProvenance.UNKNOWN)
        self.assertFalse(episode.has_usable_training_right)

    def test_repair_success_is_visible(self) -> None:
        episode = _episode()
        episode.record_repair(RepairRound(1, "compile_error", resolved=False))
        self.assertFalse(episode.repair_succeeded)
        episode.record_repair(RepairRound(2, "type_error", resolved=True))
        self.assertTrue(episode.repair_succeeded)

    def test_unsupported_is_not_success(self) -> None:
        """**「能力が無い」を「通った」と数えない。**"""
        self.assertFalse(VerificationOutcome.UNSUPPORTED.is_evidence_of_success)
        self.assertFalse(VerificationOutcome.SKIPPED.is_evidence_of_success)
        self.assertFalse(VerificationOutcome.UNKNOWN.is_evidence_of_success)

    def test_the_store_tracks_start_and_finish(self) -> None:
        store = EpisodeStore()
        episode = store.start(_episode())
        self.assertGreater(episode.started_at, 0)
        store.finish(episode.episode_id, EpisodeOutcome.SUCCEEDED)
        self.assertGreater(store.get(episode.episode_id).finished_at, 0)


# ---------------------------------------------------------------------------
# §19 Teacher
# ---------------------------------------------------------------------------


class TestTeacherIsNotTruth(unittest.TestCase):
    def _comparison(self, teacher_axes, local_axes, **kw):  # noqa: ANN001, ANN003
        return TeacherComparison(
            task_id="t", teacher=TeacherCandidate("gemini", "flash", Deployment.CLOUD),
            teacher_score=EvaluationScore(teacher_axes),
            local_provider="local", local_score=EvaluationScore(local_axes), **kw,
        )

    def test_local_can_win(self) -> None:
        """**Teacher が落ちて Local が通ったら、Local が良い。**"""
        comparison = self._comparison(
            {EvaluationAxis.VALIDATOR: _F, EvaluationAxis.BUILD: _P},
            {EvaluationAxis.VALIDATOR: _P, EvaluationAxis.BUILD: _P},
        )
        self.assertIs(comparison.verdict, ComparisonVerdict.LOCAL_BETTER)
        self.assertTrue(comparison.local_wins_where_teacher_failed)

    def test_teacher_can_win(self) -> None:
        comparison = self._comparison(
            {EvaluationAxis.VALIDATOR: _P, EvaluationAxis.BUILD: _P},
            {EvaluationAxis.VALIDATOR: _F, EvaluationAxis.BUILD: _P},
        )
        self.assertIs(comparison.verdict, ComparisonVerdict.TEACHER_BETTER)

    def test_too_few_measured_axes_is_inconclusive(self) -> None:
        """**分からないものを「Teacher が正しい」へ倒さない。**"""
        comparison = self._comparison(
            {EvaluationAxis.VALIDATOR: _U, EvaluationAxis.BUILD: _U},
            {EvaluationAxis.VALIDATOR: _U, EvaluationAxis.BUILD: _U},
        )
        self.assertIs(comparison.verdict, ComparisonVerdict.INCONCLUSIVE)

    def test_the_evaluator_never_sees_the_provider(self) -> None:
        """同じ結果なら、Provider が違っても同じ点になる。"""
        teacher = _episode(provider="gemini", model="flash")
        local = _episode(provider="local", model="qwen")
        self.assertEqual(
            evaluate_episode(teacher).to_dict()["axes"],
            evaluate_episode(local).to_dict()["axes"],
        )

    def test_a_teacher_candidate_is_marked_as_candidate_not_truth(self) -> None:
        self.assertTrue(TeacherCandidate("gemini", "flash").teacher_candidate)


# ---------------------------------------------------------------------------
# §21 Training Gym
# ---------------------------------------------------------------------------


class TestTrainingGym(unittest.TestCase):
    def setUp(self) -> None:
        self.gym = default_training_gym()

    def test_training_and_held_out_do_not_overlap(self) -> None:
        self.gym.assert_disjoint()

    def test_every_category_is_represented(self) -> None:
        for category in TaskCategory:
            self.assertTrue(
                self.gym.for_category(category), f"{category.value} の課題が無い",
            )

    def test_novel_tasks_are_held_out(self) -> None:
        """**Novel を training に入れたら Novel ではない。**"""
        for task in self.gym.for_category(TaskCategory.NOVEL):
            self.assertIs(task.split, TaskSplit.HELD_OUT, task.task_id)

    def test_task_identity_changes_when_the_task_changes(self) -> None:
        """課題を書き換えたら別物として扱う（011 §3 と同じ）。"""
        from dataclasses import replace

        task = self.gym.get("gym.known.todo")
        self.assertNotEqual(task.identity, replace(task, need="別の課題").identity)

    def test_task_identity_changes_with_version(self) -> None:
        from dataclasses import replace

        task = self.gym.get("gym.known.todo")
        self.assertNotEqual(task.identity, replace(task, version=2).identity)

    def test_an_overlapping_gym_is_refused(self) -> None:
        from dataclasses import replace

        from app.ai.learning.gym import TrainingGym

        task = self.gym.get("gym.known.todo")
        broken = TrainingGym(tasks=(task, replace(task, split=TaskSplit.HELD_OUT)))
        with self.assertRaises(ValueError):
            broken.assert_disjoint()


# ---------------------------------------------------------------------------
# §22 Novel Benchmark
# ---------------------------------------------------------------------------


class TestNovelBenchmark(unittest.TestCase):
    def setUp(self) -> None:
        self.gym = default_training_gym()
        self.novel = self.gym.get("gym.novel.fish_puzzle")

    def test_a_training_task_cannot_be_used(self) -> None:
        """**training の Task を Novel として数えない。**"""
        with self.assertRaises(ValueError):
            NovelBenchmarkRun(
                task=self.gym.get("gym.known.todo"), provider="p", model="m",
            )

    def test_an_unknown_axis_is_refused(self) -> None:
        with self.assertRaises(ValueError):
            NovelBenchmarkRun(
                task=self.novel, provider="p", model="m",
                axes={"made_up_axis": AxisResult.PASSED},
            )

    def test_not_evaluated_earns_nothing(self) -> None:
        """**測っていないものを PASS へ倒さない。**"""
        score = score_novel_run(
            NovelBenchmarkRun(task=self.novel, provider="p", model="m"),
        )
        self.assertEqual(score.earned, 0)

    def test_unsupported_is_removed_from_the_denominator(self) -> None:
        """能力が無い軸を0点として混ぜない（§22）。"""
        score = score_novel_run(NovelBenchmarkRun(
            task=self.novel, provider="p", model="m",
            axes={"runtime": AxisResult.UNSUPPORTED, "build": AxisResult.PASSED},
        ))
        self.assertEqual(score.unsupported_weight, 15)
        self.assertEqual(score.possible, 100 - 15)

    def test_the_raw_ratio_uses_the_full_hundred(self) -> None:
        """対外的な実力は100点満点で言う。"""
        score = score_novel_run(NovelBenchmarkRun(
            task=self.novel, provider="p", model="m",
            axes={"build": AxisResult.PASSED},
        ))
        self.assertAlmostEqual(score.raw_ratio, 0.15)

    def test_a_dedicated_template_run_is_excluded(self) -> None:
        """**専用 template を使った run は Novel ではない。**"""
        run = NovelBenchmarkRun(
            task=self.novel, provider="p", model="m",
            axes={"build": AxisResult.PASSED}, used_dedicated_template=True,
        )
        self.assertFalse(run.counts_as_novel)
        summary = NovelBenchmarkSummary((run,))
        self.assertEqual(len(summary.novel_runs), 0)
        self.assertEqual(len(summary.excluded_runs), 1)

    def test_the_score_is_versioned(self) -> None:
        score = score_novel_run(
            NovelBenchmarkRun(task=self.novel, provider="p", model="m"),
        )
        self.assertEqual(score.scoring_version, SCORING_VERSION)

    def test_widget_count_is_not_an_axis(self) -> None:
        """**Widget数 / Template数 を KPI にしない**（§22）。"""
        from app.ai.learning.novel_benchmark import _WEIGHTS

        for forbidden in ("widget_count", "template_count", "genre_count"):
            self.assertNotIn(forbidden, _WEIGHTS)


# ---------------------------------------------------------------------------
# §27・§28 Dataset
# ---------------------------------------------------------------------------


class TestDatasetQualityGate(unittest.TestCase):
    def test_a_fully_verified_episode_is_accepted(self) -> None:
        candidate, reasons = evaluate_episode_for_dataset(_episode())
        self.assertIsNotNone(candidate)
        self.assertEqual(reasons, ())

    def test_a_mock_episode_is_refused(self) -> None:
        """**Mock の癖を学ばない。**"""
        _, reasons = evaluate_episode_for_dataset(
            _episode(provenance=LearningDataProvenance.TEST_DOUBLE),
        )
        self.assertIn(DatasetRejection.NOT_USABLE_PROVENANCE, reasons)

    def test_an_unknown_provenance_episode_is_refused(self) -> None:
        _, reasons = evaluate_episode_for_dataset(
            _episode(provenance=LearningDataProvenance.UNKNOWN),
        )
        self.assertIn(DatasetRejection.PROVENANCE_UNKNOWN, reasons)

    def test_collection_right_is_not_training_right(self) -> None:
        """収集してよい ≠ 学習に使ってよい（§40）。

        Episode が記録されている（＝収集はできた）ことは、学習に使って
        よい理由にならない。`training_use` が `ALLOWED` でなければ通さない。
        """
        for right in (TrainingUse.UNKNOWN, TrainingUse.FORBIDDEN):
            _, reasons = evaluate_episode_for_dataset(_episode(training_use=right))
            self.assertIn(
                DatasetRejection.TRAINING_RIGHT_MISSING, reasons, right.value,
            )

    def test_no_build_evidence_is_refused(self) -> None:
        _, reasons = evaluate_episode_for_dataset(_episode(build_outcome=_U))
        self.assertIn(DatasetRejection.NO_BUILD_EVIDENCE, reasons)

    def test_a_failed_runtime_is_refused(self) -> None:
        _, reasons = evaluate_episode_for_dataset(_episode(runtime_outcome=_F))
        self.assertIn(DatasetRejection.RUNTIME_FAILED, reasons)

    def test_a_cloud_teacher_goes_through_the_same_gate(self) -> None:
        """**強いAIの出力だから通す、をしない**（§19）。"""
        _, reasons = evaluate_episode_for_dataset(_episode(
            provider="gemini", model="flash",
            provenance=LearningDataProvenance.CLOUD_AI_OUTPUT,
            training_use=TrainingUse.UNKNOWN,
        ))
        self.assertIn(DatasetRejection.TRAINING_RIGHT_MISSING, reasons)

    def test_duplicates_are_removed(self) -> None:
        accepted, rejected = build_dataset_candidates([_episode(), _episode()])
        self.assertEqual(len(accepted), 1)
        self.assertTrue(
            any(DatasetRejection.DUPLICATE in r for r in rejected.values()),
        )

    def test_an_anomalous_episode_is_refused(self) -> None:
        episode = _episode()
        episode.steps = tuple(
            EpisodeStep(StepKind.TOOL_CALL, "read_file") for _ in range(501)
        )
        _, reasons = evaluate_episode_for_dataset(episode)
        self.assertIn(DatasetRejection.ANOMALOUS, reasons)

    def test_rejections_are_reported_not_silent(self) -> None:
        _, reasons = evaluate_episode_for_dataset(
            _episode(provenance=LearningDataProvenance.UNKNOWN, build_outcome=_U),
        )
        self.assertGreaterEqual(len(reasons), 2, "落とした理由を1つに潰していない")


class TestPreferencePairs(unittest.TestCase):
    def test_a_successful_repair_becomes_a_pair(self) -> None:
        episode = _episode()
        episode.record_repair(RepairRound(1, "compile_error", resolved=True))
        pairs = build_preference_pairs(episodes=[episode])
        self.assertEqual(len(pairs), 1)
        self.assertIs(pairs[0].reason, PreferenceReason.REPAIRED_TO_PASS)

    def test_an_unresolved_repair_is_not_a_pair(self) -> None:
        """**良い側が確定していないものを対にしない**（§28）。"""
        episode = _episode(final_outcome=EpisodeOutcome.FAILED)
        episode.record_repair(RepairRound(1, "compile_error", resolved=False))
        self.assertEqual(build_preference_pairs(episodes=[episode]), ())

    def test_local_beating_teacher_becomes_a_pair(self) -> None:
        comparison = TeacherComparison(
            task_id="t", teacher=TeacherCandidate("gemini", "flash"),
            teacher_score=EvaluationScore(
                {EvaluationAxis.VALIDATOR: _F, EvaluationAxis.BUILD: _P},
            ),
            local_provider="local",
            local_score=EvaluationScore(
                {EvaluationAxis.VALIDATOR: _P, EvaluationAxis.BUILD: _P},
            ),
        )
        pairs = build_preference_pairs(comparisons=[comparison])
        self.assertEqual(len(pairs), 1)
        self.assertIs(pairs[0].reason, PreferenceReason.LOCAL_BEAT_TEACHER)

    def test_a_score_margin_alone_is_not_a_pair(self) -> None:
        """点差だけでは対にしない。**どの軸で勝ったか**が要る。"""
        comparison = TeacherComparison(
            task_id="t", teacher=TeacherCandidate("gemini", "flash"),
            teacher_score=EvaluationScore(
                {EvaluationAxis.VALIDATOR: _P, EvaluationAxis.BUILD: VerificationOutcome.SKIPPED},
            ),
            local_provider="local",
            local_score=EvaluationScore(
                {EvaluationAxis.VALIDATOR: _P, EvaluationAxis.BUILD: _P},
            ),
        )
        self.assertEqual(build_preference_pairs(comparisons=[comparison]), ())


# ---------------------------------------------------------------------------
# §25・§26 Knowledge / Skill
# ---------------------------------------------------------------------------


class TestKnowledgeNeedsEvidence(unittest.TestCase):
    def _skills(self) -> tuple[ExtractedSkill, ...]:
        return (
            ExtractedSkill("grid_interaction", SkillKind.INTERACTION, "格子の操作"),
            ExtractedSkill("matching_rule", SkillKind.PATTERN, "一致の規則"),
        )

    def test_a_verified_episode_yields_a_candidate(self) -> None:
        episode = _episode(web_source_references=("https://x.test/a",))
        candidate, reasons = evaluate_knowledge_acquisition(episode, self._skills())
        self.assertIsNotNone(candidate)
        self.assertEqual(reasons, ())

    def test_reading_alone_is_not_knowledge(self) -> None:
        """**Build も Test も無いものを知識にしない**（§25）。"""
        episode = _episode(
            build_outcome=_U, test_outcome=_U,
            web_source_references=("https://x.test/a",),
        )
        _, reasons = evaluate_knowledge_acquisition(episode, self._skills())
        self.assertIn(AcquisitionRejection.BUILD_NOT_PASSED, reasons)

    def test_a_sourceless_claim_is_refused(self) -> None:
        _, reasons = evaluate_knowledge_acquisition(_episode(), self._skills())
        self.assertIn(AcquisitionRejection.NO_SOURCE, reasons)

    def test_a_genre_template_is_refused(self) -> None:
        """**`match3_template` として覚えない**（§26 / §33）。"""
        episode = _episode(web_source_references=("https://x.test/a",))
        _, reasons = evaluate_knowledge_acquisition(
            episode,
            (ExtractedSkill("match3_template", SkillKind.PATTERN, "Match3 一式"),),
        )
        self.assertIn(AcquisitionRejection.NOT_GENERALIZED, reasons)

    def test_a_genre_widget_is_refused(self) -> None:
        episode = _episode(web_source_references=("https://x.test/a",))
        _, reasons = evaluate_knowledge_acquisition(
            episode,
            (ExtractedSkill("jrpg_widget", SkillKind.CAPABILITY, "JRPG 一式"),),
        )
        self.assertIn(AcquisitionRejection.NOT_GENERALIZED, reasons)


# ---------------------------------------------------------------------------
# §29・§30 Adapter / Self-Extension
# ---------------------------------------------------------------------------


class TestAdapterPromotion(unittest.TestCase):
    def _adapter(self, **overrides) -> AdapterMetadata:  # noqa: ANN003
        defaults = {
            "adapter_id": "ad-1",
            "base_model_compatibility": ("qwen2.5:1.5b-instruct",),
            "dataset": DatasetSnapshot("v1", "abc123", 100, 20),
            "training_config_identity": "cfg-1",
            "stage": TrainingStage.BENCHMARKED,
            "benchmark_before": 0.60, "benchmark_after": 0.72,
            "regression_passed": True, "rollback_target": "base",
        }
        defaults.update(overrides)
        return AdapterMetadata(**defaults)

    def test_a_complete_adapter_is_eligible(self) -> None:
        decision = evaluate_adapter_promotion(
            self._adapter(), base_model="qwen2.5:1.5b-instruct",
        )
        self.assertTrue(decision.eligible, decision.reasons)

    def test_a_different_base_model_is_refused(self) -> None:
        decision = evaluate_adapter_promotion(self._adapter(), base_model="other")
        self.assertFalse(decision.eligible)

    def test_a_missing_before_benchmark_is_refused(self) -> None:
        """**比較していない昇格を通さない。**"""
        decision = evaluate_adapter_promotion(
            self._adapter(benchmark_before=None), base_model="qwen2.5:1.5b-instruct",
        )
        self.assertFalse(decision.eligible)

    def test_a_regression_failure_is_refused(self) -> None:
        decision = evaluate_adapter_promotion(
            self._adapter(regression_passed=False),
            base_model="qwen2.5:1.5b-instruct",
        )
        self.assertFalse(decision.eligible)

    def test_no_rollback_target_is_refused(self) -> None:
        """**戻せない変更を本番へ入れない。**"""
        decision = evaluate_adapter_promotion(
            self._adapter(rollback_target=""), base_model="qwen2.5:1.5b-instruct",
        )
        self.assertFalse(decision.eligible)

    def test_every_reason_is_reported(self) -> None:
        decision = evaluate_adapter_promotion(
            self._adapter(regression_passed=False, rollback_target=""),
            base_model="other",
        )
        self.assertGreaterEqual(len(decision.reasons), 3)


class TestSelfExtensionPromotion(unittest.TestCase):
    def _spec(self, lifecycle=CapabilityLifecycle.PROVISIONAL):  # noqa: ANN001, ANN202
        return CapabilitySpec("cap.grid_interaction", "格子の操作", lifecycle=lifecycle)

    def _passing(self) -> ExtensionEvidence:
        return ExtensionEvidence(True, True, True, True, True)

    def test_repeated_success_is_required(self) -> None:
        """**1回の成功で昇格させない。**"""
        verdict = evaluate_capability_promotion(self._spec(), [self._passing()])
        self.assertFalse(verdict.eligible)

    def test_three_successes_are_enough(self) -> None:
        verdict = evaluate_capability_promotion(
            self._spec(), [self._passing()] * 3,
        )
        self.assertTrue(verdict.eligible, verdict.reasons)

    def test_provisional_cannot_be_skipped(self) -> None:
        """**`PROVISIONAL` を飛ばして本番へ行けない。**"""
        verdict = evaluate_capability_promotion(
            self._spec(CapabilityLifecycle.GENERATED), [self._passing()] * 3,
        )
        self.assertFalse(verdict.eligible)

    def test_evidence_from_outside_the_sandbox_is_refused(self) -> None:
        outside = ExtensionEvidence(False, True, True, True, True)
        verdict = evaluate_capability_promotion(
            self._spec(), [self._passing(), self._passing(), self._passing(), outside],
        )
        self.assertFalse(verdict.eligible)

    def test_security_must_pass_at_least_once(self) -> None:
        insecure = ExtensionEvidence(True, True, True, False, True)
        verdict = evaluate_capability_promotion(self._spec(), [insecure] * 3)
        self.assertFalse(verdict.eligible)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
