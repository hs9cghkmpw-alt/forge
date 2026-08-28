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

from forge_ai.prompt.prompt_builder import Prompt
from forge_ai.provider.provider_interface import ProviderResponse

from app.ai.foundation.interfaces import LLMAdapter
from app.ai.gateway.tasks import ForgeTask

# stageごとに期待する構造化出力の最小スキーマ。MockProvider
# (forge_ai/provider/mock_provider.py)が実際に返す`structured`の形に
# 合わせている。将来実LLMを接続する際、このスキーマを渡すことで
# Structured Outputを要求する想定(LLMAdapter.complete_structuredの
# 契約)。
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
    # FORGE-PRODUCT-VISION-002(2026-08-12)新規。「このアプリが繰り返し
    # 記録する1件分のデータ」の構造をAIに設計させる段階
    # (`forge_ai/core/ir/entity_synthesizer.py`)。
    #
    # **このスキーマの登録は必須である**(省略してはならない): 未登録の
    # stageは下の`_UNKNOWN_STAGE_SCHEMA`(`{"type": "object"}`、
    # propertiesを持たない)へ落ちるが、TD40で実機確認したとおり、
    # Geminiは`properties`の無い`"type": "object"`をresponseSchemaとして
    # 渡されると**黙って空オブジェクト`{}`を返す**。その場合、合成は
    # 常に失敗し、全Domainが従来のChecklistへフォールバックし続ける
    # ——しかもエラーにはならないため、気付けない。
    "entity_synthesis": {
        "type": "object",
        "properties": {
            "entity_name": {"type": "string"},
            "entity_label": {"type": "string"},
            "visual_style": {"type": "string", "enum": ["calm", "warm", "vibrant", "neutral"]},
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
                        # FORGE-R1-CLOSURE-015。数値が**どういう量か**。
                        # ここはenumで閉じてよい——選択肢が6つで固定で
                        # あり、Design Roleのように増減しないため。
                        # forge_ai側でも必ず検証し直す(`_sanitize_measure`)。
                        "measure": {
                            "type": "string",
                            "enum": [
                                "additive", "averageable", "level",
                                "extremum", "identifier", "unknown",
                            ],
                        },
                    },
                    "required": ["name", "label", "type"],
                },
            },
        },
        "required": ["entity_name", "entity_label", "visual_style", "fields"],
    },
    # FORGE-R1(2026-08-17)。Design Languageの意味的役割をAIに選ばせる段。
    #
    # **enumを持たせない**のは、選択肢がProviderへ渡るcontext側にあり、
    # Forge側で必ず検証し直すためである(`design_intent.py`)。schemaで
    # enumを固定すると、語彙を1つ増やすたびに2箇所を直すことになり、
    # そのうちずれる——ずれたときに黙って通る方が危ない。
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
            # FORGE-AI-QUALITY-001(2026-08-11): 依頼内容に即した初期データ
            # 例。任意項目(旧Mock応答・旧テストとの後方互換のためrequired
            # には含めない、`compiler.py`側も未指定を正しく許容する)。
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
    """`Prompt`(system/instruction/context)を1本の文字列へ整形する。

    文字列連結を行うのはforge_ai/の外側、このBridge内部だけである
    (forge_ai/自体は文字列連結を禁止している。ADAPTER_CONTRACT_V1.md
    4.2節のコメント参照)。
    """
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
    """Test Doubleの値をJSON Schemaの型の形へ決定的に合わせる。

    020A4で実測した`array<object>`→文字列配列の崩れだけでなく、
    nested object/arrayの同種事故を再発させないため再帰的に扱う。

    **mock以外には呼ばない。** これは実LLMの失敗を隠すRepairではない。
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
            # Entity Synthesisのfieldsで実際に踏んだ形。
            # 文字列をobjectへ意味変換せず、Schemaのrequiredから1件作る。
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


class ForgeAIProviderBridge:
    """forge_ai.AIProvider Protocolを満たす、LLMAdapterへの委譲実装。"""

    def __init__(self, llm_adapter: LLMAdapter) -> None:
        self._llm_adapter = llm_adapter

    @property
    def provider_id(self) -> str:
        """Actual provider selected by the adapter, for typed provenance."""
        return str(getattr(self._llm_adapter, "last_provider_used", "") or "")

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

        # Test Doubleだけは、既存Mockがnested schemaを平坦化する既知の制限を
        # Bridge境界で補う。実Provider(Local/Cloud)の出力は絶対に補正しない。
        # Real Local Level 0を「Forgeが作った値」で偽装しないための境界である。
        provider_id = str(getattr(self._llm_adapter, "last_provider_used", "") or "")
        if provider_id == "mock":
            structured = _repair_test_double_value(structured, schema)

        return ProviderResponse(
            text=f"[{prompt.stage}] 応答を受け取りました。",
            structured=structured,
        )
