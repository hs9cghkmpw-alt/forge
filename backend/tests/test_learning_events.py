"""FORGE-018A Learning boundary, isolation, and production wiring tests."""

from __future__ import annotations

import dataclasses
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import MappingProxyType

from app.ai.gateway.artifact_feedback import (
    ArtifactEvidenceId, EvidenceKind, FeedbackEventLog, FeedbackSource,
)
from app.ai.gateway.generation_evidence import (
    GenerationEvidenceStore, GenerationRecord, GenerationSource, RuntimeOutcome,
)
from app.ai.gateway.learning_contract import (
    ContributionTarget, DataResidency, IntelligenceScope, LearningEventType,
)
from app.ai.gateway.learning_events import (
    AppIdentity, AppTrustTier, ConsentCategory, ConsentSnapshot, DatasetCandidate,
    Deployment, LearningArtifact, LearningDataProvenance, LearningEvent,
    LearningEventService, ProjectionContext, QualityState, TrainingUse,
    consent_category_for_event, default_learning_event_service,
)
from app.ai.gateway.learning_foundation import (
    AcceptanceSignal, ExperienceRecord, ExperienceStore, TrainingProvenance,
)
from app.ai.gateway.revision_evidence import RevisionRecord
from app.ai.gateway.tasks import ForgeTask


class _TrustedIdentity:
    def issue(self) -> str:
        return "server-issued-opaque-test-id"


def _consent(*categories: ConsentCategory, now: float | None = None) -> ConsentSnapshot:
    return ConsentSnapshot.create(
        {item: item in categories for item in ConsentCategory}, now=now,
    )


def _global_context(
    training_use: TrainingUse = TrainingUse.ALLOWED, *,
    provider_terms: bool | None = True,
) -> ProjectionContext:
    return ProjectionContext(
        IntelligenceScope.GLOBAL, DataResidency.CLOUD_ELIGIBLE,
        ContributionTarget.GLOBAL,
        AppIdentity("forge", AppTrustTier.FORGE_CORE),
        training_use, provider_terms,
    )


def _generation(
    source: GenerationSource = GenerationSource.CURATED, *,
    recorded_at: float | None = None,
) -> GenerationRecord:
    return GenerationRecord(
        source, "finance", True,
        user_acceptance=AcceptanceSignal.ACCEPTED,
        runtime_outcome=RuntimeOutcome.RENDERED,
        recorded_at=time.time() if recorded_at is None else recorded_at,
    )


class LearningBoundaryContractTests(unittest.TestCase):
    def test_evaluation_context_snapshot_reproduces_policy_inputs_without_content(self) -> None:
        service = LearningEventService(identity_provider=_TrustedIdentity())
        event = service.observe(_generation())
        consent = ConsentSnapshot.create({ConsentCategory.USAGE_STATISTICS: True})
        context = ProjectionContext(
            intelligence_scope=IntelligenceScope.GLOBAL,
            data_residency=DataResidency.CLOUD_ELIGIBLE,
            contribution_target=ContributionTarget.GLOBAL,
            app_identity=AppIdentity("forge", AppTrustTier.FORGE_CORE),
            training_use=TrainingUse.FORBIDDEN,
            provider_terms_allow_training=False,
        )
        service.evaluate_for_export(event, consent=consent, context=context)
        snapshot = service.evaluations[-1].context_snapshot
        self.assertEqual(snapshot.training_use, TrainingUse.FORBIDDEN)
        self.assertEqual(snapshot.app_trust_tier, AppTrustTier.FORGE_CORE)
        self.assertTrue(snapshot.export_policy_version)
        self.assertTrue(snapshot.training_policy_version)
        forbidden = {"utterance", "message", "prompt", "raw_output", "conversation",
                     "secret", "token", "artifact_handle", "version_token"}
        self.assertTrue(forbidden.isdisjoint(snapshot.__dataclass_fields__))

    def test_event_has_no_raw_content_or_capability_handles(self) -> None:
        names = {item.name for item in dataclasses.fields(LearningEvent)}
        forbidden = {
            "utterance", "message", "prompt", "raw_output", "conversation",
            "secret", "token", "raw_provider_response", "forge_document",
            "artifact_handle", "version_token",
        }
        self.assertFalse(names & forbidden)

    def test_learning_provenance_is_not_model_training_provenance(self) -> None:
        field_type = next(
            item.type for item in dataclasses.fields(LearningEvent)
            if item.name == "provenance"
        )
        self.assertIn("LearningDataProvenance", str(field_type))
        self.assertNotIn("TrainingProvenance", str(field_type))
        self.assertNotEqual(LearningDataProvenance, TrainingProvenance)

    def test_consent_is_immutable_all_off_and_append_only(self) -> None:
        first = ConsentSnapshot.all_off(now=1.0)
        self.assertTrue(all(not first.allows(item) for item in ConsentCategory))
        self.assertIsInstance(first.choices, MappingProxyType)
        with self.assertRaises(TypeError):
            first.choices[ConsentCategory.AI_FEEDBACK] = True  # type: ignore[index]
        second = ConsentSnapshot.create(
            {ConsentCategory.AI_FEEDBACK: True}, now=2.0, previous=first,
        )
        self.assertNotEqual(first.snapshot_id, second.snapshot_id)
        self.assertEqual(second.previous_snapshot_id, first.snapshot_id)
        self.assertEqual(second.effective_at, 2.0)
        self.assertFalse(first.allows(ConsentCategory.AI_FEEDBACK))

    def test_central_consent_routing_is_event_specific_and_fail_closed(self) -> None:
        self.assertIs(
            consent_category_for_event(LearningEventType.GENERATION),
            ConsentCategory.USAGE_STATISTICS,
        )
        self.assertIs(
            consent_category_for_event(LearningEventType.FEEDBACK),
            ConsentCategory.AI_FEEDBACK,
        )
        self.assertIs(
            consent_category_for_event(LearningEventType.REVISION),
            ConsentCategory.SEMANTIC_CORRECTIONS,
        )
        self.assertIs(
            consent_category_for_event(LearningEventType.CRASH),
            ConsentCategory.RUNTIME_CRASH,
        )
        self.assertIsNone(consent_category_for_event(LearningEventType.REGENERATION))

    def test_revision_cannot_export_with_usage_statistics_only(self) -> None:
        service = LearningEventService(identity_provider=_TrustedIdentity())
        event = service.observe(RevisionRecord(
            base_generation_ref=1, source=GenerationSource.CURATED,
            validator_passed=True, runtime_outcome=RuntimeOutcome.RENDERED,
            user_acceptance=AcceptanceSignal.ACCEPTED, recorded_at=time.time(),
        ))
        decision = service.evaluate_for_export(
            event, consent=_consent(ConsentCategory.USAGE_STATISTICS),
            context=_global_context(),
        )
        self.assertFalse(decision.eligible)
        self.assertIn("collection_consent_missing_or_withdrawn", decision.reasons)

    def test_collection_rights_are_independent_from_training_rights(self) -> None:
        service = LearningEventService(identity_provider=_TrustedIdentity())
        event = service.observe(_generation())
        decision = service.evaluate_for_export(
            event, consent=_consent(ConsentCategory.USAGE_STATISTICS),
            context=_global_context(TrainingUse.FORBIDDEN),
        )
        self.assertTrue(decision.eligible, decision.reasons)
        self.assertEqual(len(service.outbox), 1)
        self.assertFalse(service.dataset_candidates)
        evaluation = service.evaluations[-1]
        self.assertTrue(evaluation.export_eligible)
        self.assertFalse(evaluation.training_eligible)
        self.assertIn("training_use_not_allowed", evaluation.training_reasons)
        self.assertNotIn("training_use_not_allowed", evaluation.export_reasons)

    def test_cloud_output_terms_unknown_never_becomes_dataset_candidate(self) -> None:
        service = LearningEventService(identity_provider=_TrustedIdentity())
        event = service.observe(_generation(GenerationSource.CLOUD_AI))
        decision = service.evaluate_for_export(
            event, consent=_consent(ConsentCategory.USAGE_STATISTICS),
            context=_global_context(provider_terms=None),
        )
        self.assertTrue(decision.eligible)
        self.assertFalse(service.dataset_candidates)
        self.assertIn(
            "provider_training_terms_not_allowed",
            service.evaluations[-1].training_reasons,
        )

    def test_test_double_can_be_collected_but_not_trained(self) -> None:
        service = LearningEventService(identity_provider=_TrustedIdentity())
        event = service.observe(ExperienceRecord(
            ForgeTask.COGNITIVE_STAGE, "mock", "mock", True,
            validator_passed=True, recorded_at=time.time(),
        ))
        decision = service.evaluate_for_export(
            event, consent=_consent(ConsentCategory.USAGE_STATISTICS),
            context=_global_context(),
        )
        self.assertTrue(decision.eligible)
        self.assertIs(event.provenance, LearningDataProvenance.TEST_DOUBLE)
        self.assertFalse(service.dataset_candidates)

    def test_only_training_eligible_events_create_dataset_candidates(self) -> None:
        service = LearningEventService(identity_provider=_TrustedIdentity())
        event = service.observe(_generation())
        service.evaluate_for_export(
            event, consent=_consent(ConsentCategory.USAGE_STATISTICS),
            context=_global_context(),
        )
        self.assertEqual(len(service.dataset_candidates), 1)
        candidate: DatasetCandidate = service.dataset_candidates[0]
        self.assertEqual(candidate.source_event_ids, (event.event_id,))
        self.assertEqual(candidate.quality_state, QualityState.CANDIDATE)

    def test_missing_identity_and_local_boundary_fail_closed(self) -> None:
        service = LearningEventService()
        event = service.observe(_generation())
        decision = service.evaluate_for_export(
            event, consent=_consent(ConsentCategory.USAGE_STATISTICS),
            context=ProjectionContext(training_use=TrainingUse.ALLOWED),
        )
        self.assertIn("server_issued_identity_unavailable", decision.reasons)
        self.assertIn("local_only", decision.reasons)
        self.assertIn("personal_scope", decision.reasons)
        self.assertFalse(service.outbox)

    def test_sanitizer_and_untrusted_app_fail_closed(self) -> None:
        service = LearningEventService(identity_provider=_TrustedIdentity())
        event = service.observe(ExperienceRecord(
            ForgeTask.COGNITIVE_STAGE, "person@example.com", "model", True,
            recorded_at=time.time(),
        ))
        context = dataclasses.replace(
            _global_context(),
            app_identity=AppIdentity("client-value", AppTrustTier.UNTRUSTED),
        )
        decision = service.evaluate_for_export(
            event, consent=_consent(ConsentCategory.USAGE_STATISTICS),
            context=context,
        )
        self.assertIn("sanitization_failed", decision.reasons)
        self.assertIn("untrusted_app", decision.reasons)


class IsolationRetentionAndDeploymentTests(unittest.TestCase):
    def test_subject_consent_isolation_sequential_and_parallel(self) -> None:
        service = LearningEventService(identity_provider=_TrustedIdentity())
        event_a = service.observe(_generation())
        event_b = service.observe(_generation())
        on = _consent(ConsentCategory.USAGE_STATISTICS)
        off = ConsentSnapshot.all_off()

        first = service.evaluate_for_export(
            event_a, consent=on, context=_global_context(TrainingUse.FORBIDDEN),
        )
        second = service.evaluate_for_export(
            event_b, consent=off, context=_global_context(TrainingUse.FORBIDDEN),
        )
        self.assertTrue(first.eligible)
        self.assertFalse(second.eligible)

        service.reset()
        events = [service.observe(_generation()), service.observe(_generation())]
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [
                pool.submit(
                    service.evaluate_for_export, events[0], consent=on,
                    context=_global_context(TrainingUse.FORBIDDEN),
                ),
                pool.submit(
                    service.evaluate_for_export, events[1], consent=off,
                    context=_global_context(TrainingUse.FORBIDDEN),
                ),
            ]
        results = [item.result() for item in futures]
        self.assertEqual([item.eligible for item in results], [True, False])
        self.assertEqual(
            {item.consent_snapshot_id for item in service.outbox},
            {on.snapshot_id},
        )

    def test_withdrawal_appends_snapshot_clears_outbox_and_revokes_dataset(self) -> None:
        service = LearningEventService(identity_provider=_TrustedIdentity(), now=lambda: 20.0)
        consent = _consent(ConsentCategory.USAGE_STATISTICS, now=10.0)
        event = service.observe(_generation(recorded_at=20.0))
        service.evaluate_for_export(
            event, consent=consent, context=_global_context(),
        )
        self.assertEqual(len(service.outbox), 1)
        self.assertEqual(len(service.dataset_candidates), 1)
        withdrawn = service.withdraw_consent(consent)
        self.assertNotEqual(withdrawn.snapshot_id, consent.snapshot_id)
        self.assertEqual(withdrawn.previous_snapshot_id, consent.snapshot_id)
        self.assertFalse(service.outbox)
        self.assertEqual(
            service.dataset_candidates[0].quality_state, QualityState.REVOKED,
        )
        self.assertEqual(service.dataset_candidates[0].revoked_at, 20.0)
        future = service.evaluate_for_export(
            event, consent=consent, context=_global_context(),
        )
        self.assertFalse(future.eligible)
        self.assertIn(
            "collection_consent_missing_or_withdrawn", future.reasons,
        )

    def test_retention_purges_all_implemented_stores(self) -> None:
        now = [10.0]
        service = LearningEventService(
            identity_provider=_TrustedIdentity(), now=lambda: now[0],
        )
        consent = _consent(ConsentCategory.USAGE_STATISTICS, now=10.0)
        event = service.observe(_generation(recorded_at=10.0))
        service.evaluate_for_export(
            event, consent=consent, context=_global_context(),
        )
        service.learning_artifacts.append(LearningArtifact(
            "a", event.event_id, "sanitized_document", True, "1",
            TrainingUse.ALLOWED, LearningDataProvenance.CURATED,
            QualityState.CANDIDATE, 10.0,
        ))
        self.assertTrue(service.local_events)
        self.assertTrue(service.export_decisions)
        self.assertTrue(service.evaluations)
        self.assertTrue(service.outbox)
        self.assertTrue(service.dataset_candidates)
        self.assertTrue(service.learning_artifacts)
        now[0] = 200 * 86400
        self.assertGreaterEqual(service.purge_expired(), 6)
        self.assertFalse(service.local_events)
        self.assertFalse(service.export_decisions)
        self.assertFalse(service.evaluations)
        self.assertFalse(service.outbox)
        self.assertFalse(service.dataset_candidates)
        self.assertFalse(service.learning_artifacts)

    def test_provider_registry_is_deployment_source_of_truth(self) -> None:
        service = LearningEventService()
        local = service.observe(ExperienceRecord(
            ForgeTask.COGNITIVE_STAGE, "local", "model", True,
            recorded_at=time.time(),
        ))
        mock = service.observe(ExperienceRecord(
            ForgeTask.COGNITIVE_STAGE, "mock", "mock", True,
            recorded_at=time.time(),
        ))
        curated = service.observe(_generation())
        unknown = service.observe(ExperienceRecord(
            ForgeTask.COGNITIVE_STAGE, "ollama-unregistered", "model", True,
            recorded_at=time.time(),
        ))
        self.assertIs(local.deployment, Deployment.LOCAL)
        self.assertIs(
            local.provenance, LearningDataProvenance.LOCAL_AI_OUTPUT,
        )
        self.assertIs(mock.deployment, Deployment.UNKNOWN)
        self.assertIs(mock.provenance, LearningDataProvenance.TEST_DOUBLE)
        self.assertIs(curated.deployment, Deployment.NOT_APPLICABLE)
        self.assertIs(curated.provenance, LearningDataProvenance.CURATED)
        self.assertIs(unknown.deployment, Deployment.UNKNOWN)


class ProductionStoreWiringTests(unittest.TestCase):
    def setUp(self) -> None:
        self.service = default_learning_event_service()
        self.service.reset()

    def test_all_existing_stores_emit_without_exporting(self) -> None:
        ExperienceStore().record(ExperienceRecord(
            ForgeTask.CONVERSATION_STEP, "mock", "mock", True,
        ))
        stored = GenerationEvidenceStore().record(GenerationRecord(
            GenerationSource.CURATED, "finance", True,
            capabilities=("crud",), design_language_roles=("metric.primary",),
            knowledge_references=("design_role.metric.primary@v1",),
        ))
        feedback_log = FeedbackEventLog()
        evidence_id = ArtifactEvidenceId(
            EvidenceKind.GENERATION, stored.uid, stored.ref,
        )
        feedback_log.append(
            evidence_id=evidence_id, signal=AcceptanceSignal.ACCEPTED,
            source=FeedbackSource.USER_EXPLICIT,
        )
        feedback_log.append(
            evidence_id=evidence_id, signal=AcceptanceSignal.CORRECTED,
            source=FeedbackSource.USER_EXPLICIT,
        )
        types = [item.event_type for item in self.service.local_events]
        self.assertIn(LearningEventType.AI_CALL, types)
        self.assertIn(LearningEventType.GENERATION, types)
        self.assertEqual(types.count(LearningEventType.FEEDBACK), 2)
        generation = next(
            item for item in self.service.local_events
            if item.event_type is LearningEventType.GENERATION
        )
        self.assertEqual(
            generation.knowledge_references,
            ("design_role.metric.primary@v1",),
        )
        self.assertFalse(self.service.export_decisions)
        self.assertFalse(self.service.dataset_candidates)
        self.assertFalse(self.service.outbox)

    def test_learning_failure_does_not_break_evidence_and_is_diagnosed(self) -> None:
        original = self.service.projector.project
        before = self.service.diagnostics.failure_count

        def broken(_evidence: object) -> LearningEvent:
            raise RuntimeError("projector-bug")

        self.service.projector.project = broken  # type: ignore[method-assign]
        try:
            stored = ExperienceStore().record(ExperienceRecord(
                ForgeTask.CONVERSATION_STEP, "mock", "mock", True,
            ))
        finally:
            self.service.projector.project = original  # type: ignore[method-assign]
        self.assertEqual(stored.ref, 1)
        self.assertEqual(self.service.diagnostics.failure_count, before + 1)
        self.assertEqual(self.service.diagnostics.last_error_type, "RuntimeError")

    def test_repository_agent_protocol_is_present(self) -> None:
        root = Path(__file__).resolve().parents[2]
        protocol = (root / "AGENTS.md").read_text(encoding="utf-8")
        claude = (root / "CLAUDE.md").read_text(encoding="utf-8")
        for phrase in (
            "GitHub", "Source of Truth", "1つ", "commit", "push", "mutation",
            "CI", "UNVERIFIED", "ChatGPT Reviewer",
        ):
            self.assertIn(phrase, protocol)
        self.assertIn("AGENTS.md", claude.splitlines()[2])


class HTTPProductionWiringTests(unittest.TestCase):
    def setUp(self) -> None:
        from fastapi.testclient import TestClient
        from app.main import app

        self.client = TestClient(app)
        self.service = default_learning_event_service()
        self.service.reset()

    def test_generate_then_feedback_keeps_local_projection_only(self) -> None:
        response = self.client.post("/api/v1/ai/generate", json={"input": {
            "natural_language": "家計の支出をカテゴリ別に管理したい",
            "generation_options": {"provider": "mock"},
        }})
        self.assertEqual(response.status_code, 200, response.text)
        artifact = response.json()["result"]["artifact"]
        for sequence, signal in enumerate(("accepted", "corrected"), start=1):
            feedback = self.client.post("/api/v1/ai/feedback", json={
                "artifact_id": artifact["artifact_id"],
                "seen_version_token": artifact["version_token"],
                "signal": signal,
                "idempotency_key": f"learning-http-018a-{sequence}",
            })
            self.assertEqual(feedback.status_code, 200, feedback.text)
        types = [item.event_type for item in self.service.local_events]
        self.assertIn(LearningEventType.AI_CALL, types)
        self.assertIn(LearningEventType.GENERATION, types)
        self.assertEqual(types.count(LearningEventType.FEEDBACK), 2)
        self.assertFalse(self.service.export_decisions)
        self.assertFalse(self.service.outbox)


if __name__ == "__main__":
    unittest.main()
