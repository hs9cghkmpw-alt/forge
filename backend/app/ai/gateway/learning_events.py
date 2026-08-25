"""Safe Learning Event production boundary (FORGE-018).

Existing evidence remains the source of truth.  This module only projects that
evidence into content-free local events and evaluates whether an event may cross
the cloud/dataset boundary.  Network export is deliberately absent: Auth, RLS
and a trusted server-issued contributor identity do not exist yet.
"""

from __future__ import annotations

import time
import re
from dataclasses import dataclass, field, fields
from enum import Enum
from typing import Protocol
from uuid import uuid4

from app.ai.gateway.learning_contract import (
    ContributionTarget,
    DataResidency,
    IntelligenceScope,
    LearningEventType,
    LearningTaskId,
    learning_task_for,
)
from app.ai.gateway.learning_foundation import AcceptanceSignal, TrainingProvenance

SCHEMA_VERSION = "1"
PRIVACY_POLICY_VERSION = "1"
SANITIZER_VERSION = "1"


class TrainingUse(str, Enum):
    ALLOWED = "allowed"
    FORBIDDEN = "forbidden"
    UNKNOWN = "unknown"


class Deployment(str, Enum):
    LOCAL = "local"
    CLOUD = "cloud"
    UNKNOWN = "unknown"


class QualityState(str, Enum):
    CANDIDATE = "candidate"
    REJECTED = "rejected"
    UNKNOWN = "unknown"


class AppTrustTier(str, Enum):
    FORGE_CORE = "forge_core"
    FORGE_GENERATED = "forge_generated"
    REGISTERED_EXTERNAL = "registered_external"
    UNTRUSTED = "untrusted"


class ConsentCategory(str, Enum):
    USAGE_STATISTICS = "usage_statistics"
    AI_FEEDBACK = "ai_feedback"
    SEMANTIC_CORRECTIONS = "semantic_corrections"
    SANITIZED_ARTIFACTS = "sanitized_artifacts"
    CODE_DIFF = "code_diff"
    RUNTIME_CRASH = "runtime_crash"


@dataclass(frozen=True)
class ConsentSnapshot:
    snapshot_id: str
    policy_version: str
    choices: dict[ConsentCategory, bool]
    created_at: float
    withdrawn: bool = False

    @classmethod
    def all_off(cls, *, now: float | None = None) -> "ConsentSnapshot":
        return cls(
            snapshot_id=uuid4().hex,
            policy_version=PRIVACY_POLICY_VERSION,
            choices={category: False for category in ConsentCategory},
            created_at=float(now if now is not None else time.time()),
        )

    def allows(self, category: ConsentCategory) -> bool:
        return not self.withdrawn and self.choices.get(category, False) is True


@dataclass(frozen=True)
class AppIdentity:
    app_id: str
    trust_tier: AppTrustTier = AppTrustTier.UNTRUSTED

    @property
    def permits_global_contribution(self) -> bool:
        return self.trust_tier in {AppTrustTier.FORGE_CORE, AppTrustTier.FORGE_GENERATED}


@dataclass(frozen=True)
class ProjectionContext:
    intelligence_scope: IntelligenceScope = IntelligenceScope.PERSONAL
    data_residency: DataResidency = DataResidency.LOCAL_ONLY
    contribution_target: ContributionTarget = ContributionTarget.NONE
    app_identity: AppIdentity | None = None
    training_use: TrainingUse = TrainingUse.UNKNOWN


@dataclass(frozen=True)
class LearningEvent:
    schema_version: str
    event_id: str
    event_type: LearningEventType
    task_type_id: LearningTaskId
    intelligence_scope: IntelligenceScope
    data_residency: DataResidency
    contribution_target: ContributionTarget
    app_id: str | None
    provider_id: str | None
    deployment: Deployment
    base_model_id: str | None
    base_model_version: str | None
    adapter_id: str | None
    adapter_version: str | None
    forge_ai_version: str | None
    forge_language_version: str | None
    knowledge_version: str | None
    prompt_policy_version: str | None
    capability_ids: tuple[str, ...]
    design_role_ids: tuple[str, ...]
    acceptance: AcceptanceSignal
    repair_attempts: int
    validator_passed: bool | None
    runtime_outcome: str
    build_result: str | None
    test_result: str | None
    latency_ms: float | None
    token_usage: int | None
    consent_snapshot_id: str
    privacy_policy_version: str
    sanitizer_version: str
    training_use: TrainingUse
    provenance: TrainingProvenance
    source: str
    artifact_evidence_id: str | None
    feedback_event_ids: tuple[str, ...]
    knowledge_references: tuple[str, ...]
    created_at: float

    def to_dict(self) -> dict[str, object]:
        def value(item: object) -> object:
            if isinstance(item, Enum):
                return item.value
            if isinstance(item, LearningTaskId):
                return item.value
            if isinstance(item, tuple):
                return [value(v) for v in item]
            return item
        return {item.name: value(getattr(self, item.name)) for item in fields(self)}


@dataclass(frozen=True)
class LearningArtifact:
    artifact_id: str
    event_id: str
    artifact_type: str
    sanitized: bool
    sanitizer_version: str
    training_use: TrainingUse
    provenance: TrainingProvenance
    quality_state: QualityState


@dataclass(frozen=True)
class CloudLearningEnvelope:
    envelope_id: str
    event: LearningEvent
    pseudonymous_contributor_id: str
    created_at: float


class ContributorIdentityProvider(Protocol):
    """Trusted backend boundary. No production implementation exists yet."""

    def issue(self) -> str | None: ...


@dataclass(frozen=True)
class SanitizationResult:
    passed: bool
    reasons: tuple[str, ...] = ()


class LearningSanitizer:
    """Minimization guard for structured events; never claims perfect PII removal."""

    _FORBIDDEN_FIELDS = {
        "utterance", "message", "prompt", "raw_output", "conversation",
        "secret", "token", "raw_provider_response", "forge_document",
        "artifact_handle", "version_token",
    }

    # Conservative rejection patterns. They reduce obvious leakage; they are
    # explicitly not a claim of complete PII detection.
    _SENSITIVE_PATTERNS = (
        re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
        re.compile(r"\bBearer\s+[A-Za-z0-9._~+/=-]{8,}", re.IGNORECASE),
        re.compile(r"\beyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\b"),
        re.compile(r"\b(?:sk|ghp|AIza)[-_A-Za-z0-9]{16,}\b"),
        re.compile(r"\b[A-Z][A-Z0-9_]*(?:KEY|SECRET|TOKEN|PASSWORD)\s*=\s*\S+"),
        re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE),
        re.compile(r"(?<!\d)(?:\+?\d[\d ()-]{7,}\d)(?!\d)"),
        re.compile(r"(?:address|住所|所在地)\s*[:=]\s*\S+", re.IGNORECASE),
    )

    def sanitize(self, event: LearningEvent) -> SanitizationResult:
        present = {item.name.lower() for item in fields(event)}
        violations = list(sorted(present & self._FORBIDDEN_FIELDS))
        # Inspect only boundary-provided labels. Opaque UUIDs/timestamps are
        # machine data and can coincidentally look like phone numbers.
        for value in (
            event.app_id, event.provider_id, event.base_model_id,
            event.base_model_version, event.adapter_id, event.adapter_version,
        ):
            values = value if isinstance(value, list) else [value]
            for item in values:
                if isinstance(item, str) and any(pattern.search(item) for pattern in self._SENSITIVE_PATTERNS):
                    violations.append("sensitive_value_detected")
                    break
        unique = tuple(dict.fromkeys(violations))
        return SanitizationResult(not unique, unique)


class RetentionKind(str, Enum):
    LOCAL_EVENT = "local_event"
    CLOUD_EXPORT_CANDIDATE = "cloud_export_candidate"
    REJECTED_CANDIDATE = "rejected_candidate"
    LEARNING_ARTIFACT = "learning_artifact"


@dataclass(frozen=True)
class RetentionPolicy:
    max_age_seconds: dict[RetentionKind, float] = field(default_factory=lambda: {
        RetentionKind.LOCAL_EVENT: 90 * 86400,
        RetentionKind.CLOUD_EXPORT_CANDIDATE: 30 * 86400,
        RetentionKind.REJECTED_CANDIDATE: 7 * 86400,
        RetentionKind.LEARNING_ARTIFACT: 30 * 86400,
    })

    def is_expired(self, kind: RetentionKind, created_at: float, *, now: float) -> bool:
        return now - created_at > self.max_age_seconds[kind]


@dataclass(frozen=True)
class ExportDecision:
    event_id: str
    eligible: bool
    reasons: tuple[str, ...]
    created_at: float


@dataclass(frozen=True)
class DatasetCandidate:
    dataset_candidate_id: str
    source_event_ids: tuple[str, ...]
    source_artifact_ids: tuple[str, ...]
    quality_state: QualityState
    created_at: float


class TrainingEligibilityPolicy:
    """The single policy deciding dataset/training eligibility."""

    def evaluate(
        self, event: LearningEvent, *, consent: ConsentSnapshot,
        sanitization: SanitizationResult, expired: bool,
    ) -> tuple[str, ...]:
        reasons: list[str] = []
        category = (
            ConsentCategory.AI_FEEDBACK
            if event.event_type is LearningEventType.FEEDBACK
            else ConsentCategory.USAGE_STATISTICS
        )
        if event.training_use is not TrainingUse.ALLOWED:
            reasons.append("training_use_not_allowed")
        if not consent.allows(category):
            reasons.append("consent_missing_or_withdrawn")
        if not sanitization.passed:
            reasons.append("sanitization_failed")
        if event.provenance is TrainingProvenance.UNKNOWN:
            reasons.append("provenance_unknown")
        if event.source in {"test_double", "unknown"}:
            reasons.append("source_not_trainable")
        if event.validator_passed is False:
            reasons.append("validator_failed")
        if event.runtime_outcome == "failed":
            reasons.append("runtime_failed")
        if expired:
            reasons.append("expired")
        return tuple(reasons)


class LearningEventProjector:
    """The only existing-evidence -> LearningEvent conversion entry point."""

    def project(self, evidence: object, *, consent: ConsentSnapshot, context: ProjectionContext) -> LearningEvent:
        from app.ai.gateway.artifact_feedback import ArtifactFeedbackEvent
        from app.ai.gateway.generation_evidence import GenerationRecord, GenerationSource
        from app.ai.gateway.learning_foundation import ExperienceRecord
        from app.ai.gateway.revision_evidence import RevisionRecord

        event_type: LearningEventType
        task = LearningTaskId("forge", "unknown")
        provider = model = forge_language = artifact_id = None
        deployment = Deployment.UNKNOWN
        capabilities: tuple[str, ...] = ()
        roles: tuple[str, ...] = ()
        acceptance = AcceptanceSignal.UNKNOWN
        repairs = 0
        validator: bool | None = None
        runtime = "unknown"
        latency: float | None = None
        source = "unknown"
        feedback_ids: tuple[str, ...] = ()
        knowledge: tuple[str, ...] = ()
        created_at = time.time()
        provenance = TrainingProvenance.UNKNOWN

        if isinstance(evidence, ExperienceRecord):
            event_type = LearningEventType.AI_CALL
            task = learning_task_for(evidence.task)
            provider, model = evidence.provider, evidence.model
            deployment = Deployment.LOCAL if evidence.provider in {"local", "mock"} else Deployment.CLOUD
            acceptance, repairs, validator = evidence.acceptance, evidence.repair_attempts, evidence.validator_passed
            latency, created_at = evidence.latency_ms, evidence.recorded_at
            source = "test_double" if evidence.provider == "mock" else "ai"
        elif isinstance(evidence, GenerationRecord):
            event_type = LearningEventType.GENERATION
            task = LearningTaskId("forge", "generation")
            capabilities, roles = evidence.capabilities, evidence.design_language_roles
            acceptance, repairs, validator = evidence.user_acceptance, evidence.repair_attempts, evidence.validator_passed
            runtime, created_at = evidence.runtime_outcome.value, evidence.recorded_at
            forge_language, artifact_id = evidence.forge_language_version or None, evidence.uid or None
            knowledge, source = evidence.knowledge_references, evidence.source.value
            deployment = Deployment.LOCAL if evidence.source in {GenerationSource.LOCAL_AI, GenerationSource.CURATED, GenerationSource.TEST_DOUBLE} else Deployment.CLOUD
            provenance = TrainingProvenance.FORGE_SYNTHETIC if evidence.source.is_usable_for_training else TrainingProvenance.UNKNOWN
        elif isinstance(evidence, RevisionRecord):
            event_type = LearningEventType.REVISION
            task = LearningTaskId("forge", "design_revision")
            acceptance, validator = evidence.user_acceptance, evidence.validator_passed
            runtime, created_at = evidence.runtime_outcome.value, evidence.recorded_at
            forge_language, artifact_id, source = evidence.forge_language_version or None, evidence.uid or None, evidence.source.value
            provenance = TrainingProvenance.FORGE_SYNTHETIC if evidence.source.is_usable_for_training else TrainingProvenance.UNKNOWN
        elif isinstance(evidence, ArtifactFeedbackEvent):
            event_type = LearningEventType.FEEDBACK
            task = LearningTaskId("forge", "artifact_feedback")
            acceptance, created_at = evidence.signal, evidence.recorded_at
            artifact_id = evidence.artifact_evidence_ref.uid
            feedback_ids, source = (evidence.event_id,), evidence.source.value
            provenance = TrainingProvenance.FORGE_USER_DATA if source == "user_explicit" else TrainingProvenance.UNKNOWN
        else:
            raise TypeError(f"Unsupported evidence type: {type(evidence).__name__}")

        app_id = context.app_identity.app_id if context.app_identity else None
        return LearningEvent(
            SCHEMA_VERSION, uuid4().hex, event_type, task,
            context.intelligence_scope, context.data_residency, context.contribution_target,
            app_id, provider, deployment, model, None, None, None, None,
            forge_language, None, None, capabilities, roles, acceptance, repairs,
            validator, runtime, None, None, latency, None, consent.snapshot_id,
            consent.policy_version, SANITIZER_VERSION, context.training_use, provenance,
            source, artifact_id, feedback_ids, knowledge, created_at,
        )


class LearningEventService:
    """Production coordinator: local event -> gates -> outbox/lineage decision."""

    def __init__(self, *, now: object = time.time, identity_provider: ContributorIdentityProvider | None = None) -> None:
        self._now = now
        self._identity_provider = identity_provider
        self.projector = LearningEventProjector()
        self.sanitizer = LearningSanitizer()
        self.retention = RetentionPolicy()
        self.eligibility = TrainingEligibilityPolicy()
        self.consent = ConsentSnapshot.all_off(now=float(now()))
        self.context = ProjectionContext()
        self.local_events: list[LearningEvent] = []
        self.export_decisions: list[ExportDecision] = []
        self.outbox: list[CloudLearningEnvelope] = []
        self.dataset_candidates: list[DatasetCandidate] = []

    def observe(self, evidence: object) -> LearningEvent:
        self.purge_expired()
        event = self.projector.project(evidence, consent=self.consent, context=self.context)
        self.local_events.append(event)
        sanitization = self.sanitizer.sanitize(event)
        expired = self.retention.is_expired(RetentionKind.LOCAL_EVENT, event.created_at, now=float(self._now()))
        reasons = list(self.eligibility.evaluate(event, consent=self.consent, sanitization=sanitization, expired=expired))
        if event.data_residency is not DataResidency.CLOUD_ELIGIBLE:
            reasons.append("local_only")
        if event.intelligence_scope is IntelligenceScope.PERSONAL:
            reasons.append("personal_scope")
        if event.contribution_target is ContributionTarget.NONE:
            reasons.append("no_contribution_target")
        if event.contribution_target is ContributionTarget.GLOBAL and (
            self.context.app_identity is not None and not self.context.app_identity.permits_global_contribution
        ):
            reasons.append("untrusted_app")
        contributor_id = self._identity_provider.issue() if self._identity_provider and not reasons else None
        if not contributor_id:
            reasons.append("server_issued_identity_unavailable")
        reasons = list(dict.fromkeys(reasons))
        eligible = not reasons
        self.export_decisions.append(ExportDecision(event.event_id, eligible, tuple(reasons), float(self._now())))
        quality = QualityState.CANDIDATE if eligible else QualityState.REJECTED
        self.dataset_candidates.append(DatasetCandidate(
            uuid4().hex, (event.event_id,), (event.artifact_evidence_id,) if event.artifact_evidence_id else (),
            quality, float(self._now()),
        ))
        if eligible and contributor_id:
            self.outbox.append(CloudLearningEnvelope(uuid4().hex, event, contributor_id, float(self._now())))
        return event

    def purge_expired(self) -> int:
        now = float(self._now())
        before = len(self.local_events)
        self.local_events[:] = [e for e in self.local_events if not self.retention.is_expired(RetentionKind.LOCAL_EVENT, e.created_at, now=now)]
        return before - len(self.local_events)

    def withdraw_consent(self) -> None:
        self.consent = ConsentSnapshot(
            self.consent.snapshot_id, self.consent.policy_version,
            dict(self.consent.choices), self.consent.created_at, True,
        )
        self.outbox.clear()  # future export is blocked; already-trained weights are not unlearned

    def reset(self) -> None:
        self.local_events.clear()
        self.export_decisions.clear()
        self.outbox.clear()
        self.dataset_candidates.clear()
        self.consent = ConsentSnapshot.all_off(now=float(self._now()))
        self.context = ProjectionContext()


_DEFAULT_SERVICE = LearningEventService()


def default_learning_event_service() -> LearningEventService:
    return _DEFAULT_SERVICE


def observe_evidence(evidence: object) -> LearningEvent:
    """Stable hook used by every existing Evidence Store."""
    return _DEFAULT_SERVICE.observe(evidence)
