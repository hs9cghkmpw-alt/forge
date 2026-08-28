"""FORGE-020A4B — Bridge stage-aware routing / Test Double schema guards."""

from __future__ import annotations

import unittest

from app.ai.gateway.tasks import ForgeTask
from app.ai.runtime.forge_ai_provider_bridge import ForgeAIProviderBridge
from forge_ai.prompt.prompt_builder import Prompt


class _RecordingBoundAdapter:
    def __init__(self, *, provider: str = "mock", fail: bool = False) -> None:
        self.task = ForgeTask.COGNITIVE_STAGE
        self.provider = provider
        self.fail = fail
        self.last_provider_used: str | None = None
        self.seen_tasks: list[ForgeTask] = []

    def complete_structured(self, prompt: str, response_schema: dict) -> dict:  # noqa: ARG002
        self.seen_tasks.append(self.task)
        self.last_provider_used = self.provider
        if self.fail:
            raise RuntimeError("synthetic failure")
        if "fields" in (response_schema.get("properties") or {}):
            return {
                "entity_name": "mock_result",
                "entity_label": "記録",
                "visual_style": "mock_result",
                # 020A4で実際に観測した壊れ方を再現する。
                "fields": ["盆栽", "水やり"],
            }
        return {}


def _prompt(stage: str) -> Prompt:
    return Prompt(
        stage=stage,
        system="system",
        instruction="instruction",
        context={"user_text": "盆栽の水やりの記録をつけたい"},
    )


class TestForgeAIProviderBridgeStageRouting(unittest.TestCase):
    def test_entity_synthesis_uses_dedicated_router_task_and_restores_default(self) -> None:
        adapter = _RecordingBoundAdapter(provider="mock")
        bridge = ForgeAIProviderBridge(adapter)

        response = bridge.complete(_prompt("entity_synthesis"))

        self.assertEqual(adapter.seen_tasks, [ForgeTask.ENTITY_SYNTHESIS])
        self.assertIs(adapter.task, ForgeTask.COGNITIVE_STAGE)
        self.assertEqual(bridge.provider_id, "mock")

        fields = response.structured["fields"]
        self.assertTrue(fields)
        self.assertIsInstance(fields[0], dict)
        self.assertEqual(fields[0]["type"], "string")

    def test_non_structure_stage_stays_cognitive_and_mock_output_is_unchanged(self) -> None:
        adapter = _RecordingBoundAdapter(provider="mock")
        bridge = ForgeAIProviderBridge(adapter)

        response = bridge.complete(_prompt("compile"))

        self.assertEqual(adapter.seen_tasks, [ForgeTask.COGNITIVE_STAGE])
        self.assertIs(adapter.task, ForgeTask.COGNITIVE_STAGE)
        # compile schema requires title. A global Mock schema repair would invent
        # {"title": "mock_result"} here and change existing naming semantics.
        # 020A4B repair is deliberately entity_synthesis-only.
        self.assertEqual(response.structured, {})

    def test_real_provider_output_is_never_repaired_by_test_double_guard(self) -> None:
        adapter = _RecordingBoundAdapter(provider="local")
        bridge = ForgeAIProviderBridge(adapter)

        response = bridge.complete(_prompt("entity_synthesis"))

        # Local/Cloudの構造不正をForge側で捏造してPASSさせてはならない。
        self.assertEqual(response.structured["fields"], ["盆栽", "水やり"])
        self.assertIs(adapter.task, ForgeTask.COGNITIVE_STAGE)

    def test_task_is_restored_even_when_provider_raises(self) -> None:
        adapter = _RecordingBoundAdapter(provider="mock", fail=True)
        bridge = ForgeAIProviderBridge(adapter)

        with self.assertRaisesRegex(RuntimeError, "synthetic failure"):
            bridge.complete(_prompt("entity_synthesis"))

        self.assertEqual(adapter.seen_tasks, [ForgeTask.ENTITY_SYNTHESIS])
        self.assertIs(adapter.task, ForgeTask.COGNITIVE_STAGE)


if __name__ == "__main__":
    unittest.main()
