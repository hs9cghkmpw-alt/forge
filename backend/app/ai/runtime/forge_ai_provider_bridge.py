"""ForgeAIProviderBridge。

`docs/spec/ADAPTER_CONTRACT_V1.md` 4.2節の実装。forge_ai.AIProvider
Protocol(`complete(prompt: Prompt) -> ProviderResponse`)を満たしながら、
内部ではM005の`LLMAdapter`(`complete_structured(prompt: str,
response_schema: dict) -> dict`)へ処理を委譲する。

forge_ai/自体はこのBridgeの存在を知らない(forge_ai/はMockProviderか、
このBridgeか、将来の別実装かを区別しない。forge_ai.AIProvider Protocolを
満たすオブジェクトなら何でも渡せる、という既存の設計をそのまま活かす)。

FORGE-020A4Bでは、Cognitive Pipeline全体を一律に
`ForgeTask.COGNITIVE_STAGE`として記録していた穴を閉じた。
`entity_synthesis` stageだけは request-local なBoundAdapterのTaskを
`ForgeTask.ENTITY_SYNTHESIS`へ一時的に切り替え、呼び出し後に必ず元へ戻す。
これにより、構造生成の仕事が本当にAIRouterのENTITY_SYNTHESISとして
観測される。Provider選択・Quota・Circuit Breaker自体は引き続きAIRouterが
唯一の出口である。
"""

from __future__ import annotations

from typing import Any

from forge_ai.core.semantics.capability_plan import plan_capabilities
from forge_ai.prompt.prompt_builder import Prompt
from forge_ai.provider.provider_interface import ProviderResponse

from app.ai.foundation.interfaces import LLMAdapter
from app.ai.gateway.tasks import ForgeTask


_RESPONSE_SCHEMAS: dict[str, dict[str, Any]] = {
    "meaning": {
        "type": "object",
        "properties": {
            "mentioned_concepts": {"type": "array", "items": {"type": "string"}},
            "mentioned_actions": {"type": "array", "items": {"type": "string"}},
            "keywords": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["mentioned_concepts", "mentioned_actions", "keywords"],
    },
    "intent": {
        "type": "object",
        "properties": {
            "goal": {"type": "string"},
            "required_concepts": {"type": "array", "items": {"type": "string"}},
            "required_actions": {"type": "array", "items": {"type": "string"}},
            "constraints": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["goal", "required_concepts", "required_actions", "constraints"],
    },
    "planning": {
        "type": "object",
        "properties": {
            "title": {"type": "string"},
            "screens": {"type": "array"},
            "data_entities": {"type": "array", "items": {"type": "string"}},
            "primary_flow": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["title", "screens", "data_entities", "primary_flow"],
    },
    "entity_synthesis": {
        "type": "object",
        "properties": {
            "entity_name": {"type": "string"},
            "entity_label": {"type": "string"},
            "visual_style": {
                "type": "string",
                "enum": ["calm", "warm", "vibrant", "neutral"],
            },
            "fields": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "label": {"type": "string"},
                        "type": {
                            "type": "string",
                            "enum": ["string", "number", "boolean", "date", "choice"],
                        },
                        "required": {"type": "boolean"},
                        "choices": {"type": "array", "items": {"type": "string"}},
                        "min_value": {"type": "number"},
                        "max_value": {"type": "number"},
                        "measure": {
                            "type": "string",
                            "enum": [
                                "additive",
                                "averageable",
                                "level",
                                "extremum",
                                "identifier",
                                "unknown",
                            ],
                        },
                    },
                    "required": ["name", "label", "type"],
                },
            },
        },
        "required": ["entity_name", "entity_label", "visual_style", "fields"],
    },
    "design_intent": {
        "type": "object",
        "properties": {
            "screen_density": {"type": "string"},
            "list_surface": {"type": "string"},
        },
        "required": ["screen_density", "list_surface"],
    },
    "compile": {
        "type": "object",
        "properties": {
            "title": {"type": "string"},
            "example_items": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["title"],
    },
    "repair": {
        "type": "object",
        "properties": {"addressed_issue_count": {"type": "integer"}},
        "required": ["addressed_issue_count"],
    },
}

_UNKNOWN_STAGE_SCHEMA: dict[str, Any] = {"type": "object"}


def _flatten_prompt_to_string(prompt: Prompt) -> str:
    """`Prompt`(system/instruction/context)を1本の文字列へ整形する。"""
    lines = [
        f"[SYSTEM]\n{prompt.system}",
        f"[INSTRUCTION]\n{prompt.instruction}",
        f"[CONTEXT]\n{prompt.context!r}",
    ]
    return "\n\n".join(lines)


def _task_for_stage(stage: str) -> ForgeTask:
    """Cognitive内部stageをAIRouterのTaskへ落とす。

    現時点で独立した品質・Level 0測定単位を持つのはEntity Synthesisだけ。
    他stageは従来どおりCOGNITIVE_STAGEへ残す。存在しないTaskを先に増やさない。
    """
    if stage == "entity_synthesis":
        return ForgeTask.ENTITY_SYNTHESIS
    return ForgeTask.COGNITIVE_STAGE


def _repair_test_double_value(value: Any, schema: dict[str, Any]) -> Any:
    """Entity Synthesis Test Doubleのnested schema形状を決定的に補う。

    FORGE-020A4でproduction preflightが実測した
    `fields: array<object>`→文字列配列というMock固有の不整合を、
    **Entity SynthesisのTest Double controlだけ**で補正するための関数。

    実LLM出力には使わない。また他のMock stageへも広げない。020A4B初版で
    全Mock stageへ適用したところ、既存の命名意味論を変えてしまいCIが
    回帰を検出したため、測定された欠陥の境界へ絞った。
    """
    schema_type = schema.get("type")

    if schema_type == "object":
        current = dict(value) if isinstance(value, dict) else {}
        properties = schema.get("properties")
        properties = properties if isinstance(properties, dict) else {}
        required = schema.get("required")
        required_names = set(required) if isinstance(required, list) else set()

        repaired: dict[str, Any] = {}
        for name, item_schema in properties.items():
            if not isinstance(item_schema, dict):
                continue
            if name in current:
                repaired[name] = _repair_test_double_value(current[name], item_schema)
            elif name in required_names:
                repaired[name] = _test_double_default(item_schema)

        for name, item in current.items():
            repaired.setdefault(name, item)
        return repaired

    if schema_type == "array":
        item_schema = schema.get("items")
        if not isinstance(item_schema, dict):
            return value if isinstance(value, list) else []

        current = value if isinstance(value, list) else []
        if item_schema.get("type") == "object":
            dict_items = [item for item in current if isinstance(item, dict)]
            if dict_items:
                return [
                    _repair_test_double_value(item, item_schema)
                    for item in dict_items
                ]
            return [_test_double_default(item_schema)]

        return [
            _repair_test_double_value(item, item_schema)
            for item in current
        ]

    if schema_type == "string":
        enum = schema.get("enum")
        if isinstance(enum, list) and enum:
            if isinstance(value, str) and value in enum:
                return value
            return str(enum[0])
        return value if isinstance(value, str) else "mock_result"

    if schema_type == "boolean":
        return value if isinstance(value, bool) else False

    if schema_type == "integer":
        return value if isinstance(value, int) and not isinstance(value, bool) else 0

    if schema_type == "number":
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return value
        return 0.0

    return value


def _test_double_default(schema: dict[str, Any]) -> Any:
    """SchemaからTest Double用の最小値を作る。意味品質は主張しない。"""
    schema_type = schema.get("type")

    if schema_type == "object":
        properties = schema.get("properties")
        properties = properties if isinstance(properties, dict) else {}
        required = schema.get("required")
        required_names = required if isinstance(required, list) else []
        return {
            name: _test_double_default(properties[name])
            for name in required_names
            if name in properties and isinstance(properties[name], dict)
        }

    if schema_type == "array":
        return []

    if schema_type == "string":
        enum = schema.get("enum")
        if isinstance(enum, list) and enum:
            return str(enum[0])
        return "mock_result"

    if schema_type == "boolean":
        return False

    if schema_type == "integer":
        return 0

    if schema_type == "number":
        return 0.0

    return None


def _repair_entity_synthesis_test_double_semantics(
    structured: dict[str, Any], prompt: Prompt,
) -> dict[str, Any]:
    """MockのSystem例文をEntity labelとして誤採用させない。

    既存`MockLLMAdapter`は`entity_label`生成時にflatten済みPrompt全体を
    topic判定へ渡す。Entity SynthesisのSystem文には説明例として
    「買い物」が含まれるため、実際のNeedに関係なく
    `買い物リスト`が返ることを020A4B CIで実測した。

    Test Doubleは意味理解能力を主張するものではない。そこで、同じNeedへ
    production pipelineが後段で使うCanonical Capability Planを再利用し、
    役から主題が取れる場合だけそのlabelを使う。何も取れない場合は
    internal identifierへ戻し、`decide_app_name()`がそれを人向け名称として
    採用しないようにする。専用アプリ名テーブルは増やさない。
    """
    fixed = dict(structured)
    need = str(prompt.context.get("user_text", "") or "")
    semantic_label = plan_capabilities(need).entity_label
    if semantic_label:
        fixed["entity_label"] = semantic_label
    else:
        fixed["entity_label"] = str(fixed.get("entity_name") or "mock_result")
    return fixed


class ForgeAIProviderBridge:
    """forge_ai.AIProvider Protocolを満たす、LLMAdapterへの委譲実装。"""

    def __init__(self, llm_adapter: LLMAdapter) -> None:
        self._llm_adapter = llm_adapter

    @property
    def provider_id(self) -> str:
        """Actual provider selected by the adapter, for typed provenance."""
        return str(getattr(self._llm_adapter, "last_provider_used", "") or "")

    @property
    def last_structured_output_mode(self) -> str:
        """直近の呼び出しで実際に受理された構造化出力 mode。"""
        return str(
            getattr(self._llm_adapter, "last_structured_output_mode", "") or ""
        )

    def complete(self, prompt: Prompt) -> ProviderResponse:
        """forge_ai.AIProvider Protocolの実装本体。

        `PromptPipeline`が渡すBoundAdapterはrequest-localであるため、
        entity_synthesisの1呼び出しだけTaskを差し替えても別requestとは
        競合しない。それでも例外時にTaskが残留しないよう`finally`で復元する。
        """
        flat_prompt = _flatten_prompt_to_string(prompt)
        schema = _RESPONSE_SCHEMAS.get(prompt.stage, _UNKNOWN_STAGE_SCHEMA)

        original_task = getattr(self._llm_adapter, "task", None)
        target_task = _task_for_stage(prompt.stage)
        task_was_switched = (
            isinstance(original_task, ForgeTask) and original_task is not target_task
        )
        if task_was_switched:
            self._llm_adapter.task = target_task

        try:
            structured = self._llm_adapter.complete_structured(flat_prompt, schema)
        finally:
            if task_was_switched:
                self._llm_adapter.task = original_task

        provider_id = str(getattr(self._llm_adapter, "last_provider_used", "") or "")
        if provider_id == "mock" and prompt.stage == "entity_synthesis":
            structured = _repair_test_double_value(structured, schema)
            structured = _repair_entity_synthesis_test_double_semantics(
                structured, prompt,
            )

        return ProviderResponse(
            text=f"[{prompt.stage}] 応答を受け取りました。",
            structured=structured,
        )
