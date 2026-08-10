"""AI Runtime — Context Builder(FORGE-MILESTONE-003 PHASE6/7)。

**責務定義のみ。実装は含まない。**

`AIContextBuilder`は、既存の`Memory`・`Conversation`(foundation/interfaces.py)
から、1回のプロンプト生成に必要な「文脈」を組み立てる契約である。
foundation/には個々の情報源(Memory/Conversation)のProtocolはあったが、
それらを「1回のプロンプトのために統合する」という責務を持つコンポーネントが
無かった(これはPHASE7で新たに要求された、正当な新規追加)。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from app.ai.foundation.interfaces import Conversation, Memory


@dataclass(frozen=True)
class PromptContext:
    """1回のプロンプト生成に使う、統合済みの文脈データ。"""

    conversation_history: tuple[str, ...] = ()
    working_context: dict[str, object] = field(default_factory=dict)
    project_history_summary: tuple[str, ...] = ()
    user_preferences: dict[str, object] | None = None  # Noneなら未opt-in(方針10章)


class AIContextBuilder(Protocol):
    """Memory/Conversationから、1回のプロンプトに必要な`PromptContext`を組み立てる契約
    (PHASE7の要求名)。"""

    def build_context(self, session_id: str, project_id: str, user_id: str) -> PromptContext:
        """3層のMemory(Working/Project/User)とConversationから、
        統合済みのPromptContextを組み立てる。user_idのopt-in状態に応じて
        `user_preferences`がNoneになりうる(方針10章のプライバシー原則)。
        """
        ...


class StubAIContextBuilder:
    """`AIContextBuilder`の未実装スタブ。

    `memory`/`conversation`は将来の実装がMemory/Conversation Protocolの
    具体実装を注入できるよう、コンストラクタで受け取る形にしている
    (Dependency Injection。ただし今回はどちらも未実装のため、実際に
    渡されるのは将来の話であり、このスタブ自体はNotImplementedErrorを返す)。
    """

    def __init__(self, memory: Memory | None = None, conversation: Conversation | None = None) -> None:
        """DIで将来のMemory/Conversation実装を受け取れるようにする(今回は未使用)。"""
        self._memory = memory
        self._conversation = conversation

    def build_context(self, session_id: str, project_id: str, user_id: str) -> PromptContext:
        """未実装。"""
        raise NotImplementedError(
            "StubAIContextBuilder.build_context() は未実装です"
            "(FORGE-MILESTONE-003 PHASE6/7は責務定義のみ)。"
            "実装にはMemory/ConversationのDBバックエンド実装が先に必要です。"
        )
