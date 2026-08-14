"""Local AI Learning Foundation
(FORGE-AI-FOUNDATION-010 Phase K、2026-08-13)。

守っているのは3つである:

1. 利用者の入力が、学習用の記録へ**入りえない**こと
2. Shadow Modeが、明示的に有効化しなければ**走らない**こと
3. Modelの由来が、記録漏れのときに**楽観側へ倒れない**こと
"""

from __future__ import annotations

import dataclasses
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from app.ai.gateway.learning_foundation import (  # noqa: E402
    ACTIVE_SHADOW_PLANS,
    KNOWN_MODEL_PROVENANCE,
    CorrectionSignal,
    ExperienceRecord,
    ExperienceStore,
    ModelProvenance,
    ShadowPlan,
    TrainingProvenance,
)
from app.ai.gateway.tasks import ForgeTask  # noqa: E402

_TASK = ForgeTask.CONVERSATION_STEP


def _record(**overrides) -> ExperienceRecord:
    defaults = {
        "task": _TASK, "provider": "gemini", "model": "gemini-2.0-flash",
        "structured_output_valid": True,
    }
    return ExperienceRecord(**{**defaults, **overrides})


class TestUserInputCannotEnterTheLearningRecord(unittest.TestCase):
    """FORGE-USER-GUIDED-SELF-EXTENSION-006 §22「Trainingへ入れない」。"""

    def test_the_record_has_no_free_text_field_for_content(self) -> None:
        """**型で塞ぐ。**

        「本文を入れないよう気を付ける」という運用は、いずれ破られる。
        `ExperienceRecord`には、発話・生成物・応答本文を入れられる
        フィールドがそもそも無い。

        `provider`と`model`は識別子であって内容ではないので許す。
        """
        content_fields = {
            f.name for f in dataclasses.fields(ExperienceRecord)
            if f.type in ("str", "str | None")
        }
        self.assertEqual(
            content_fields, {"provider", "model"},
            f"内容を入れられるフィールドが増えている: {content_fields}",
        )

    def test_it_cannot_hold_an_utterance_or_a_generated_document(self) -> None:
        for forbidden in ("prompt", "utterance", "message", "text", "build_brief",
                          "forge_document", "response", "content", "session_id", "user_id"):
            with self.subTest(field=forbidden):
                with self.assertRaises(TypeError):
                    _record(**{forbidden: "何か"})

    def test_the_diagnostic_view_contains_no_content(self) -> None:
        described = repr(_record(correction=CorrectionSignal.CORRECTED).to_dict())
        self.assertIn("gemini", described)
        for forbidden in ("prompt", "utterance", "build_brief", "forge_document"):
            self.assertNotIn(forbidden, described)

    def test_a_correction_records_only_that_it_happened(self) -> None:
        """訂正の**内容**は利用者の発話そのものなので持たない。"""
        record = _record(correction=CorrectionSignal.CORRECTED)
        self.assertIs(record.correction, CorrectionSignal.CORRECTED)
        self.assertNotIn("correction_text", record.to_dict())

    def test_no_correction_does_not_mean_it_was_correct(self) -> None:
        """`NONE`は「正しかった」ではない——諦めた場合も気付かなかった
        場合もここに入る。Enumのdocstringで明示していることを、
        値の設計としても保つ(`CORRECT`のような値を作らない)。"""
        self.assertNotIn("correct", [v.value for v in CorrectionSignal])


class TestObservationsAreNotBenchmarks(unittest.TestCase):
    """本番の観測を、同一Datasetの実測と混同しない(§19)。"""

    def test_the_summary_says_it_is_not_a_benchmark(self) -> None:
        store = ExperienceStore()
        store.record(_record())
        summary = store.summary_for(_TASK)
        self.assertIn("Benchmark", str(summary.get("note", "")))

    def test_an_empty_task_reports_zero_samples_not_a_rate(self) -> None:
        """0件のときに`0.0`という**率**を返さない。

        「構造化出力の妥当率0%」と「まだ測っていない」は違う。
        """
        summary = ExperienceStore().summary_for(_TASK)
        self.assertEqual(summary["samples"], 0)
        self.assertNotIn("structured_output_valid_rate", summary)

    def test_it_counts_what_it_says_it_counts(self) -> None:
        store = ExperienceStore()
        store.record(_record(structured_output_valid=True))
        store.record(_record(structured_output_valid=False))
        store.record(_record(correction=CorrectionSignal.CORRECTED))
        store.record(_record(used_fallback=True))
        summary = store.summary_for(_TASK)
        self.assertEqual(summary["samples"], 4)
        self.assertEqual(summary["structured_output_valid_rate"], 0.75)
        self.assertEqual(summary["correction_rate"], 0.25)
        self.assertEqual(summary["fallback_rate"], 0.25)

    def test_old_records_are_dropped_instead_of_growing_without_bound(self) -> None:
        store = ExperienceStore()
        for _ in range(ExperienceStore._MAX_RECORDS + 50):  # noqa: SLF001
            store.record(_record())
        self.assertEqual(len(store.all_records()), ExperienceStore._MAX_RECORDS)  # noqa: SLF001


class TestShadowModeDoesNotRunByAccident(unittest.TestCase):
    """Quotaとlatencyを倍にする機能は、明示しなければ動かない。"""

    def test_a_plan_is_inactive_by_default(self) -> None:
        plan = ShadowPlan(task=_TASK, candidate_provider="local")
        self.assertFalse(plan.is_active)

    def test_enabling_without_a_sample_rate_still_does_nothing(self) -> None:
        """「有効にした」だけでは走らない。**割合を書かせる。**"""
        plan = ShadowPlan(task=_TASK, candidate_provider="local", enabled=True)
        self.assertFalse(plan.is_active)

    def test_it_becomes_active_only_when_everything_is_stated(self) -> None:
        plan = ShadowPlan(
            task=_TASK, candidate_provider="local", sample_rate=0.1, enabled=True
        )
        self.assertTrue(plan.is_active)
        self.assertIn("利用者への応答は現行Provider", plan.describe())

    def test_no_shadow_plan_is_active_right_now(self) -> None:
        """MVPでは設計だけ。実行していないことを固定する。"""
        self.assertEqual([p for p in ACTIVE_SHADOW_PLANS if p.is_active], [])


class TestProvenanceFailsClosed(unittest.TestCase):
    """記録漏れが「安全」に化けないこと。"""

    def test_unknown_is_the_default(self) -> None:
        self.assertIs(ModelProvenance(model="x").provenance, TrainingProvenance.UNKNOWN)

    def test_unknown_is_not_allowed_where_provenance_matters(self) -> None:
        """「分からないなら止める」であって「分からないなら大丈夫」ではない。"""
        self.assertFalse(ModelProvenance(model="x").may_be_used_where_provenance_matters)

    def test_a_stated_provenance_passes(self) -> None:
        stated = ModelProvenance(
            model="x", provenance=TrainingProvenance.FORGE_SYNTHETIC
        )
        self.assertTrue(stated.may_be_used_where_provenance_matters)

    def test_no_known_model_claims_a_verified_provenance(self) -> None:
        """Provider公称を検証済みとして書かない(§46)。"""
        for entry in KNOWN_MODEL_PROVENANCE:
            with self.subTest(model=entry.model):
                self.assertIs(entry.provenance, TrainingProvenance.UNKNOWN)

    def test_no_model_is_trained_on_user_data(self) -> None:
        """利用者データで育てたModelは存在しない。

        `FORGE_USER_DATA`という値があるのは、将来そうするなら
        **明示的に書かねばならない**ようにするためであって、
        今そうなっているからではない。
        """
        self.assertEqual(
            [e for e in KNOWN_MODEL_PROVENANCE
             if e.provenance is TrainingProvenance.FORGE_USER_DATA],
            [],
        )


if __name__ == "__main__":
    unittest.main()
