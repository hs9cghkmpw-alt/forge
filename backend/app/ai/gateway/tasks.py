"""Forge AIが行う仕事の単位(FORGE-QUALITY-AI-INDEPENDENCE-003 3章)。

`ForgeTask`だけを置く独立モジュールである
(FORGE-AI-FOUNDATION-010 Phase Bで`model_gateway.py`から切り出した)。

## なぜ切り出したか

`ForgeTask`は**Forgeの語彙**であり、Routing実装の付属品ではない。
`AIRouter`・`PromptPipeline`・`routers/ai.py`・Benchmarkがいずれも
これを使うが、どれも「Gateway実装」には依存していない。実装の
入れ替え(`ModelGateway` → `AIRouter`)のたびに全importが動くのは、
置き場所が間違っていたからである。

`ModelGateway`自体は削除した。`AIRouter`
(`app/ai/gateway/ai_router.py`)が同じ責務を、失敗分類・Quota・
Circuit Breaker込みで果たす。**同じことをする層を2つ残さない**
——片方が本番から呼ばれないまま残り、テストだけが通り続ける、
という状態(TD59)を作らないため。
"""

from __future__ import annotations

from enum import Enum

__all__ = ["ForgeTask"]


class ForgeTask(str, Enum):
    """Forge AIが行う仕事の単位(指示書3章)。

    「GeminiとLocalのどちらが優秀か」という大雑把な比較は禁止されており
    (指示書3章)、評価もRoutingもこの単位で行う。

    ここに挙げるのは**現に実装が存在する**Taskだけである。指示書3章の
    候補のうち`solution_hypothesis`・`product_planning`等は、現状
    `PromptPipeline`/`forge_ai`の内部で分離されておらず、単独で呼べる
    入口が無い。存在しないTaskを先に列挙しても、Routing表に永久に
    使われない行が並ぶだけなので入れていない(指示書5章「今すぐ不要な
    Providerを空実装しない」と同じ理由)。
    """

    CONVERSATION_STEP = "conversation_step"
    """1ターン分の会話判断(Problem/Need/Unknown/Impact抽出 +
    ASK/BUILD候補)。`conversation_engine.py`が呼ぶ。"""

    ENTITY_SYNTHESIS = "entity_synthesis"
    """「このアプリが繰り返し記録する1件分のデータ」の設計。
    `forge_ai/core/ir/entity_synthesizer.py`が呼ぶ。"""

    FORGE_LANGUAGE_UPDATE = "forge_language_update"
    """既存Forge Documentの更新(Forming)。`forge_operation.py`が呼ぶ。"""

    COGNITIVE_STAGE = "cognitive_stage"
    """Cognitive Pipelineの各段(meaning/intent/planning/compile/repair)。
    現状これらは`ForgeAIProviderBridge`が1つの入口でまとめて扱っており、
    段ごとの分離はしていない。"""
