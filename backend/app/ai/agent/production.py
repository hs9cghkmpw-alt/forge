"""FORGE-020B — Tool-Using Local Agent production wiring.

This is intentionally the first bounded production stage, not FORGE-020G yet.
A real Local model chooses inspection tools, ToolBroker/PermissionBroker executes
them, and Forge independently re-runs the deterministic Validator. Model confidence
is never a success signal.

The production agent receives no raw conversation and no server-repository access.
Its context is identifiers/counts/evidence only. Build/test/runtime/visual are not
claimed unless actually measured; in this stage they remain UNKNOWN.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from typing import Any
from uuid import uuid4

from app.ai.agent.loop import AgentBudget, AgentLoop, AttemptResult
from app.ai.agent.tools import ToolCall
from app.ai.agent.toolset import build_generation_inspection_toolset
from app.ai.gateway.ai_router import default_router
from app.ai.gateway.generation_evidence import default_generation_store
from app.ai.gateway.learning_events import (
    Deployment,
    LearningDataProvenance,
    TrainingUse,
)
from app.ai.gateway.tasks import ForgeTask
from app.ai.learning.episode import (
    EpisodeOutcome,
    EpisodeStep,
    GenerationEpisode,
    StepKind,
    VerificationOutcome,
    default_episode_store,
)
from app.ai.validators.schema_validator import validate_forge_document

__all__ = ["AgentRunSummary", "run_local_agent_verification"]

_ALLOWED_TOOLS = (
    "inspect_forge_document",
    "inspect_capability_gap",
    "validate_forge_document",
)

_AGENT_PLAN_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "tools": {
            "type": "array",
            "minItems": 1,
            "maxItems": 3,
            "items": {"type": "string", "enum": list(_ALLOWED_TOOLS)},
        },
        "reason_code": {
            "type": "string",
            "pattern": "^[a-z][a-z0-9_]*$",
        },
    },
    "required": ["tools"],
}


@dataclass(frozen=True)
class AgentRunSummary:
    requested: bool
    executed: bool
    outcome: EpisodeOutcome
    episode_id: str
    provider: str = ""
    model: str = ""
    tool_calls: int = 0
    tools_used: tuple[str, ...] = ()
    validator_outcome: VerificationOutcome = VerificationOutcome.UNKNOWN
    stopped_because: str = ""

    def to_dict(self) -> dict[str, object]:
        return {
            "requested": self.requested,
            "executed": self.executed,
            "outcome": self.outcome.value,
            "episode_id": self.episode_id,
            "provider": self.provider,
            "model": self.model,
            "tool_calls": self.tool_calls,
            "tools_used": list(self.tools_used),
            "validator_outcome": self.validator_outcome.value,
            "stopped_because": self.stopped_because,
        }


def _generation_record(result: object):
    ref = getattr(result, "generation_ref", None)
    if not isinstance(ref, int):
        return None
    return default_generation_store().get(ref)


def _sanitized_context(result: object, record: object) -> dict[str, object]:
    usage = tuple(getattr(record, "capability_usage", ()) or ())
    gap = getattr(result, "capability_gap", None)
    quality = getattr(result, "quality", None)
    return {
        "forge_language_version": str(
            getattr(record, "forge_language_version", "") or ""
        ),
        "generation_source": str(
            getattr(getattr(record, "source", None), "value", "unknown")
        ),
        "structure_source": str(
            getattr(getattr(record, "structure_source", None), "value", "unknown")
        ),
        "validator_already_passed": bool(getattr(record, "validator_passed", False)),
        "release_ready": bool(getattr(quality, "release_ready", False))
        if quality is not None
        else False,
        "capabilities": [
            {
                "id": str(getattr(item, "capability_id", "") or ""),
                "status": str(getattr(getattr(item, "status", None), "value", "unknown")),
                "used": bool(getattr(item, "used", False)),
            }
            for item in usage
        ],
        "capability_gap": {
            "missing": list(getattr(gap, "missing", ()) or ()),
            "partial": list(getattr(gap, "partial", ()) or ()),
            "critical": list(getattr(gap, "critical", ()) or ()),
            "blocks_completion": bool(getattr(gap, "blocks_completion", False)),
        },
        "available_tools": list(_ALLOWED_TOOLS),
    }


def _agent_prompt(result: object, record: object) -> str:
    context = json.dumps(
        _sanitized_context(result, record),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return (
        "You are Forge Local Agent verification. Choose the minimum useful read-only "
        "tools for independently checking the generated Forge artifact. "
        "Only choose tool names from available_tools. You do not decide success: "
        "Forge Validator and tool outcomes are the source of truth. "
        "Do not request shell, repository, network, write, upload, push, login, or "
        "other side-effecting operations. CONTEXT="
        + context
    )


def run_local_agent_verification(
    result: object,
    *,
    router=None,
    episode_store=None,
) -> AgentRunSummary:
    """Run one bounded, production-wired Local tool-use verification episode.

    Provenance is fail-closed: the Episode starts as UNKNOWN and is promoted to
    LOCAL/LOCAL_AI_OUTPUT only *after* AIRouter reports a successful Local response.
    A provider resolution/timeout failure therefore cannot become positive Local-AI
    trajectory evidence merely because the caller intended to use Local.
    """
    record = _generation_record(result)
    store = episode_store or default_episode_store()
    evidence_uid = str(getattr(record, "uid", "") or "") if record is not None else ""
    episode = store.start(GenerationEpisode(
        task_id="forge.local_agent.verify",
        intent_reference=(f"generation:{evidence_uid}" if evidence_uid else ""),
        deployment=Deployment.UNKNOWN,
        provenance=LearningDataProvenance.UNKNOWN,
        training_use=TrainingUse.UNKNOWN,
        generation_evidence_uid=evidence_uid,
    ))

    if record is None:
        store.finish(episode.episode_id, EpisodeOutcome.FAILED)
        return AgentRunSummary(
            requested=True,
            executed=False,
            outcome=EpisodeOutcome.FAILED,
            episode_id=episode.episode_id,
            stopped_because="missing_generation_evidence",
        )

    broker = build_generation_inspection_toolset(
        forge_document=getattr(result, "forge_document"),
        capability_gap=getattr(result, "capability_gap", None),
        validator=validate_forge_document,
    )
    loop = AgentLoop(
        broker=broker,
        episode=episode,
        budget=AgentBudget(
            max_repair_rounds=0,
            max_tool_calls=6,
            time_budget_seconds=180.0,
        ),
    )
    bound = (router or default_router()).bind(ForgeTask.AGENT_STEP, provider="local")
    plan_generated = False

    def attempt() -> AttemptResult:
        nonlocal plan_generated
        plan = bound.complete_structured(_agent_prompt(result, record), _AGENT_PLAN_SCHEMA)
        plan_generated = True

        actual_provider = bound.last_provider_used or ""
        if actual_provider != "local":
            raise RuntimeError("agent_provider_not_local")
        episode.provider = actual_provider
        episode.model = str(getattr(bound, "last_model_used", "") or "")
        episode.deployment = Deployment.LOCAL
        episode.provenance = LearningDataProvenance.LOCAL_AI_OUTPUT
        episode.record_step(EpisodeStep(
            kind=StepKind.GENERATE,
            name="agent_tool_plan",
            succeeded=True,
            detail_code="structured_plan",
            at=time.time(),
        ))

        raw_tools = plan.get("tools", [])
        requested = [str(name) for name in raw_tools] if isinstance(raw_tools, list) else []
        requested.append("validate_forge_document")
        selected = tuple(dict.fromkeys(requested))

        tool_results = []
        for tool_name in selected:
            tool_results.append(loop.call_tool(ToolCall(
                tool=tool_name,
                call_id=uuid4().hex,
            )))

        fresh_validation = validate_forge_document(getattr(result, "forge_document"))
        validator_outcome = (
            VerificationOutcome.PASSED
            if bool(getattr(fresh_validation, "valid", False))
            else VerificationOutcome.FAILED
        )
        tools_ok = all(item.ok for item in tool_results)

        failure_code = ""
        if not tools_ok:
            failure_code = "tool_failure"
        elif validator_outcome is VerificationOutcome.FAILED:
            failure_code = "validator_failed"

        return AttemptResult(
            succeeded=not failure_code,
            failure_code=failure_code,
            validator=validator_outcome,
            # Build/test/runtime/visual were not executed in 020B. UNKNOWN is the
            # truthful value; SKIPPED means "not applicable" in the Episode contract.
            build=VerificationOutcome.UNKNOWN,
            test=VerificationOutcome.UNKNOWN,
            runtime=VerificationOutcome.UNKNOWN,
            visual=VerificationOutcome.UNKNOWN,
        )

    try:
        report = loop.run(attempt=attempt, repair=lambda current: current)
    except Exception:  # noqa: BLE001 — provider/agent failure must not destroy a valid generation
        episode.record_step(EpisodeStep(
            kind=StepKind.GENERATE,
            name="agent_tool_plan",
            succeeded=False,
            detail_code="provider_or_agent_error",
            at=time.time(),
        ))
        store.finish(episode.episode_id, EpisodeOutcome.FAILED)
        return AgentRunSummary(
            requested=True,
            executed=plan_generated,
            outcome=EpisodeOutcome.FAILED,
            episode_id=episode.episode_id,
            provider=episode.provider,
            model=episode.model,
            tool_calls=len(broker.calls),
            tools_used=tuple(call.tool for call in broker.calls),
            validator_outcome=episode.validator_outcome,
            stopped_because="provider_or_agent_error",
        )

    # The verification task itself can succeed while the generated application is
    # known to be incomplete. Preserve that distinction as PARTIAL rather than
    # pretending the artifact completed the user's request or calling it a repair
    # budget exhaustion.
    critical_gap = bool(
        getattr(getattr(result, "capability_gap", None), "blocks_completion", False)
    )
    final_outcome = (
        EpisodeOutcome.PARTIAL
        if report.outcome is EpisodeOutcome.SUCCEEDED and critical_gap
        else report.outcome
    )
    store.finish(episode.episode_id, final_outcome)
    return AgentRunSummary(
        requested=True,
        executed=True,
        outcome=final_outcome,
        episode_id=episode.episode_id,
        provider=episode.provider,
        model=episode.model,
        tool_calls=report.tool_calls,
        tools_used=tuple(call.tool for call in broker.calls),
        validator_outcome=episode.validator_outcome,
        stopped_because=(
            "critical_capability_gap"
            if final_outcome is EpisodeOutcome.PARTIAL
            else report.stopped_because
        ),
    )
