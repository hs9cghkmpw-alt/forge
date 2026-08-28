"""FORGE-020A4 — Level 0 probe preflight の回帰・mutation guard。"""

from __future__ import annotations

import unittest

from app.ai.gateway.capability_evidence import (
    GenerationStructureSource,
    StructureProvider,
)
from app.ai.gateway.level0_preflight import (
    Level0PreflightFacts,
    Level0PreflightOutcome,
    evaluate_level0_probe_preflight,
)
from app.ai.gateway.tasks import ForgeTask


class TestLevel0PreflightEvaluator(unittest.TestCase):
    def _eligible(self, **overrides) -> Level0PreflightFacts:  # noqa: ANN003
        values = {
            "domain_resolution": "generated",
            "structure_source": GenerationStructureSource.AI_ENTITY_SYNTHESIS,
            "structure_provider": StructureProvider.TEST_DOUBLE,
            "structure_task": ForgeTask.ENTITY_SYNTHESIS.value,
            "observed_tasks": (ForgeTask.COGNITIVE_STAGE, ForgeTask.ENTITY_SYNTHESIS),
            "validator_passed": True,
            "generation_evidence_uid": "preflight-generation-uid",
            "entity_synthesis_attempted": True,
            "entity_synthesis_accepted": True,
            "entity_synthesis_rejection_reason": None,
        }
        values.update(overrides)
        return Level0PreflightFacts(**values)

    def test_only_complete_mock_entity_synthesis_is_eligible(self) -> None:
        result = evaluate_level0_probe_preflight(self._eligible())
        self.assertTrue(result.eligible_for_real_run, result.reasons)
        self.assertIs(result.outcome, Level0PreflightOutcome.ELIGIBLE_FOR_REAL_RUN)

    def test_curated_probe_is_rejected_before_real_model_run(self) -> None:
        result = evaluate_level0_probe_preflight(
            self._eligible(
                domain_resolution="curated",
                structure_source=GenerationStructureSource.CURATED,
                structure_provider=StructureProvider.NONE,
                structure_task="",
                observed_tasks=(),
                entity_synthesis_attempted=False,
                entity_synthesis_accepted=False,
            )
        )
        self.assertFalse(result.eligible_for_real_run)
        self.assertIs(result.outcome, Level0PreflightOutcome.CURATED_BYPASS)

    def test_deterministic_structure_is_not_an_eligible_probe(self) -> None:
        result = evaluate_level0_probe_preflight(
            self._eligible(
                structure_source=(
                    GenerationStructureSource.DETERMINISTIC_CAPABILITY_PLAN
                ),
                structure_provider=StructureProvider.NONE,
                structure_task="",
                entity_synthesis_attempted=False,
                entity_synthesis_accepted=False,
            )
        )
        self.assertFalse(result.eligible_for_real_run)
        self.assertIs(result.outcome, Level0PreflightOutcome.DETERMINISTIC_BYPASS)

    def test_synthesis_rejection_is_visible_not_generic_failure(self) -> None:
        result = evaluate_level0_probe_preflight(
            self._eligible(
                structure_source=GenerationStructureSource.UNKNOWN,
                structure_provider=StructureProvider.NONE,
                structure_task="",
                entity_synthesis_accepted=False,
                entity_synthesis_rejection_reason="invalid_identifier",
            )
        )
        self.assertFalse(result.eligible_for_real_run)
        self.assertIs(result.outcome, Level0PreflightOutcome.SYNTHESIS_REJECTED)
        self.assertTrue(
            any("invalid_identifier" in reason for reason in result.reasons),
            result.reasons,
        )

    def test_cloud_or_local_provider_cannot_masquerade_as_mock_preflight(self) -> None:
        for provider in (StructureProvider.CLOUD, StructureProvider.LOCAL):
            with self.subTest(provider=provider):
                result = evaluate_level0_probe_preflight(
                    self._eligible(structure_provider=provider)
                )
                self.assertFalse(result.eligible_for_real_run)
                self.assertIs(result.outcome, Level0PreflightOutcome.WRONG_PROVIDER)

    def test_entity_synthesis_task_must_be_observed(self) -> None:
        result = evaluate_level0_probe_preflight(
            self._eligible(observed_tasks=(ForgeTask.COGNITIVE_STAGE,))
        )
        self.assertFalse(result.eligible_for_real_run)
        self.assertIs(result.outcome, Level0PreflightOutcome.WRONG_TASK)

    def test_structure_task_cannot_be_a_lookalike_string(self) -> None:
        result = evaluate_level0_probe_preflight(
            self._eligible(structure_task="entity_structure")
        )
        self.assertFalse(result.eligible_for_real_run)
        self.assertIs(result.outcome, Level0PreflightOutcome.WRONG_TASK)

    def test_missing_generation_evidence_uid_is_not_eligible(self) -> None:
        result = evaluate_level0_probe_preflight(
            self._eligible(generation_evidence_uid="")
        )
        self.assertFalse(result.eligible_for_real_run)
        self.assertIs(result.outcome, Level0PreflightOutcome.UNOBSERVABLE)

    def test_validator_failure_is_not_eligible(self) -> None:
        result = evaluate_level0_probe_preflight(
            self._eligible(validator_passed=False)
        )
        self.assertFalse(result.eligible_for_real_run)
        self.assertIs(result.outcome, Level0PreflightOutcome.VALIDATION_FAILED)

    def test_to_dict_contains_no_need_or_raw_model_output_field(self) -> None:
        payload = evaluate_level0_probe_preflight(self._eligible()).to_dict()
        rendered = repr(payload).lower()
        self.assertNotIn("natural_language", rendered)
        self.assertNotIn("raw_output", rendered)
        self.assertNotIn("prompt", rendered)


try:
    from fastapi.testclient import TestClient

    from app.ai.gateway.generation_evidence import default_generation_store
    from app.ai.gateway.learning_foundation import default_experience_store
    from app.main import app

    _FASTAPI_AVAILABLE = True
except ImportError:  # pragma: no cover
    _FASTAPI_AVAILABLE = False


@unittest.skipUnless(_FASTAPI_AVAILABLE, "FastAPI dependencies unavailable")
class TestProductionProbePreflight(unittest.TestCase):
    """production /generate + mock が本当に typed structure evidence を残すか。"""

    DEFAULT_PROBE = "盆栽の水やりの記録をつけたい"
    CURATED_TRAP = "毎日の支出を記録して合計を見たい"

    @staticmethod
    def _domain_resolution(result: dict) -> str:
        diagnostics = result.get("diagnostics") or {}
        for entry in diagnostics.get("decision_trace") or ():
            if entry.get("stage") == "domain_resolution":
                return str(entry.get("decision") or "").strip().lower()
        return ""

    def _run(self, need: str) -> tuple[Level0PreflightFacts, object]:
        generation_store = default_generation_store()
        experience_store = default_experience_store()
        before_generation = len(generation_store.all_records())
        before_experience = len(experience_store.all_records())

        response = TestClient(app).post(
            "/api/v1/ai/generate",
            json={
                "input": {
                    "natural_language": need,
                    "generation_options": {"provider": "mock"},
                },
            },
        )
        self.assertEqual(response.status_code, 200, response.text)
        result = response.json()["result"]

        records = generation_store.all_records()
        self.assertGreater(len(records), before_generation)
        record = records[-1]
        observed_tasks = tuple(dict.fromkeys(
            item.task
            for item in experience_store.all_records()[before_experience:]
        ))
        facts = Level0PreflightFacts(
            domain_resolution=self._domain_resolution(result),
            structure_source=record.structure_source,
            structure_provider=record.structure_provider,
            structure_task=record.structure_task,
            observed_tasks=observed_tasks,
            validator_passed=record.validator_passed,
            generation_evidence_uid=record.uid,
            entity_synthesis_attempted=record.entity_synthesis_attempted,
            entity_synthesis_accepted=record.entity_synthesis_accepted,
            entity_synthesis_rejection_reason=record.entity_synthesis_rejection_reason,
        )
        return facts, record

    def test_default_probe_reaches_mock_entity_synthesis_before_real_run(self) -> None:
        facts, record = self._run(self.DEFAULT_PROBE)
        result = evaluate_level0_probe_preflight(facts)
        self.assertTrue(result.eligible_for_real_run, result.to_dict())
        self.assertEqual(record.source.value, "test_double")
        self.assertIs(record.structure_provider, StructureProvider.TEST_DOUBLE)
        self.assertTrue(record.entity_synthesis_attempted)
        self.assertTrue(record.entity_synthesis_accepted)

    def test_known_curated_trap_is_rejected_by_preflight(self) -> None:
        facts, _ = self._run(self.CURATED_TRAP)
        result = evaluate_level0_probe_preflight(facts)
        self.assertFalse(result.eligible_for_real_run)
        self.assertIs(result.outcome, Level0PreflightOutcome.CURATED_BYPASS)


if __name__ == "__main__":
    unittest.main()
