from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")

def write(path: str, text: str) -> None:
    target = ROOT / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8")

def replace_once(path: str, old: str, new: str) -> None:
    text = read(path)
    if old not in text:
        raise RuntimeError(f"marker not found in {path}: {old[:120]!r}")
    if text.count(old) != 1:
        raise RuntimeError(f"marker not unique in {path}: {old[:120]!r}")
    write(path, text.replace(old, new, 1))

replace_once(
    "backend/app/ai/gateway/tasks.py",
    '''    ENTITY_SYNTHESIS = "entity_synthesis"
    """「このアプリが繰り返し記録する1件分のデータ」の設計。
    `forge_ai/core/ir/entity_synthesizer.py`が呼ぶ。"""

    FORGE_LANGUAGE_UPDATE = "forge_language_update"
''',
    '''    ENTITY_SYNTHESIS = "entity_synthesis"
    """「このアプリが繰り返し記録する1件分のデータ」の設計。
    `forge_ai/core/ir/entity_synthesizer.py`が呼ぶ。"""

    AGENT_STEP = "agent_step"
    """FORGE-020B。Local Agent が生成物を道具で検証する1手。
    `app.ai.agent.production` が本番の生成経路から実際に呼ぶ。"""

    FORGE_LANGUAGE_UPDATE = "forge_language_update"
''',
)

replace_once(
    "backend/app/ai/gateway/ai_router.py",
    '''    last_provider_used: str | None = field(default=None, init=False)
    last_structured_output_mode: str = field(default="", init=False)
    """直近の`complete_structured()`で**実際に**応答を返したProvider名。
''',
    '''    last_provider_used: str | None = field(default=None, init=False)
    last_model_used: str = field(default="", init=False)
    last_structured_output_mode: str = field(default="", init=False)
    """直近の`complete_structured()`で**実際に**応答を返したProvider名。
''',
)
replace_once(
    "backend/app/ai/gateway/ai_router.py",
    '''        self.last_provider_used = result.provider_used
        self.last_structured_output_mode = result.structured_output_mode
        if result.experience_ref:
''',
    '''        self.last_provider_used = result.provider_used
        self.last_model_used = next(
            (
                attempt.model
                for attempt in reversed(result.attempts)
                if attempt.ok and attempt.provider == result.provider_used
            ),
            "",
        )
        self.last_structured_output_mode = result.structured_output_mode
        if result.experience_ref:
''',
)

replace_once(
    "backend/app/ai/agent/permission.py",
    '''    "read_runtime_error": PermissionTier.AUTO_ALLOW,
    "web_search": PermissionTier.AUTO_ALLOW,
''',
    '''    "read_runtime_error": PermissionTier.AUTO_ALLOW,
    "inspect_forge_document": PermissionTier.AUTO_ALLOW,
    "validate_forge_document": PermissionTier.AUTO_ALLOW,
    "inspect_capability_gap": PermissionTier.AUTO_ALLOW,
    "web_search": PermissionTier.AUTO_ALLOW,
''',
)

replace_once(
    "backend/app/ai/agent/tools.py",
    '''    tool: str
    outcome: ToolOutcome
    content: str = ""
''',
    '''    tool: str
    outcome: ToolOutcome
    call_id: str = ""
    content: str = ""
''',
)
replace_once(
    "backend/app/ai/agent/tools.py",
    '''            "tool": self.tool,
            "outcome": self.outcome.value,
            "error": self.error,
''',
    '''            "tool": self.tool,
            "outcome": self.outcome.value,
            "call_id": self.call_id,
            "error": self.error,
''',
)
for old, new in (
    (
        '''                call.tool, ToolOutcome.UNKNOWN_TOOL,
                error="登録されていない道具",
''',
        '''                call.tool, ToolOutcome.UNKNOWN_TOOL, call_id=call.call_id,
                error="登録されていない道具",
''',
    ),
    (
        '''            return ToolResult(call.tool, ToolOutcome.INVALID_ARGUMENTS, error=invalid)
''',
        '''            return ToolResult(
                call.tool, ToolOutcome.INVALID_ARGUMENTS, call_id=call.call_id, error=invalid
            )
''',
    ),
    (
        '''                call.tool, ToolOutcome.DENIED,
                error=decision.reason, permission=decision,
''',
        '''                call.tool, ToolOutcome.DENIED, call_id=call.call_id,
                error=decision.reason, permission=decision,
''',
    ),
    (
        '''                call.tool, ToolOutcome.FAILED,
                error=redact_secrets(f"{type(error).__name__}: {error}"),
''',
        '''                call.tool, ToolOutcome.FAILED, call_id=call.call_id,
                error=redact_secrets(f"{type(error).__name__}: {error}"),
''',
    ),
    (
        '''            call.tool, ToolOutcome.OK, content=content, permission=decision,
''',
        '''            call.tool, ToolOutcome.OK, call_id=call.call_id,
            content=content, permission=decision,
''',
    ),
):
    replace_once("backend/app/ai/agent/tools.py", old, new)

replace_once(
    "backend/app/ai/agent/loop.py",
    '''            kind=StepKind.TOOL_CALL, name=call.tool,
            succeeded=result.ok, detail_code=result.outcome.value,
            duration_ms=result.duration_ms, at=time.time(),
''',
    '''            kind=StepKind.TOOL_CALL, name=call.tool,
            succeeded=result.ok, detail_code=result.outcome.value,
            references=((call.call_id,) if call.call_id else ()),
            duration_ms=result.duration_ms, at=time.time(),
''',
)

replace_once(
    "backend/app/ai/agent/toolset.py",
    '''import shlex
import subprocess
''',
    '''import json
import shlex
import subprocess
''',
)
replace_once(
    "backend/app/ai/agent/toolset.py",
    '''__all__ = ["CommandRunner", "build_default_toolset"]
''',
    '''__all__ = [
    "CommandRunner",
    "build_default_toolset",
    "build_generation_inspection_toolset",
]
''',
)
toolset_addition = r'''


def build_generation_inspection_toolset(
    *,
    forge_document: dict,
    capability_gap: object,
    validator,
    permissions: PermissionBroker | None = None,
) -> ToolBroker:
    """FORGE-020B production toolset.

    The Local Agent does not receive the Forge server repository or arbitrary shell.
    It can inspect only structural facts about the generated document, capability
    identifiers, and a fresh deterministic Validator result. Tool outputs deliberately
    exclude document values, user text, prompts, and validation messages.
    """
    broker = ToolBroker(permissions=permissions, in_sandbox=False)
    broker.register(ToolSpec(
        name="inspect_forge_document",
        description="生成済みForge Documentの構造件数だけを調べる",
        run=lambda: json.dumps(_document_structure_summary(forge_document), sort_keys=True),
    ))
    broker.register(ToolSpec(
        name="validate_forge_document",
        description="Forge Validatorを再実行し、合否と分類件数だけを見る",
        run=lambda: json.dumps(_validation_summary(validator(forge_document)), sort_keys=True),
    ))
    broker.register(ToolSpec(
        name="inspect_capability_gap",
        description="不足・部分対応CapabilityのIDと完了阻害フラグだけを見る",
        run=lambda: json.dumps(_capability_gap_summary(capability_gap), sort_keys=True),
    ))
    return broker


def _document_structure_summary(document: dict) -> dict[str, object]:
    widget_types: dict[str, int] = {}
    action_count = 0
    state_count = 0

    def walk(value: object) -> None:
        nonlocal action_count, state_count
        if isinstance(value, dict):
            kind = value.get("type")
            if isinstance(kind, str):
                widget_types[kind] = widget_types.get(kind, 0) + 1
            if "action" in value or "actions" in value:
                action_count += 1
            for key, child in value.items():
                if key == "state":
                    if isinstance(child, dict):
                        state_count += len(child)
                    elif isinstance(child, list):
                        state_count += len(child)
                walk(child)
        elif isinstance(value, list):
            for child in value:
                walk(child)

    walk(document)
    screens = document.get("screens", ())
    return {
        "forge_language_version": str(document.get("version", "") or ""),
        "screen_count": len(screens) if isinstance(screens, list) else 0,
        "widget_count": sum(widget_types.values()),
        "widget_types": dict(sorted(widget_types.items())),
        "action_container_count": action_count,
        "state_entry_count": state_count,
    }


def _validation_summary(validation: object) -> dict[str, object]:
    errors = tuple(getattr(validation, "errors", ()) or ())
    warnings = tuple(getattr(validation, "warnings", ()) or ())
    return {
        "valid": bool(getattr(validation, "valid", False)),
        "error_count": len(errors),
        "warning_count": len(warnings),
        "error_categories": sorted({
            str(getattr(item, "category", "") or "") for item in errors
            if getattr(item, "category", "")
        }),
        "warning_categories": sorted({
            str(getattr(item, "category", "") or "") for item in warnings
            if getattr(item, "category", "")
        }),
    }


def _capability_gap_summary(gap: object) -> dict[str, object]:
    return {
        "missing": list(getattr(gap, "missing", ()) or ()),
        "partial": list(getattr(gap, "partial", ()) or ()),
        "critical": list(getattr(gap, "critical", ()) or ()),
        "blocks_completion": bool(getattr(gap, "blocks_completion", False)),
    }
'''
text = read("backend/app/ai/agent/toolset.py")
if "def build_generation_inspection_toolset(" in text:
    raise RuntimeError("generation inspection toolset already exists")
write("backend/app/ai/agent/toolset.py", text + toolset_addition)

replace_once(
    "backend/app/ai/runtime/confirmation_store.py",
    '''    previous_answers: tuple[str, ...] = ()

    def is_expired''',
    '''    previous_answers: tuple[str, ...] = ()
    agent_mode: str = "off"
    """FORGE-020B。確認往復で opt-in Agent 設定を失わない。"""

    def is_expired''',
)
replace_once(
    "backend/app/ai/runtime/confirmation_store.py",
    '''        previous_answers: tuple[str, ...] = (),
    ) -> PendingConfirmation:
''',
    '''        previous_answers: tuple[str, ...] = (),
        agent_mode: str = "off",
    ) -> PendingConfirmation:
''',
)
replace_once(
    "backend/app/ai/runtime/confirmation_store.py",
    '''            previous_decision_trace=decision_trace,
            previous_answers=previous_answers,
        )
''',
    '''            previous_decision_trace=decision_trace,
            previous_answers=previous_answers,
            agent_mode=agent_mode,
        )
''',
)

replace_once(
    "backend/app/schemas/ai.py",
    '''    max_repair_attempts: int | None = Field(default=None, ge=0, le=2)


class GenerateInputDTO''',
    '''    max_repair_attempts: int | None = Field(default=None, ge=0, le=2)
    agent_mode: Literal["off", "verify"] = Field(
        default="off",
        description=(
            "FORGE-020B Local Tool Agent。off=従来経路、verify=生成後にLocal Agentが"
            "read-only Tool Broker経由で客観検証する。現段階では品質/遅延の実測前なので"
            "既定では有効化しない。"
        ),
    )


class GenerateInputDTO''',
)
agent_dto = r'''

class AgentRunDTO(BaseModel):
    """FORGE-020B Local Tool Agent の外部向け要約。

    Tool本文、Prompt、ユーザー発話、Generation Evidence UIDは返さない。
    """

    requested: bool = True
    executed: bool = False
    outcome: Literal["succeeded", "partial", "failed", "abandoned", "unknown"] = "unknown"
    episode_id: str = ""
    provider: str = ""
    model: str = ""
    tool_calls: int = 0
    tools_used: list[str] = Field(default_factory=list)
    validator_outcome: Literal["passed", "failed", "skipped", "unsupported", "unknown"] = "unknown"
    stopped_because: str = ""

'''
replace_once(
    "backend/app/schemas/ai.py",
    '''class GenerateResultDTO(BaseModel):
''',
    agent_dto + '''class GenerateResultDTO(BaseModel):
''',
)
replace_once(
    "backend/app/schemas/ai.py",
    '''    diagnostics: DiagnosticsDTO
    artifact: ArtifactRefDTO | None = Field(
''',
    '''    diagnostics: DiagnosticsDTO
    agent: AgentRunDTO | None = None
    artifact: ArtifactRefDTO | None = Field(
''',
)
replace_once(
    "backend/app/schemas/ai.py",
    '''    provider: Literal["mock", "gemini", "local"] | None = Field(
        default=None,
        description="ConversationEngineが使うLLM Provider。既定は'mock'。",
    )
''',
    '''    provider: Literal["mock", "gemini", "local"] | None = Field(
        default=None,
        description="ConversationEngineが使うLLM Provider。既定は'mock'。",
    )
    agent_mode: Literal["off", "verify"] = Field(
        default="off",
        description="BUILD後にFORGE-020B Local Tool Agent検証を行うか。",
    )
''',
)

replace_once(
    "backend/app/routers/ai.py",
    '''from app.ai.runtime.confirmation_store import (
''',
    '''from app.ai.agent.production import AgentRunSummary, run_local_agent_verification
from app.ai.runtime.confirmation_store import (
''',
)
replace_once(
    "backend/app/routers/ai.py",
    '''    ArtifactRefDTO,
    ConfirmationAnswerRequest,
''',
    '''    AgentRunDTO,
    ArtifactRefDTO,
    ConfirmationAnswerRequest,
''',
)
replace_once(
    "backend/app/routers/ai.py",
    '''def _result_dto(result, *, session_id: str | None = None) -> GenerateResultDTO:  # noqa: ANN001 — PipelineRunResult
    return GenerateResultDTO(
''',
    '''def _agent_dto(summary: AgentRunSummary | None) -> AgentRunDTO | None:
    return AgentRunDTO(**summary.to_dict()) if summary is not None else None


def _result_dto(
    result, *, session_id: str | None = None, agent_summary: AgentRunSummary | None = None
) -> GenerateResultDTO:  # noqa: ANN001 — PipelineRunResult
    return GenerateResultDTO(
''',
)
replace_once(
    "backend/app/routers/ai.py",
    '''        diagnostics=_diagnostics_dto(result.diagnostics),
        # **作れないと分かっていることを返す**''',
    '''        diagnostics=_diagnostics_dto(result.diagnostics),
        agent=_agent_dto(agent_summary),
        # **作れないと分かっていることを返す**''',
)
replace_once(
    "backend/app/routers/ai.py",
    '''def _success_response(result) -> GenerateSuccessResponse:  # noqa: ANN001 — PipelineRunResult
    return GenerateSuccessResponse(result=_result_dto(result))
''',
    '''def _success_response(
    result, *, agent_mode: str = "off"
) -> GenerateSuccessResponse:  # noqa: ANN001 — PipelineRunResult
    agent_summary = (
        run_local_agent_verification(result) if agent_mode == "verify" else None
    )
    return GenerateSuccessResponse(result=_result_dto(result, agent_summary=agent_summary))
''',
)
replace_once(
    "backend/app/routers/ai.py",
    '''    previous_answers: tuple[str, ...] = (),
):
''',
    '''    previous_answers: tuple[str, ...] = (),
    agent_mode: str = "off",
):
''',
)
replace_once(
    "backend/app/routers/ai.py",
    '''            result, natural_language, round_count=round_count, previous_answers=all_answers
        )
    return _success_response(result)
''',
    '''            result,
            natural_language,
            round_count=round_count,
            previous_answers=all_answers,
            agent_mode=agent_mode,
        )
    return _success_response(result, agent_mode=agent_mode)
''',
)
replace_once(
    "backend/app/routers/ai.py",
    '''    previous_answers: tuple[str, ...] = (),
) -> GenerateNeedsConfirmationResponse:
''',
    '''    previous_answers: tuple[str, ...] = (),
    agent_mode: str = "off",
) -> GenerateNeedsConfirmationResponse:
''',
)
replace_once(
    "backend/app/routers/ai.py",
    '''        previous_answers=previous_answers,
    )
''',
    '''        previous_answers=previous_answers,
        agent_mode=agent_mode,
    )
''',
)
replace_once(
    "backend/app/routers/ai.py",
    '''    max_repair_attempts = options.max_repair_attempts if options else None

    return _run_pipeline_and_build_response(
''',
    '''    max_repair_attempts = options.max_repair_attempts if options else None
    agent_mode = options.agent_mode if options else "off"

    return _run_pipeline_and_build_response(
''',
)
replace_once(
    "backend/app/routers/ai.py",
    '''        max_repair_attempts=max_repair_attempts,
        round_count=1,
    )
''',
    '''        max_repair_attempts=max_repair_attempts,
        round_count=1,
        agent_mode=agent_mode,
    )
''',
)
replace_once(
    "backend/app/routers/ai.py",
    '''        clarification_answer=answer,
        previous_answers=record.previous_answers,
    )
''',
    '''        clarification_answer=answer,
        previous_answers=record.previous_answers,
        agent_mode=record.agent_mode,
    )
''',
)
replace_once(
    "backend/app/routers/ai.py",
    '''        return _needs_confirmation_response_with_input(result, build_brief, round_count=1)
''',
    '''        return _needs_confirmation_response_with_input(
            result, build_brief, round_count=1, agent_mode=request.agent_mode
        )
''',
)
replace_once(
    "backend/app/routers/ai.py",
    '''    build_provider_name = result.diagnostics.provider_used or provider_name
    return ConverseBuildResponse(
''',
    '''    build_provider_name = result.diagnostics.provider_used or provider_name
    agent_summary = (
        run_local_agent_verification(result)
        if request.agent_mode == "verify"
        else None
    )
    return ConverseBuildResponse(
''',
)
replace_once(
    "backend/app/routers/ai.py",
    '''        result=_result_dto(result, session_id=session.session_id), readiness=step_result.readiness.value,
''',
    '''        result=_result_dto(
            result, session_id=session.session_id, agent_summary=agent_summary
        ), readiness=step_result.readiness.value,
''',
)

replace_once(
    "backend/tests/test_forge_020_production_wiring.py",
    '''    def test_the_agent_layer_has_no_production_caller(self) -> None:
        sources = self._production_sources()
        for module in ("app.ai.agent.loop", "app.ai.agent.toolset", "app.ai.agent.web"):
            self.assertNotIn(module, sources, f"{module} が本番から参照されている")

''',
    '''    def test_the_agent_layer_has_a_production_caller(self) -> None:
        sources = self._production_sources()
        self.assertIn(
            "app.ai.agent.production", sources,
            "020B Agent production runner がHTTP本線から参照されていない",
        )

    def test_web_layer_is_still_not_claimed_as_wired(self) -> None:
        sources = self._production_sources()
        self.assertNotIn(
            "app.ai.agent.web", sources,
            "Webは020D。020Bで本番接続したことにしない",
        )

''',
)
replace_once(
    "backend/tests/test_forge_020_production_wiring.py",
    '''    Agent / Web / Teacher / Gym / Novel Benchmark / Dataset / Adapter は
    今回**契約とテストだけ**である。実 Local Model が無い状態で本番の
''',
    '''    FORGE-020Bで Agent / Tool は本番へ接続した。Web / Teacher / Gym /
    Novel Benchmark / Dataset / Adapter はまだ**契約とテストだけ**である。
    実 Local Model が無い状態で未測定の層を本番へ差し込むと、
''',
)

test_path = "backend/tests/test_confirmation_store.py"
text = read(test_path)
if "test_agent_mode_survives_confirmation_round_trip" not in text:
    anchor = '\n\nif __name__ == "__main__":'
    if anchor not in text:
        raise RuntimeError("confirmation store test anchor missing")
    addition = r'''

class TestAgentModePersistence(unittest.TestCase):
    def test_agent_mode_survives_confirmation_round_trip(self) -> None:
        store = ConfirmationStore()
        pending = store.create(
            original_natural_language="x",
            engine="forge_ai",
            provider="local",
            reached_stage="ambiguity",
            reason="missing",
            agent_mode="verify",
        )
        record, original, answer = store.consume_and_advance(
            pending.request_id, answer="y"
        )
        self.assertEqual(original, "x")
        self.assertEqual(answer, "y")
        self.assertEqual(record.agent_mode, "verify")
'''
    write(test_path, text.replace(anchor, addition + anchor, 1))

print("FORGE-020B apply complete")
