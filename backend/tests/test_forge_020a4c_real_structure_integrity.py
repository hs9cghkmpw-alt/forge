from app.ai.foundation.openai_compatible import OpenAICompatibleAdapter
from app.ai.gateway.benchmark_evidence import Verification
from app.ai.gateway.capability_evidence import GenerationStructureSource, StructureProvider
from app.ai.gateway.generation_evidence import GenerationRecord, GenerationSource
from app.ai.gateway.learning_events import Deployment
from app.ai.gateway.local_model_evidence import LocalRuntimeBackend, RealLocalModelRun
from app.ai.gateway.tasks import ForgeTask


def _passing_run(**changes) -> RealLocalModelRun:
    values = dict(
        provider="local",
        model="qwen-test",
        task=ForgeTask.ENTITY_SYNTHESIS,
        observed_tasks=(ForgeTask.ENTITY_SYNTHESIS,),
        structure_source=GenerationStructureSource.AI_ENTITY_SYNTHESIS,
        structure_provider=StructureProvider.LOCAL,
        structure_task=ForgeTask.ENTITY_SYNTHESIS.value,
        entity_synthesis_strict_contract_passed=True,
        entity_synthesis_repairs=(),
        structured_output_mode="json_schema",
        domain_resolution="generated",
        runtime_backend=LocalRuntimeBackend.OLLAMA,
        model_id="qwen-test",
        deployment=Deployment.LOCAL,
        latency_ms=1.0,
        structured_output_ok=True,
        validator_passed=True,
        generation_evidence_uid="generation-uid",
        generation_source=GenerationSource.LOCAL_AI,
        verification=Verification.REAL,
    )
    values.update(changes)
    return RealLocalModelRun(**values)


def test_repaired_output_cannot_count_even_if_validator_passes():
    run = _passing_run(
        entity_synthesis_strict_contract_passed=False,
        entity_synthesis_repairs=("unknown_type_to_string",),
    )
    assert run.validator_passed is True
    assert run.counts_as_real_local is False
    assert any("sanitizer" in reason for reason in run.why_not_counted())


def test_unknown_contract_evidence_fails_closed():
    assert _passing_run(entity_synthesis_strict_contract_passed=False).counts_as_real_local is False


def test_json_object_fallback_does_not_prove_strict_level0_contract():
    assert _passing_run(structured_output_mode="json_object").counts_as_real_local is False


def test_strict_unrepaired_run_can_pass_integrity_predicate():
    assert _passing_run().counts_as_real_local is True


def test_generation_record_serializer_keeps_diagnosis_without_raw_content():
    record = GenerationRecord(
        source=GenerationSource.LOCAL_AI,
        domain="generic",
        validator_passed=True,
        entity_synthesis_attempted=True,
        entity_synthesis_accepted=True,
        entity_synthesis_raw_schema_valid=False,
        entity_synthesis_repairs=("required_injected",),
        entity_synthesis_fields_received=2,
        entity_synthesis_fields_accepted=2,
        entity_synthesis_strict_contract_passed=False,
        entity_synthesis_structured_output_mode="json_schema",
    )
    payload = record.to_dict()
    assert payload["entity_synthesis_attempted"] is True
    assert payload["entity_synthesis_repairs"] == ["required_injected"]
    assert payload["entity_synthesis_strict_contract_passed"] is False
    assert "prompt" not in payload
    assert "raw_output" not in payload
    assert "user_text" not in payload


def test_openai_compatible_records_actual_json_object_mode(monkeypatch):
    adapter = OpenAICompatibleAdapter(
        provider_name="local", base_url="http://unused", model="qwen-test"
    )
    monkeypatch.setattr(adapter, "_chat", lambda *args, **kwargs: '{"ok": true}')
    assert adapter.complete_structured("x", {}) == {"ok": True}
    assert adapter.last_structured_output_mode == "json_object"
