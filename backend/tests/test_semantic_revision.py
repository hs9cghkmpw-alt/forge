from __future__ import annotations

import copy
import unittest

from fastapi.testclient import TestClient

from app.ai.runtime.semantic_revision import (
    AppliedSemanticRevision,
    SemanticOperationKind,
    TargetResolution,
    TargetResolutionStatus,
    apply_semantic_intent,
)
from app.ai.gateway.artifact_feedback import default_artifact_registry, default_feedback_log
from app.ai.gateway.generation_evidence import GenerationRecord, GenerationSource, default_generation_store
from app.ai.gateway.learning_events import default_learning_event_service
from app.ai.gateway.learning_contract import LearningEventType
from app.ai.gateway.revision_evidence import RevisionPatchMode, default_revision_store
from app.main import app


def finance_document(*, duplicate_balance: bool = False) -> dict:
    children = [
        {"type": "metric_view", "id": "income", "label": "収入", "state_ref": "records",
         "value_field": "amount", "aggregate": "sum", "style_role": "metric.primary"},
        {"type": "metric_view", "id": "balance", "label": "残高", "state_ref": "records",
         "value_field": "amount", "aggregate": "sum", "style_role": "metric.secondary"},
        {"type": "text", "id": "unrelated_note", "value": "取引一覧は変更しない"},
    ]
    if duplicate_balance:
        children.append({"type": "metric_view", "id": "balance2", "label": "残高",
                         "state_ref": "records", "value_field": "amount", "aggregate": "sum",
                         "style_role": "metric.secondary"})
    return {
        "version": "1.12", "app": {"title": "家計"}, "initial_screen_id": "home",
        "record_schemas": {"transaction": {"fields": [
            {"name": "name", "type": "string", "label": "名前", "required": True},
            {"name": "category", "type": "string", "label": "分類", "required": True},
            {"name": "amount", "type": "number", "label": "金額", "required": True},
        ]}},
        "screens": [{"id": "home", "title": "家計", "state": {
            "records": {"type": "record_list", "value": [], "schema_ref": "transaction"}},
            "body": {"type": "column", "id": "root", "children": children}}],
    }


class TestSemanticRevision(unittest.TestCase):
    def test_balance_is_resolved_and_promoted_by_typed_operation(self) -> None:
        result = apply_semantic_intent(finance_document(), "残高をもっと目立たせて")
        self.assertIsInstance(result, AppliedSemanticRevision)
        assert isinstance(result, AppliedSemanticRevision)
        self.assertEqual(result.operation.kind, SemanticOperationKind.SELECT_PRIMARY_METRIC)
        widgets = result.document["screens"][0]["body"]["children"]
        self.assertEqual(widgets[1]["style_role"], "metric.primary")
        self.assertEqual(widgets[0]["style_role"], "finance.income")
        self.assertTrue(result.validation.valid)
        self.assertFalse(result.critic.has_blocking_issue)

    def test_unrelated_subtree_is_canonically_identical(self) -> None:
        before = finance_document()
        unrelated = copy.deepcopy(before["screens"][0]["body"]["children"][2])
        result = apply_semantic_intent(before, "残高をもっと目立たせて")
        assert isinstance(result, AppliedSemanticRevision)
        self.assertEqual(result.document["screens"][0]["body"]["children"][2], unrelated)
        self.assertEqual(before, finance_document(), "input document must not be mutated")

    def test_ambiguous_targets_require_clarification(self) -> None:
        result = apply_semantic_intent(finance_document(duplicate_balance=True), "残高を強調")
        self.assertIsInstance(result, TargetResolution)
        assert isinstance(result, TargetResolution)
        self.assertEqual(result.status, TargetResolutionStatus.AMBIGUOUS)

    def test_raw_path_is_not_an_operation_language(self) -> None:
        result = apply_semantic_intent(finance_document(), "screens[0].body.children[1].style_roleを変えて")
        self.assertIsInstance(result, TargetResolution)
        assert isinstance(result, TargetResolution)
        self.assertEqual(result.status, TargetResolutionStatus.UNSUPPORTED)


class TestSemanticRevisionProductionWiring(unittest.TestCase):
    def setUp(self) -> None:
        default_generation_store().reset()
        default_revision_store().reset()
        default_artifact_registry().reset()
        default_feedback_log().reset()
        default_learning_event_service().reset()
        self.client = TestClient(app)

    def _artifact(self):
        generation = default_generation_store().record(GenerationRecord(
            source=GenerationSource.CURATED, domain="household_budget",
            validator_passed=True, forge_language_version="1.12",
        ))
        return default_artifact_registry().register(
            generation_ref=generation.ref, generation_uid=generation.uid,
            session_id="forge-019",
        )

    def test_update_records_revision_learning_event_and_advances_capability(self) -> None:
        artifact = self._artifact()
        response = self.client.post("/api/v1/ai/update", json={
            "forge_document": finance_document(),
            "change_request": "残高をもっと目立たせて",
            "artifact_id": artifact.handle,
            "seen_version_token": artifact.version_token,
            "idempotency_key": "forge-019-correction-1",
        })
        self.assertEqual(response.status_code, 200, response.text)
        result = response.json()["result"]
        self.assertEqual(result["revision_mode"], "local_semantic_patch")
        self.assertEqual(result["semantic_operation"], "select_primary_metric")
        self.assertNotEqual(result["artifact"]["version_token"], artifact.version_token)
        revisions = default_revision_store().all_records()
        self.assertEqual(len(revisions), 1)
        self.assertEqual(revisions[0].patch_mode, RevisionPatchMode.LOCAL_SEMANTIC_PATCH)
        event_types = [e.event_type for e in default_learning_event_service().local_events]
        self.assertIn(LearningEventType.REVISION, event_types)
        self.assertIn(LearningEventType.FEEDBACK, event_types)

        stale = self.client.post("/api/v1/ai/update", json={
            "forge_document": result["forge_document"],
            "change_request": "残高をもっと目立たせて",
            "artifact_id": artifact.handle,
            "seen_version_token": artifact.version_token,
        })
        self.assertEqual(stale.status_code, 422, stale.text)


if __name__ == "__main__":
    unittest.main()
