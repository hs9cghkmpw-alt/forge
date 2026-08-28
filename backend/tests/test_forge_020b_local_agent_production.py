"""FORGE-020B Local Tool Agent production wiring tests."""

from __future__ import annotations

import json
import os
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from app.ai.agent.production import run_local_agent_verification  # noqa: E402
from app.ai.gateway.ai_router import AIRouter, ModelDescriptor  # noqa: E402
from app.ai.gateway.generation_evidence import (  # noqa: E402
    GenerationRecord,
    GenerationSource,
    default_generation_store,
)
from app.ai.gateway.learning_events import TrainingUse  # noqa: E402
from app.ai.learning.episode import (  # noqa: E402
    EpisodeOutcome,
    StepKind,
    VerificationOutcome,
    default_episode_store,
)
from app.ai.runtime.capability_gap import CapabilityGap  # noqa: E402

try:
    from fastapi.testclient import TestClient
    from app.main import app
    _FASTAPI_AVAILABLE = True
except ImportError:  # pragma: no cover
    _FASTAPI_AVAILABLE = False


class _AgentAdapter:
    provider_name = "local"
    model = "qwen-test-double"

    def __init__(self, plan: dict) -> None:
        self.plan = plan
        self.calls = 0
        self.last_structured_output_mode = "json_schema"

    def complete_structured(self, prompt: str, response_schema: dict) -> dict:
        self.calls += 1
        return dict(self.plan)


def _router_for(plan: dict) -> tuple[AIRouter, _AgentAdapter]:
    adapter = _AgentAdapter(plan)
    router = AIRouter(
        resolve=lambda name: adapter,
        catalog=(ModelDescriptor(provider="local", is_local=True),),
    )
    return router, adapter


@unittest.skipUnless(_FASTAPI_AVAILABLE, "fastapi/pydantic unavailable")
class TestHTTPProductionWiring(unittest.TestCase):
    def setUp(self) -> None:
        default_generation_store().reset()
        default_episode_store().reset()
        self.client = TestClient(app)

    def _generate(self, plan: dict, *, text: str = "毎日の支出を記録して合計を見たい"):
        router, adapter = _router_for(plan)
        with patch("app.ai.agent.production.default_router", return_value=router):
            response = self.client.post(
                "/api/v1/ai/generate",
                json={
                    "version": "1.0",
                    "input": {
                        "natural_language": text,
                        "generation_options": {
                            "provider": "mock",
                            "agent_mode": "verify",
                        },
                    },
                },
            )
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["status"], "success", response.text)
        return response.json()["result"], adapter

    def test_http_generate_reaches_real_agent_runner(self) -> None:
        result, adapter = self._generate({
            "tools": ["inspect_forge_document", "validate_forge_document"],
            "reason_code": "verify_structure",
        })
        agent = result["agent"]
        self.assertTrue(agent["requested"])
        self.assertTrue(agent["executed"])
        self.assertEqual(agent["provider"], "local")
        self.assertEqual(agent["model"], "qwen-test-double")
        self.assertEqual(agent["validator_outcome"], "passed")
        self.assertEqual(agent["outcome"], "succeeded")
        self.assertGreaterEqual(agent["tool_calls"], 1)
        self.assertEqual(adapter.calls, 1)

    def test_validator_is_mandatory_even_when_model_omits_it(self) -> None:
        result, _ = self._generate({
            "tools": ["inspect_forge_document"],
            "reason_code": "inspect",
        })
        self.assertIn("validate_forge_document", result["agent"]["tools_used"])

    def test_unregistered_side_effecting_tool_cannot_execute(self) -> None:
        result, _ = self._generate({
            "tools": ["write_file"],
            "reason_code": "try_write",
        })
        agent = result["agent"]
        self.assertEqual(agent["outcome"], "abandoned")
        self.assertIn("write_file", agent["tools_used"])
        self.assertEqual(agent["stopped_because"], "max_repair_rounds")

    def test_episode_links_generation_evidence_and_has_no_training_right(self) -> None:
        phrase = "毎日の支出を記録して合計を見たい"
        result, _ = self._generate(
            {"tools": ["validate_forge_document"], "reason_code": "verify"},
            text=phrase,
        )
        episode = default_episode_store().get(result["agent"]["episode_id"])
        self.assertIsNotNone(episode)
        assert episode is not None
        self.assertTrue(episode.generation_evidence_uid)
        self.assertIs(episode.training_use, TrainingUse.UNKNOWN)
        self.assertFalse(episode.has_usable_training_right)
        self.assertNotIn(phrase, json.dumps(episode.to_dict(), ensure_ascii=False))
        self.assertIs(episode.build_outcome, VerificationOutcome.SKIPPED)
        self.assertIs(episode.test_outcome, VerificationOutcome.SKIPPED)
        self.assertIs(episode.runtime_outcome, VerificationOutcome.UNKNOWN)
        self.assertIs(episode.visual_outcome, VerificationOutcome.UNKNOWN)

    def test_tool_steps_have_call_ids_but_no_tool_body(self) -> None:
        result, _ = self._generate(
            {"tools": ["inspect_capability_gap"], "reason_code": "gap"}
        )
        episode = default_episode_store().get(result["agent"]["episode_id"])
        assert episode is not None
        tool_steps = [step for step in episode.steps if step.kind is StepKind.TOOL_CALL]
        self.assertTrue(tool_steps)
        self.assertTrue(all(step.references for step in tool_steps))
        serialized = json.dumps([step.to_dict() for step in tool_steps])
        self.assertNotIn("content", serialized)


class TestObjectiveTruthBeatsModelClaim(unittest.TestCase):
    def setUp(self) -> None:
        default_generation_store().reset()
        default_episode_store().reset()

    def test_invalid_document_cannot_become_success(self) -> None:
        stored = default_generation_store().record(GenerationRecord(
            source=GenerationSource.LOCAL_AI,
            domain="generated",
            validator_passed=False,
        ))
        invalid = SimpleNamespace(
            generation_ref=stored.ref,
            forge_document={},
            capability_gap=CapabilityGap(),
            quality=None,
        )
        router, _ = _router_for({
            "tools": ["validate_forge_document"],
            "reason_code": "all_good",
            "success": True,
        })
        summary = run_local_agent_verification(invalid, router=router)
        self.assertIs(summary.outcome, EpisodeOutcome.ABANDONED)
        self.assertIs(summary.validator_outcome, VerificationOutcome.FAILED)
        self.assertNotEqual(summary.outcome, EpisodeOutcome.SUCCEEDED)

    def test_missing_generation_lineage_fails_closed_before_model_call(self) -> None:
        router, adapter = _router_for({
            "tools": ["validate_forge_document"],
            "reason_code": "verify",
        })
        orphan = SimpleNamespace(
            generation_ref=None,
            forge_document={},
            capability_gap=CapabilityGap(),
            quality=None,
        )
        summary = run_local_agent_verification(orphan, router=router)
        self.assertIs(summary.outcome, EpisodeOutcome.FAILED)
        self.assertFalse(summary.executed)
        self.assertEqual(summary.stopped_because, "missing_generation_evidence")
        self.assertEqual(adapter.calls, 0)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
