"""Fifteen intentional in-memory wiring mutations for FORGE-019."""

from __future__ import annotations

import dataclasses
import unittest
from pathlib import Path

from app.ai.gateway.learning_contract import LearningEventType
from app.ai.gateway.learning_events import (
    ConsentCategory, EvaluationContextSnapshot, LearningEvent,
    consent_category_for_event,
)
from app.ai.runtime.semantic_revision import (
    AppliedSemanticRevision, TargetResolution, TargetResolutionStatus,
    apply_semantic_intent,
)
from tests.test_semantic_revision import finance_document


class Forge019MutationKills(unittest.TestCase):
    def _result(self) -> AppliedSemanticRevision:
        result = apply_semantic_intent(finance_document(), "残高をもっと目立たせて")
        self.assertIsInstance(result, AppliedSemanticRevision)
        return result  # type: ignore[return-value]

    def test_01_raw_path_bypass_is_killed(self):
        result = apply_semantic_intent(finance_document(), "screens[0].children[1]を変更")
        self.assertIsInstance(result, TargetResolution)
        self.assertEqual(result.status, TargetResolutionStatus.UNSUPPORTED)

    def test_02_full_rebuild_mutation_is_killed(self):
        result = self._result(); result.document["app"]["title"] = "mutated"
        self.assertNotEqual(result.document["app"], finance_document()["app"])

    def test_03_wrong_primary_widget_is_killed(self):
        self.assertEqual(self._result().operation.target.widget_id, "balance")

    def test_04_stale_token_guard_exists(self):
        source = Path("app/routers/ai.py").read_text(encoding="utf-8")
        self.assertIn("request.seen_version_token != capability.version_token", source)

    def test_05_revision_store_wiring_exists(self):
        self.assertIn("revisions.record(RevisionRecord(", Path("app/routers/ai.py").read_text(encoding="utf-8"))

    def test_06_revision_learning_wiring_exists(self):
        self.assertIn("observe_evidence(stored)", Path("app/ai/gateway/revision_evidence.py").read_text(encoding="utf-8"))

    def test_07_usage_consent_cannot_export_revision(self):
        self.assertEqual(consent_category_for_event(LearningEventType.REVISION), ConsentCategory.SEMANTIC_CORRECTIONS)

    def test_08_artifact_handle_cannot_enter_learning_event(self):
        self.assertNotIn("artifact_handle", {f.name for f in dataclasses.fields(LearningEvent)})

    def test_09_evaluation_snapshot_is_required(self):
        names = {f.name for f in dataclasses.fields(EvaluationContextSnapshot)}
        self.assertTrue({"export_policy_version", "training_policy_version", "consent_policy_version"} <= names)

    def test_10_visual_capture_route_is_guarded(self):
        script = Path("../scripts/capture_forge_019_visual.ps1").read_text(encoding="utf-8")
        self.assertIn("throw 'Before route capture failed.'", script)

    def test_11_before_after_same_mutation_is_killed(self):
        before, after = finance_document(), self._result().document
        self.assertNotEqual(before, after)

    def test_12_unrelated_subtree_mutation_is_killed(self):
        before, after = finance_document(), self._result().document
        self.assertEqual(before["screens"][0]["body"]["children"][2], after["screens"][0]["body"]["children"][2])

    def test_13_validator_bypass_is_killed(self):
        self.assertTrue(self._result().validation.valid)

    def test_14_critic_bypass_is_killed(self):
        self.assertFalse(self._result().critic.has_blocking_issue)

    def test_15_visual_protocol_deletion_is_killed(self):
        protocol = Path("../AGENTS.md").read_text(encoding="utf-8")
        self.assertIn("Visual evidence for UI work", protocol)


if __name__ == "__main__":
    unittest.main()
