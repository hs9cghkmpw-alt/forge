"""FORGE-018 Learning Event foundation and production wiring tests."""

from __future__ import annotations

import dataclasses
import time
import unittest

from app.ai.gateway.artifact_feedback import (
    ArtifactEvidenceId, EvidenceKind, FeedbackEventLog, FeedbackSource,
)
from app.ai.gateway.generation_evidence import (
    GenerationEvidenceStore, GenerationRecord, GenerationSource, RuntimeOutcome,
)
from app.ai.gateway.learning_contract import ContributionTarget, DataResidency, IntelligenceScope
from app.ai.gateway.learning_events import (
    AppIdentity, AppTrustTier, ConsentCategory, ConsentSnapshot, DatasetCandidate,
    LearningEvent, LearningEventService, ProjectionContext, QualityState,
    TrainingUse, default_learning_event_service,
)
from app.ai.gateway.learning_foundation import (
    AcceptanceSignal, ExperienceRecord, ExperienceStore,
)
from app.ai.gateway.tasks import ForgeTask


class _TrustedIdentity:
    def issue(self) -> str:
        return "server-issued-opaque-test-id"


def _consent(*categories: ConsentCategory) -> ConsentSnapshot:
    return ConsentSnapshot(
        "consent-1", "1", {item: item in categories for item in ConsentCategory}, time.time()
    )


class LearningEventContractTests(unittest.TestCase):
    def test_learning_event_cannot_hold_raw_content_or_capability_handles(self) -> None:
        names = {field.name for field in dataclasses.fields(LearningEvent)}
        forbidden = {
            "utterance", "message", "prompt", "raw_output", "conversation", "secret",
            "token", "raw_provider_response", "forge_document", "artifact_handle", "version_token",
        }
        self.assertFalse(names & forbidden)

    def test_consent_defaults_all_off(self) -> None:
        snapshot = ConsentSnapshot.all_off()
        self.assertTrue(all(not snapshot.allows(category) for category in ConsentCategory))

    def test_unknown_test_double_and_withdrawn_are_rejected(self) -> None:
        service = LearningEventService(identity_provider=_TrustedIdentity())
        service.consent = _consent(ConsentCategory.USAGE_STATISTICS)
        service.context = ProjectionContext(
            IntelligenceScope.GLOBAL, DataResidency.CLOUD_ELIGIBLE,
            ContributionTarget.GLOBAL, AppIdentity("forge", AppTrustTier.FORGE_CORE),
            TrainingUse.ALLOWED,
        )
        event = service.observe(ExperienceRecord(ForgeTask.COGNITIVE_STAGE, "mock", "mock", True))
        self.assertEqual(event.source, "test_double")
        self.assertIn("source_not_trainable", service.export_decisions[-1].reasons)
        self.assertFalse(service.outbox)
        service.withdraw_consent()
        self.assertTrue(service.consent.withdrawn)

    def test_unknown_and_forbidden_training_use_are_independently_rejected(self) -> None:
        for training_use in (TrainingUse.UNKNOWN, TrainingUse.FORBIDDEN):
            with self.subTest(training_use=training_use):
                service = LearningEventService(identity_provider=_TrustedIdentity())
                service.consent = _consent(ConsentCategory.USAGE_STATISTICS)
                service.context = ProjectionContext(
                    IntelligenceScope.GLOBAL, DataResidency.CLOUD_ELIGIBLE,
                    ContributionTarget.GLOBAL, AppIdentity("forge", AppTrustTier.FORGE_CORE),
                    training_use,
                )
                service.observe(GenerationRecord(
                    GenerationSource.CURATED, "finance", True,
                    runtime_outcome=RuntimeOutcome.RENDERED, recorded_at=time.time(),
                ))
                self.assertIn("training_use_not_allowed", service.export_decisions[-1].reasons)
                self.assertFalse(service.outbox)

    def test_local_only_is_independently_rejected(self) -> None:
        service = LearningEventService(identity_provider=_TrustedIdentity())
        service.consent = _consent(ConsentCategory.USAGE_STATISTICS)
        service.context = ProjectionContext(
            IntelligenceScope.GLOBAL, DataResidency.LOCAL_ONLY,
            ContributionTarget.GLOBAL, AppIdentity("forge", AppTrustTier.FORGE_CORE),
            TrainingUse.ALLOWED,
        )
        service.observe(GenerationRecord(
            GenerationSource.CURATED, "finance", True,
            runtime_outcome=RuntimeOutcome.RENDERED, recorded_at=time.time(),
        ))
        self.assertIn("local_only", service.export_decisions[-1].reasons)
        self.assertFalse(service.outbox)

    def test_untrusted_app_cannot_contribute_to_global_dataset(self) -> None:
        service = LearningEventService(identity_provider=_TrustedIdentity())
        service.consent = _consent(ConsentCategory.USAGE_STATISTICS)
        service.context = ProjectionContext(
            IntelligenceScope.GLOBAL, DataResidency.CLOUD_ELIGIBLE,
            ContributionTarget.GLOBAL, AppIdentity("client-value", AppTrustTier.UNTRUSTED),
            TrainingUse.ALLOWED,
        )
        service.observe(GenerationRecord(
            GenerationSource.CURATED, "finance", True,
            runtime_outcome=RuntimeOutcome.RENDERED, recorded_at=time.time(),
        ))
        self.assertIn("untrusted_app", service.export_decisions[-1].reasons)
        self.assertFalse(service.outbox)

    def test_local_provider_metadata_fits_same_contract_without_claiming_real_run(self) -> None:
        service = LearningEventService()
        event = service.observe(ExperienceRecord(
            ForgeTask.COGNITIVE_STAGE, "local", "local-model-v1", True,
            recorded_at=time.time(),
        ))
        self.assertEqual(event.deployment.value, "local")
        self.assertEqual(event.provider_id, "local")
        self.assertEqual(event.base_model_id, "local-model-v1")

    def test_personal_local_only_never_crosses_cloud_boundary(self) -> None:
        service = LearningEventService(identity_provider=_TrustedIdentity())
        service.consent = _consent(ConsentCategory.USAGE_STATISTICS)
        service.context = ProjectionContext(training_use=TrainingUse.ALLOWED)
        service.observe(ExperienceRecord(ForgeTask.COGNITIVE_STAGE, "gemini", "model", True))
        reasons = service.export_decisions[-1].reasons
        self.assertIn("local_only", reasons)
        self.assertIn("personal_scope", reasons)
        self.assertFalse(service.outbox)

    def test_sanitizer_rejects_obvious_secret_and_pii_in_structured_values(self) -> None:
        service = LearningEventService(identity_provider=_TrustedIdentity())
        service.consent = _consent(ConsentCategory.USAGE_STATISTICS)
        service.context = ProjectionContext(
            IntelligenceScope.GLOBAL, DataResidency.CLOUD_ELIGIBLE,
            ContributionTarget.GLOBAL, AppIdentity("forge", AppTrustTier.FORGE_CORE),
            TrainingUse.ALLOWED,
        )
        service.observe(ExperienceRecord(
            ForgeTask.COGNITIVE_STAGE, "person@example.com", "model", True
        ))
        self.assertIn("sanitization_failed", service.export_decisions[-1].reasons)
        self.assertFalse(service.outbox)

    def test_expired_event_is_purged_and_ineligible(self) -> None:
        now = [10000000.0]
        service = LearningEventService(now=lambda: now[0], identity_provider=_TrustedIdentity())
        service.consent = _consent(ConsentCategory.USAGE_STATISTICS)
        service.context = ProjectionContext(
            IntelligenceScope.GLOBAL, DataResidency.CLOUD_ELIGIBLE,
            ContributionTarget.GLOBAL, AppIdentity("forge", AppTrustTier.FORGE_CORE),
            TrainingUse.ALLOWED,
        )
        event = service.observe(ExperienceRecord(
            ForgeTask.COGNITIVE_STAGE, "gemini", "model", True,
            validator_passed=True, recorded_at=1.0,
        ))
        self.assertIn("expired", service.export_decisions[-1].reasons)
        self.assertEqual(service.purge_expired(), 1)
        self.assertNotIn(event, service.local_events)

    def test_valid_boundary_builds_outbox_but_sends_nothing(self) -> None:
        service = LearningEventService(identity_provider=_TrustedIdentity())
        service.consent = _consent(ConsentCategory.USAGE_STATISTICS)
        service.context = ProjectionContext(
            IntelligenceScope.GLOBAL, DataResidency.CLOUD_ELIGIBLE,
            ContributionTarget.GLOBAL, AppIdentity("forge", AppTrustTier.FORGE_CORE),
            TrainingUse.ALLOWED,
        )
        service.observe(GenerationRecord(
            GenerationSource.CURATED, "finance", True,
            runtime_outcome=RuntimeOutcome.RENDERED, recorded_at=time.time(),
        ))
        self.assertEqual(len(service.outbox), 1)
        self.assertEqual(service.outbox[0].pseudonymous_contributor_id, "server-issued-opaque-test-id")
        self.assertNotIn("artifact_handle", service.outbox[0].event.to_dict())

    def test_missing_server_identity_blocks_otherwise_valid_candidate(self) -> None:
        service = LearningEventService()
        service.consent = _consent(ConsentCategory.USAGE_STATISTICS)
        service.context = ProjectionContext(
            IntelligenceScope.GLOBAL, DataResidency.CLOUD_ELIGIBLE,
            ContributionTarget.GLOBAL, AppIdentity("forge", AppTrustTier.FORGE_CORE),
            TrainingUse.ALLOWED,
        )
        service.observe(GenerationRecord(
            GenerationSource.CURATED, "finance", True,
            runtime_outcome=RuntimeOutcome.RENDERED, recorded_at=time.time(),
        ))
        self.assertIn("server_issued_identity_unavailable", service.export_decisions[-1].reasons)
        self.assertFalse(service.outbox)

    def test_withdrawal_clears_unsent_outbox_and_blocks_future_export(self) -> None:
        service = LearningEventService(identity_provider=_TrustedIdentity())
        service.consent = _consent(ConsentCategory.USAGE_STATISTICS)
        service.context = ProjectionContext(
            IntelligenceScope.GLOBAL, DataResidency.CLOUD_ELIGIBLE,
            ContributionTarget.GLOBAL, AppIdentity("forge", AppTrustTier.FORGE_CORE),
            TrainingUse.ALLOWED,
        )
        evidence = GenerationRecord(
            GenerationSource.CURATED, "finance", True,
            runtime_outcome=RuntimeOutcome.RENDERED, recorded_at=time.time(),
        )
        service.observe(evidence)
        self.assertEqual(len(service.outbox), 1)
        service.withdraw_consent()
        self.assertFalse(service.outbox)
        service.observe(evidence)
        self.assertIn("consent_missing_or_withdrawn", service.export_decisions[-1].reasons)
        self.assertFalse(service.outbox)


class ProductionStoreWiringTests(unittest.TestCase):
    def setUp(self) -> None:
        self.service = default_learning_event_service()
        self.service.reset()

    def test_experience_store_emits_ai_call(self) -> None:
        ExperienceStore().record(ExperienceRecord(
            ForgeTask.CONVERSATION_STEP, "mock", "mock", True
        ))
        self.assertEqual(self.service.local_events[-1].event_type.value, "ai_call")

    def test_generation_store_emits_generation_with_knowledge_lineage(self) -> None:
        stored = GenerationEvidenceStore().record(GenerationRecord(
            GenerationSource.CURATED, "finance", True,
            capabilities=("crud",), design_language_roles=("metric.primary",),
            knowledge_references=("design_role.metric.primary@v1",),
        ))
        event = self.service.local_events[-1]
        self.assertEqual(event.event_type.value, "generation")
        self.assertEqual(event.artifact_evidence_id, stored.uid)
        self.assertEqual(event.knowledge_references, ("design_role.metric.primary@v1",))
        candidate: DatasetCandidate = self.service.dataset_candidates[-1]
        self.assertEqual(candidate.source_event_ids, (event.event_id,))
        self.assertEqual(candidate.source_artifact_ids, (stored.uid,))

    def test_feedback_history_emits_every_event_in_order(self) -> None:
        recorded_at = time.time()
        log = FeedbackEventLog(now=lambda: recorded_at)
        evidence = ArtifactEvidenceId(EvidenceKind.GENERATION, "generation-uid", 1)
        first = log.append(evidence_id=evidence, signal=AcceptanceSignal.ACCEPTED, source=FeedbackSource.USER_EXPLICIT)
        second = log.append(evidence_id=evidence, signal=AcceptanceSignal.CORRECTED, source=FeedbackSource.USER_EXPLICIT)
        events = self.service.local_events[-2:]
        self.assertEqual([e.acceptance for e in events], [AcceptanceSignal.ACCEPTED, AcceptanceSignal.CORRECTED])
        self.assertEqual([e.feedback_event_ids for e in events], [(first.event_id,), (second.event_id,)])
        self.assertEqual([first.sequence, second.sequence], [1, 2])

    def test_default_production_path_is_fail_closed_and_lineage_is_not_lost(self) -> None:
        GenerationEvidenceStore().record(GenerationRecord(
            GenerationSource.CLOUD_AI, "finance", True,
            runtime_outcome=RuntimeOutcome.RENDERED,
        ))
        self.assertFalse(self.service.outbox)
        self.assertEqual(self.service.dataset_candidates[-1].quality_state, QualityState.REJECTED)
        self.assertIn("consent_missing_or_withdrawn", self.service.export_decisions[-1].reasons)


class HTTPProductionWiringTests(unittest.TestCase):
    """Touch only HTTP; AI_CALL/GENERATION/FEEDBACK must appear downstream."""

    def setUp(self) -> None:
        from fastapi.testclient import TestClient
        from app.main import app

        self.client = TestClient(app)
        self.service = default_learning_event_service()
        self.service.reset()

    def test_generate_then_two_feedback_events_close_the_three_paths(self) -> None:
        response = self.client.post(
            "/api/v1/ai/generate",
            json={"input": {
                "natural_language": "家計の支出をカテゴリ別に管理したい",
                "generation_options": {"provider": "mock"},
            }},
        )
        self.assertEqual(response.status_code, 200, response.text)
        artifact = response.json()["result"]["artifact"]
        types = [event.event_type.value for event in self.service.local_events]
        self.assertIn("ai_call", types)
        self.assertIn("generation", types)

        for sequence, signal in enumerate(("accepted", "corrected"), start=1):
            feedback = self.client.post("/api/v1/ai/feedback", json={
                "artifact_id": artifact["artifact_id"],
                "seen_version_token": artifact["version_token"],
                "signal": signal,
                "idempotency_key": f"learning-http-{sequence}",
            })
            self.assertEqual(feedback.status_code, 200, feedback.text)
            self.assertTrue(feedback.json()["recorded"])

        feedback_events = [
            event for event in self.service.local_events if event.event_type.value == "feedback"
        ]
        self.assertEqual(
            [event.acceptance for event in feedback_events],
            [AcceptanceSignal.ACCEPTED, AcceptanceSignal.CORRECTED],
        )
        self.assertTrue(all(event.feedback_event_ids for event in feedback_events))
        self.assertFalse(self.service.outbox, "Production default must never export without consent")


if __name__ == "__main__":
    unittest.main()
