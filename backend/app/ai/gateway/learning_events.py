"""Learning Event projection and safe contribution boundaries (FORGE-018A).

Evidence is the source of truth. Local projection never reads subject consent.
Cloud collection and dataset/training rights are evaluated separately. Network
export and a production contributor identity deliberately remain absent.
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass, field, fields, replace
from enum import Enum
from types import MappingProxyType
from typing import Mapping, Protocol
from uuid import uuid4

from app.ai.gateway.learning_contract import (
    ContributionTarget, DataResidency, IntelligenceScope, LearningEventType,
    LearningTaskId, learning_task_for,
)
from app.ai.gateway.learning_foundation import AcceptanceSignal

SCHEMA_VERSION = "1"
PRIVACY_POLICY_VERSION = "1"
SANITIZER_VERSION = "1"
EXPORT_POLICY_VERSION = "1"
TRAINING_POLICY_VERSION = "1"


class TrainingUse(str, Enum):
    ALLOWED = "allowed"
    FORBIDDEN = "forbidden"
    UNKNOWN = "unknown"


class Deployment(str, Enum):
    LOCAL = "local"
    CLOUD = "cloud"
    NOT_APPLICABLE = "not_applicable"
    UNKNOWN = "unknown"


class LearningDataProvenance(str, Enum):
    """Origin of data, distinct from model-training provenance."""

    CURATED = "curated"
    LOCAL_AI_OUTPUT = "local_ai_output"
    CLOUD_AI_OUTPUT = "cloud_ai_output"
    USER_EXPLICIT_FEEDBACK = "user_explicit_feedback"
    USER_CORRECTION = "user_correction"
    DETERMINISTIC_RUNTIME = "deterministic_runtime"
    TEST_DOUBLE = "test_double"
    UNKNOWN = "unknown"


class QualityState(str, Enum):
    CANDIDATE = "candidate"
    REJECTED = "rejected"
    REVOKED = "revoked"
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
    choices: Mapping[ConsentCategory, bool]
    created_at: float
    previous_snapshot_id: str | None = None
    effective_at: float = 0.0
    withdrawn: bool = False

    def __post_init__(self) -> None:
        immutable = MappingProxyType({
            category: self.choices.get(category, False) is True
            for category in ConsentCategory
        })
        object.__setattr__(self, "choices", immutable)
        if not self.effective_at:
            object.__setattr__(self, "effective_at", self.created_at)

    @classmethod
    def all_off(cls, *, now: float | None = None) -> "ConsentSnapshot":
        moment = float(now if now is not None else time.time())
        return cls(uuid4().hex, PRIVACY_POLICY_VERSION, {}, moment, effective_at=moment)

    @classmethod
    def create(
        cls, choices: Mapping[ConsentCategory, bool], *, now: float | None = None,
        previous: "ConsentSnapshot | None" = None, withdrawn: bool = False,
    ) -> "ConsentSnapshot":
        moment = float(now if now is not None else time.time())
        return cls(
            uuid4().hex, PRIVACY_POLICY_VERSION, choices, moment,
            previous.snapshot_id if previous else None, moment, withdrawn,
        )

    def allows(self, category: ConsentCategory) -> bool:
        return not self.withdrawn and self.choices.get(category, False) is True


@dataclass(frozen=True)
class AppIdentity:
    app_id: str
    trust_tier: AppTrustTier = AppTrustTier.UNTRUSTED

    @property
    def permits_global_contribution(self) -> bool:
        return self.trust_tier in {
            AppTrustTier.FORGE_CORE, AppTrustTier.FORGE_GENERATED,
        }


@dataclass(frozen=True)
class ProjectionContext:
    """Request/subject-scoped export context; never service-global state."""

    intelligence_scope: IntelligenceScope = IntelligenceScope.PERSONAL
    data_residency: DataResidency = DataResidency.LOCAL_ONLY
    contribution_target: ContributionTarget = ContributionTarget.NONE
    app_identity: AppIdentity | None = None
    training_use: TrainingUse = TrainingUse.UNKNOWN
    provider_terms_allow_training: bool | None = None


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
    consent_snapshot_id: str | None
    privacy_policy_version: str
    sanitizer_version: str
    training_use: TrainingUse
    provenance: LearningDataProvenance
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
                return [value(part) for part in item]
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
    provenance: LearningDataProvenance
    quality_state: QualityState
    created_at: float


@dataclass(frozen=True)
class CloudLearningEnvelope:
    envelope_id: str
    event: LearningEvent
    pseudonymous_contributor_id: str
    consent_snapshot_id: str
    intelligence_scope: IntelligenceScope
    contribution_target: ContributionTarget
    app_id: str | None
    created_at: float


class ContributorIdentityProvider(Protocol):
    def issue(self) -> str | None: ...


@dataclass(frozen=True)
class SanitizationResult:
    passed: bool
    reasons: tuple[str, ...] = ()


class LearningSanitizer:
    """Structured minimization guard; not a claim of complete PII detection."""

    _FORBIDDEN_FIELDS = {
        "utterance", "message", "prompt", "raw_output", "conversation", "secret",
        "token", "raw_provider_response", "forge_document", "artifact_handle",
        "version_token",
    }
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
        for item in (
            event.app_id, event.provider_id, event.base_model_id,
            event.base_model_version, event.adapter_id, event.adapter_version,
        ):
            if isinstance(item, str) and any(
                pattern.search(item) for pattern in self._SENSITIVE_PATTERNS
            ):
                violations.append("sensitive_value_detected")
        unique = tuple(dict.fromkeys(violations))
        return SanitizationResult(not unique, unique)


class RetentionKind(str, Enum):
    LOCAL_EVENT = "local_event"
    CLOUD_EXPORT_CANDIDATE = "cloud_export_candidate"
    REJECTED_CANDIDATE = "rejected_candidate"
    DATASET_CANDIDATE = "dataset_candidate"
    LEARNING_ARTIFACT = "learning_artifact"


@dataclass(frozen=True)
class RetentionPolicy:
    max_age_seconds: Mapping[RetentionKind, float] = field(
        default_factory=lambda: MappingProxyType({
            RetentionKind.LOCAL_EVENT: 90 * 86400,
            RetentionKind.CLOUD_EXPORT_CANDIDATE: 30 * 86400,
            RetentionKind.REJECTED_CANDIDATE: 7 * 86400,
            RetentionKind.DATASET_CANDIDATE: 30 * 86400,
            RetentionKind.LEARNING_ARTIFACT: 30 * 86400,
        })
    )

    def is_expired(
        self, kind: RetentionKind, created_at: float, *, now: float,
    ) -> bool:
        return now - created_at > self.max_age_seconds[kind]


@dataclass(frozen=True)
class ExportDecision:
    event_id: str
    consent_snapshot_id: str
    eligible: bool
    reasons: tuple[str, ...]
    created_at: float


@dataclass(frozen=True)
class LearningEventEvaluationRecord:
    event_id: str
    consent_snapshot_id: str
    export_eligible: bool
    export_reasons: tuple[str, ...]
    training_eligible: bool
    training_reasons: tuple[str, ...]
    created_at: float
    context_snapshot: "EvaluationContextSnapshot"


@dataclass(frozen=True)
class EvaluationContextSnapshot:
    """Privacy-safe facts needed to reproduce an evaluation decision."""

    intelligence_scope: IntelligenceScope
    data_residency: DataResidency
    contribution_target: ContributionTarget
    app_trust_tier: AppTrustTier
    app_id: str | None
    training_use: TrainingUse
    provider_terms_allow_training: bool | None
    consent_policy_version: str
    privacy_policy_version: str
    sanitizer_version: str
    export_policy_version: str
    training_policy_version: str

    @classmethod
    def capture(cls, context: ProjectionContext, consent: ConsentSnapshot) -> "EvaluationContextSnapshot":
        identity = context.app_identity
        return cls(
            context.intelligence_scope, context.data_residency,
            context.contribution_target,
            identity.trust_tier if identity else AppTrustTier.UNTRUSTED,
            identity.app_id if identity else None,
            context.training_use, context.provider_terms_allow_training,
            consent.policy_version, PRIVACY_POLICY_VERSION, SANITIZER_VERSION,
            EXPORT_POLICY_VERSION, TRAINING_POLICY_VERSION,
        )


@dataclass(frozen=True)
class DatasetCandidate:
    dataset_candidate_id: str
    source_event_ids: tuple[str, ...]
    source_artifact_ids: tuple[str, ...]
    consent_snapshot_id: str
    quality_state: QualityState
    eligibility_reasons: tuple[str, ...]
    created_at: float
    revoked_at: float | None = None


_EVENT_CONSENT: Mapping[LearningEventType, ConsentCategory] = MappingProxyType({
    LearningEventType.AI_CALL: ConsentCategory.USAGE_STATISTICS,
    LearningEventType.GENERATION: ConsentCategory.USAGE_STATISTICS,
    LearningEventType.BENCHMARK: ConsentCategory.USAGE_STATISTICS,
    LearningEventType.BUILD: ConsentCategory.USAGE_STATISTICS,
    LearningEventType.TEST: ConsentCategory.USAGE_STATISTICS,
    LearningEventType.COMPILE: ConsentCategory.USAGE_STATISTICS,
    LearningEventType.VALIDATION: ConsentCategory.USAGE_STATISTICS,
    LearningEventType.TOOL_RESULT: ConsentCategory.USAGE_STATISTICS,
    LearningEventType.FEEDBACK: ConsentCategory.AI_FEEDBACK,
    LearningEventType.REVISION: ConsentCategory.SEMANTIC_CORRECTIONS,
    LearningEventType.CRASH: ConsentCategory.RUNTIME_CRASH,
    LearningEventType.RUNTIME: ConsentCategory.RUNTIME_CRASH,
})


def consent_category_for_event(
    event_type: LearningEventType,
) -> ConsentCategory | None:
    """Central fail-closed routing; unmapped future types return None."""

    return _EVENT_CONSENT.get(event_type)


class CloudExportPolicy:
    """Collection rights only. Training rights do not belong here."""

    def evaluate(
        self, event: LearningEvent, *, consent: ConsentSnapshot,
        context: ProjectionContext, sanitization: SanitizationResult,
        expired: bool, identity_available: bool,
    ) -> tuple[str, ...]:
        reasons: list[str] = []
        category = consent_category_for_event(event.event_type)
        if category is None:
            reasons.append("unknown_consent_route")
        elif not consent.allows(category):
            reasons.append("collection_consent_missing_or_withdrawn")
        if not sanitization.passed:
            reasons.append("sanitization_failed")
        if context.data_residency is not DataResidency.CLOUD_ELIGIBLE:
            reasons.append("local_only")
        if context.intelligence_scope is IntelligenceScope.PERSONAL:
            reasons.append("personal_scope")
        if context.contribution_target is ContributionTarget.NONE:
            reasons.append("no_contribution_target")
        if context.contribution_target is ContributionTarget.GLOBAL and (
            context.app_identity is None
            or not context.app_identity.permits_global_contribution
        ):
            reasons.append("untrusted_app")
        if expired:
            reasons.append("expired")
        if not identity_available:
            reasons.append("server_issued_identity_unavailable")
        return tuple(dict.fromkeys(reasons))


class TrainingEligibilityPolicy:
    """Dataset/training rights, evaluated after collection rights."""

    def evaluate(
        self, event: LearningEvent, *, context: ProjectionContext,
        export_decision: ExportDecision,
    ) -> tuple[str, ...]:
        reasons: list[str] = []
        if not export_decision.eligible:
            reasons.append("collection_not_permitted")
        if context.training_use is not TrainingUse.ALLOWED:
            reasons.append("training_use_not_allowed")
        if event.provenance in {
            LearningDataProvenance.UNKNOWN, LearningDataProvenance.TEST_DOUBLE,
        }:
            reasons.append("provenance_not_trainable")
        if (
            event.provenance is LearningDataProvenance.CLOUD_AI_OUTPUT
            and context.provider_terms_allow_training is not True
        ):
            reasons.append("provider_training_terms_not_allowed")
        if event.validator_passed is False:
            reasons.append("validator_failed")
        if event.runtime_outcome == "failed":
            reasons.append("runtime_failed")
        return tuple(dict.fromkeys(reasons))


class LearningEventProjector:
    """The only evidence -> local LearningEvent conversion entry point."""

    @staticmethod
    def _provider_facts(
        provider_id: str | None,
    ) -> tuple[Deployment, LearningDataProvenance, str]:
        from app.ai.gateway.provider_registry import (
            Deployment as RegistryDeployment, definition_for,
        )

        definition = definition_for(provider_id) if provider_id else None
        if definition is None:
            return Deployment.UNKNOWN, LearningDataProvenance.UNKNOWN, "unknown"
        if definition.test_only:
            return Deployment.UNKNOWN, LearningDataProvenance.TEST_DOUBLE, "test_double"
        if definition.deployment is RegistryDeployment.LOCAL:
            return Deployment.LOCAL, LearningDataProvenance.LOCAL_AI_OUTPUT, "local_ai"
        if definition.deployment is RegistryDeployment.CLOUD:
            return Deployment.CLOUD, LearningDataProvenance.CLOUD_AI_OUTPUT, "cloud_ai"
        return Deployment.UNKNOWN, LearningDataProvenance.UNKNOWN, "unknown"

    @staticmethod
    def _generation_facts(source: object) -> tuple[Deployment, LearningDataProvenance]:
        from app.ai.gateway.generation_evidence import GenerationSource

        return {
            GenerationSource.CURATED: (
                Deployment.NOT_APPLICABLE, LearningDataProvenance.CURATED,
            ),
            GenerationSource.LOCAL_AI: (
                Deployment.LOCAL, LearningDataProvenance.LOCAL_AI_OUTPUT,
            ),
            GenerationSource.CLOUD_AI: (
                Deployment.CLOUD, LearningDataProvenance.CLOUD_AI_OUTPUT,
            ),
            GenerationSource.TEST_DOUBLE: (
                Deployment.UNKNOWN, LearningDataProvenance.TEST_DOUBLE,
            ),
        }.get(source, (Deployment.UNKNOWN, LearningDataProvenance.UNKNOWN))

    def project(self, evidence: object) -> LearningEvent:
        from app.ai.gateway.artifact_feedback import ArtifactFeedbackEvent
        from app.ai.gateway.generation_evidence import GenerationRecord
        from app.ai.gateway.learning_foundation import ExperienceRecord
        from app.ai.gateway.revision_evidence import RevisionRecord

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
        provenance = LearningDataProvenance.UNKNOWN

        if isinstance(evidence, ExperienceRecord):
            event_type = LearningEventType.AI_CALL
            task = learning_task_for(evidence.task)
            provider, model = evidence.provider, evidence.model
            deployment, provenance, source = self._provider_facts(provider)
            acceptance = evidence.acceptance
            repairs = evidence.repair_attempts
            validator = evidence.validator_passed
            latency, created_at = evidence.latency_ms, evidence.recorded_at
        elif isinstance(evidence, GenerationRecord):
            event_type = LearningEventType.GENERATION
            task = LearningTaskId("forge", "generation")
            capabilities, roles = evidence.capabilities, evidence.design_language_roles
            acceptance, repairs = evidence.user_acceptance, evidence.repair_attempts
            validator, runtime = evidence.validator_passed, evidence.runtime_outcome.value
            created_at = evidence.recorded_at
            forge_language, artifact_id = evidence.forge_language_version or None, evidence.uid or None
            knowledge, source = evidence.knowledge_references, evidence.source.value
            deployment, provenance = self._generation_facts(evidence.source)
        elif isinstance(evidence, RevisionRecord):
            event_type = LearningEventType.REVISION
            task = LearningTaskId("forge", "design_revision")
            acceptance, validator = evidence.user_acceptance, evidence.validator_passed
            runtime, created_at = evidence.runtime_outcome.value, evidence.recorded_at
            forge_language = evidence.forge_language_version or None
            artifact_id, source = evidence.uid or None, evidence.source.value
            if any(
                item.source.value == "user_correction"
                for item in evidence.design_revisions
            ):
                provenance = LearningDataProvenance.USER_CORRECTION
            else:
                deployment, provenance = self._generation_facts(evidence.source)
        elif isinstance(evidence, ArtifactFeedbackEvent):
            event_type = LearningEventType.FEEDBACK
            task = LearningTaskId("forge", "artifact_feedback")
            acceptance, created_at = evidence.signal, evidence.recorded_at
            artifact_id = evidence.artifact_evidence_ref.uid
            feedback_ids, source = (evidence.event_id,), evidence.source.value
            provenance = (
                LearningDataProvenance.USER_EXPLICIT_FEEDBACK
                if source == "user_explicit"
                else LearningDataProvenance.UNKNOWN
            )
            deployment = Deployment.NOT_APPLICABLE
        else:
            raise TypeError(f"Unsupported evidence type: {type(evidence).__name__}")

        return LearningEvent(
            SCHEMA_VERSION, uuid4().hex, event_type, task,
            IntelligenceScope.PERSONAL, DataResidency.LOCAL_ONLY,
            ContributionTarget.NONE, None, provider, deployment, model, None,
            None, None, None, forge_language, None, None, capabilities, roles,
            acceptance, repairs, validator, runtime, None, None, latency, None,
            None, PRIVACY_POLICY_VERSION, SANITIZER_VERSION, TrainingUse.UNKNOWN,
            provenance, source, artifact_id, feedback_ids, knowledge, created_at,
        )


@dataclass
class LearningObservationDiagnostics:
    failure_count: int = 0
    last_error_type: str | None = None

    def record_failure(self, error: Exception) -> None:
        self.failure_count += 1
        self.last_error_type = type(error).__name__


class LearningEventService:
    """Local observation plus explicit subject-scoped export evaluation."""

    def __init__(
        self, *, now: object = time.time,
        identity_provider: ContributorIdentityProvider | None = None,
    ) -> None:
        self._now = now
        self._identity_provider = identity_provider
        self.projector = LearningEventProjector()
        self.sanitizer = LearningSanitizer()
        self.retention = RetentionPolicy()
        self.cloud_export_policy = CloudExportPolicy()
        self.training_eligibility = TrainingEligibilityPolicy()
        self.local_events: list[LearningEvent] = []
        self.export_decisions: list[ExportDecision] = []
        self.evaluations: list[LearningEventEvaluationRecord] = []
        self.outbox: list[CloudLearningEnvelope] = []
        self.dataset_candidates: list[DatasetCandidate] = []
        self.learning_artifacts: list[LearningArtifact] = []
        self.consent_snapshots: list[ConsentSnapshot] = []
        self._revoked_consent_ids: set[str] = set()
        self.diagnostics = LearningObservationDiagnostics()

    def observe(self, evidence: object) -> LearningEvent:
        self.purge_expired()
        event = self.projector.project(evidence)
        self.local_events.append(event)
        return event

    def evaluate_for_export(
        self, event: LearningEvent, *, consent: ConsentSnapshot,
        context: ProjectionContext,
    ) -> ExportDecision:
        self.purge_expired()
        if all(
            item.snapshot_id != consent.snapshot_id
            for item in self.consent_snapshots
        ):
            self.consent_snapshots.append(consent)
        now = float(self._now())
        effective_consent = (
            replace(consent, withdrawn=True)
            if consent.snapshot_id in self._revoked_consent_ids else consent
        )
        sanitization = self.sanitizer.sanitize(event)
        expired = self.retention.is_expired(
            RetentionKind.LOCAL_EVENT, event.created_at, now=now,
        )
        contributor_id = (
            self._identity_provider.issue() if self._identity_provider else None
        )
        export_reasons = self.cloud_export_policy.evaluate(
            event, consent=effective_consent, context=context,
            sanitization=sanitization, expired=expired,
            identity_available=bool(contributor_id),
        )
        decision = ExportDecision(
            event.event_id, consent.snapshot_id, not export_reasons,
            export_reasons, now,
        )
        self.export_decisions.append(decision)
        training_reasons = self.training_eligibility.evaluate(
            event, context=context, export_decision=decision,
        )
        self.evaluations.append(LearningEventEvaluationRecord(
            event.event_id, consent.snapshot_id, decision.eligible,
            decision.reasons, not training_reasons, training_reasons, now,
            EvaluationContextSnapshot.capture(context, effective_consent),
        ))
        if decision.eligible and contributor_id:
            self.outbox.append(CloudLearningEnvelope(
                uuid4().hex, event, contributor_id, consent.snapshot_id,
                context.intelligence_scope, context.contribution_target,
                context.app_identity.app_id if context.app_identity else None,
                now,
            ))
        if not training_reasons:
            self.dataset_candidates.append(DatasetCandidate(
                uuid4().hex, (event.event_id,),
                (event.artifact_evidence_id,)
                if event.artifact_evidence_id else (),
                consent.snapshot_id, QualityState.CANDIDATE, (), now,
            ))
        return decision

    def withdraw_consent(
        self, previous: ConsentSnapshot,
    ) -> ConsentSnapshot:
        now = float(self._now())
        withdrawn = ConsentSnapshot.create(
            {}, now=now, previous=previous, withdrawn=True,
        )
        self.consent_snapshots.append(withdrawn)
        self._revoked_consent_ids.add(previous.snapshot_id)
        self.outbox[:] = [
            item for item in self.outbox
            if item.consent_snapshot_id != previous.snapshot_id
        ]
        self.dataset_candidates[:] = [
            replace(
                item, quality_state=QualityState.REVOKED,
                eligibility_reasons=("consent_withdrawn",), revoked_at=now,
            )
            if (
                item.consent_snapshot_id == previous.snapshot_id
                and item.quality_state is QualityState.CANDIDATE
            )
            else item
            for item in self.dataset_candidates
        ]
        return withdrawn

    def purge_expired(self) -> int:
        now = float(self._now())
        removed = 0
        collections: tuple[tuple[list[object], RetentionKind], ...] = (
            (self.local_events, RetentionKind.LOCAL_EVENT),
            (self.outbox, RetentionKind.CLOUD_EXPORT_CANDIDATE),
            (self.dataset_candidates, RetentionKind.DATASET_CANDIDATE),
            (self.learning_artifacts, RetentionKind.LEARNING_ARTIFACT),
        )
        for collection, kind in collections:
            before = len(collection)
            collection[:] = [
                item for item in collection
                if not self.retention.is_expired(kind, item.created_at, now=now)
            ]
            removed += before - len(collection)
        before = len(self.export_decisions)
        self.export_decisions[:] = [
            item for item in self.export_decisions
            if not self.retention.is_expired(
                RetentionKind.CLOUD_EXPORT_CANDIDATE
                if item.eligible else RetentionKind.REJECTED_CANDIDATE,
                item.created_at, now=now,
            )
        ]
        removed += before - len(self.export_decisions)
        before = len(self.evaluations)
        self.evaluations[:] = [
            item for item in self.evaluations
            if not self.retention.is_expired(
                RetentionKind.CLOUD_EXPORT_CANDIDATE
                if item.export_eligible else RetentionKind.REJECTED_CANDIDATE,
                item.created_at, now=now,
            )
        ]
        removed += before - len(self.evaluations)
        return removed

    def reset(self) -> None:
        self.local_events.clear()
        self.export_decisions.clear()
        self.evaluations.clear()
        self.outbox.clear()
        self.dataset_candidates.clear()
        self.learning_artifacts.clear()
        self.consent_snapshots.clear()
        self._revoked_consent_ids.clear()
        self.diagnostics = LearningObservationDiagnostics()


_DEFAULT_SERVICE = LearningEventService()


def default_learning_event_service() -> LearningEventService:
    return _DEFAULT_SERVICE


def observe_evidence(evidence: object) -> LearningEvent | None:
    """Fail-safe production hook with local, content-free diagnostics."""

    try:
        return _DEFAULT_SERVICE.observe(evidence)
    except Exception as error:  # learning telemetry must not break user success
        _DEFAULT_SERVICE.diagnostics.record_failure(error)
        return None
