"""ForgeAIProviderBridge。

`docs/spec/ADAPTER_CONTRACT_V1.md` 4.2節の実装。forge_ai.AIProvider
Protocol(`complete(prompt: Prompt) -> ProviderResponse`)を満たしながら、
内部ではM005の`LLMAdapter`(`complete_structured(prompt: str,
response_schema: dict) -> dict`)へ処理を委譲する。

forge_ai/自体はこのBridgeの存在を知らない(forge_ai/はMockProviderか、
このBridgeか、将来の別実装かを区別しない。forge_ai.AIProvider Protocolを
満たすオブジェクトなら何でも渡せる、という既存の設計をそのまま活かす)。

今回実装するのはBridgeの変換ロジックのみ。実際に接続されるLLMAdapterは
Mockのみであり(禁止事項「実LLM接続禁止」)、OpenAI/Claude/Gemini/OSSは
`backend/app/ai/foundation/providers.py`の既存Stub(NotImplementedError)
のままである。
"""

from __future__ import annotations

from typing import Any

from forge_ai.prompt.prompt_builder import Prompt
from forge_ai.provider.provider_interface import ProviderResponse

from app.ai.foundation.interfaces import LLMAdapter

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


class ForgeAIProviderBridge:
    """forge_ai.AIProvider Protocolを満たす、LLMAdapterへの委譲実装。"""

    def __init__(self, llm_adapter: LLMAdapter) -> None:
        self._llm_adapter = llm_adapter

    @property
    def provider_id(self) -> str:
        """Actual provider selected by the adapter, for typed provenance."""
        return str(getattr(self._llm_adapter, "last_provider_used", "") or "")

    def complete(self, prompt: Prompt) -> ProviderResponse:
        """forge_ai.AIProvider Protocolの実装本体。"""
        flat_prompt = _flatten_prompt_to_string(prompt)
        schema = _RESPONSE_SCHEMAS.get(prompt.stage, _UNKNOWN_STAGE_SCHEMA)
        structured = self._llm_adapter.complete_structured(flat_prompt, schema)
        return ProviderResponse(
            text=f"[{prompt.stage}] 応答を受け取りました。",
            structured=structured,
        )
