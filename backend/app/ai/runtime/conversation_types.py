"""Conversation Engine — 型定義(FORGE-PRODUCT-VISION-002、2026-08-11)。

CEO指示書「『アプリを作るAI』から『困りごとを話すと道具が生まれる
AI』への製品思想更新」への対応。設計の背景・判断根拠は
`docs/spec/FORGE_PRODUCT_VISION_002_CONVERSATIONAL_ARCHITECTURE.md`
(Phase B)・`docs/adr/ADR-014-conversation-engine-wraps-not-replaces-
pipeline.md`を参照。

このファイルはforge_ai/を一切importしない(ADR-014: Conversation
Engineは既存Cognitive Pipelineの「外」に立つ、薄い意思決定層)。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Literal


class ConversationAction(str, Enum):
    """指示書22章のASK/BUILD/UPDATE/CONFIRM契約。

    Phase E(このセッション)では`ASK`・`BUILD`のみ実際に発火しうる。
    `UPDATE`・`CONFIRM`は型として定義するが、発火する経路は未実装
    (design docのB.2・B.4参照。「発火条件が無いのに実装だけ先行させ
    ない」という、TD37の教訓を踏まえた判断)。
    """

    ASK = "ask"
    BUILD = "build"
    UPDATE = "update"
    CONFIRM = "confirm"


@dataclass(frozen=True)
class ConversationTurn:
    role: Literal["user", "forge"]
    text: str


@dataclass(frozen=True)
class NeedModel:
    """指示書9章の概念例を、Gemini structured outputで安定して返せる形
    (非再帰的なフラット構造)へ具体化したもの(design doc B.2)。

    `known`は指示書の概念例(`dict[str, bool]`)ではなく`list[str]`に
    した。Gemini `responseSchema`はOpenAPI Schemaのサブセットであり、
    任意のkeyを持つdict(`additionalProperties`)よりも、固定shapeの
    array/objectの方が安定して返る(このプロジェクトでは`responseSchema`
    を使った経験がまだ浅く、複雑な形を要求して壊れるリスクより、
    単純な形で確実に動くことを優先した)。
    """

    problem: str
    known: tuple[str, ...] = ()
    unknown_important: tuple[str, ...] = ()
    safe_assumptions: tuple[str, ...] = ()
    confidence: float = 0.0

    def to_dict(self) -> dict:
        return {
            "problem": self.problem,
            "known": list(self.known),
            "unknown_important": list(self.unknown_important),
            "safe_assumptions": list(self.safe_assumptions),
            "confidence": self.confidence,
        }


@dataclass(frozen=True)
class ConversationStepResult:
    """`ConversationEngine.step()`の戻り値。"""

    action: ConversationAction
    need_model: NeedModel
    question: str | None = None
    """action == ASKの場合のみ、意味のある値を持つ(1問だけ)。"""

    build_brief: str | None = None
    """action == BUILDの場合のみ、意味のある値を持つ。既存の
    `PromptPipeline.run()`へそのまま渡せる、会話全体を要約した1つの
    自然文(ADR-014、design doc B.1)。"""


@dataclass(frozen=True)
class ConversationSession:
    """会話1件分の状態。`ConversationStore`(`confirmation_store.py`と
    同じ設計、プロセス内メモリ)が保持する。"""

    session_id: str
    turns: tuple[ConversationTurn, ...] = field(default_factory=tuple)
    created_at: float = 0.0

    def with_turn(self, turn: ConversationTurn) -> ConversationSession:
        return ConversationSession(
            session_id=self.session_id, turns=self.turns + (turn,), created_at=self.created_at,
        )
