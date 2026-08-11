"""Conversation Session管理(FORGE-PRODUCT-VISION-002、2026-08-11)。

`confirmation_store.py`と全く同じ設計方針(プロセス内メモリのみ・TTL・
最大ターン数)を、複数ターンの会話セッションへ踏襲する。DBは追加しない
(共通指示書の既存方針を継続)。

**永続化についての既知の制限(confirmation_store.pyと同じ)**: プロセス
内メモリのみで完結する。サーバー再起動やマルチプロセス/マルチワーカー
構成では保持されない。将来複数ワーカーで運用する場合、Redis等の外部
ストアへの置き換えが必要になる(TECH_DEBT.md TD41参照)。
"""

from __future__ import annotations

import time
import uuid
from threading import Lock

from app.ai.runtime.conversation_types import ConversationSession, ConversationTurn

# design doc B.3「ターン数が一定以上に達したら強制的にBUILDへ倒す」の
# 上限。`MAX_CONFIRMATION_ROUNDS`(confirmation_store.py)と同じ値を
# 踏襲した(無限に聞き続けない、という同じ思想)。
MAX_CONVERSATION_TURNS = 3

_TTL_SECONDS = 60 * 30  # 30分。confirmation_store.pyと同じ。


class ConversationNotFoundError(Exception):
    """`session_id`に対応するConversationSessionが存在しない
    (未発行・期限切れのいずれか)。"""


class ConversationStore:
    """プロセス内メモリのみで完結する、会話セッションの追跡ストア。"""

    def __init__(self) -> None:
        self._lock = Lock()
        self._sessions: dict[str, ConversationSession] = {}
        self._expiry: dict[str, float] = {}

    def create(self) -> ConversationSession:
        session = ConversationSession(session_id=str(uuid.uuid4()), created_at=time.time())
        with self._lock:
            self._sessions[session.session_id] = session
            self._expiry[session.session_id] = session.created_at
        return session

    def get(self, session_id: str) -> ConversationSession:
        with self._lock:
            session = self._sessions.get(session_id)
            created_at = self._expiry.get(session_id)
        if session is None or created_at is None:
            raise ConversationNotFoundError(session_id)
        if (time.time() - created_at) > _TTL_SECONDS:
            self.discard(session_id)
            raise ConversationNotFoundError(session_id)
        return session

    def save(self, session: ConversationSession) -> None:
        with self._lock:
            if session.session_id not in self._sessions:
                raise ConversationNotFoundError(session.session_id)
            self._sessions[session.session_id] = session

    def discard(self, session_id: str) -> None:
        with self._lock:
            self._sessions.pop(session_id, None)
            self._expiry.pop(session_id, None)

    def add_turn(self, session_id: str, turn: ConversationTurn) -> ConversationSession:
        session = self.get(session_id)
        updated = session.with_turn(turn)
        self.save(updated)
        return updated

    def size(self) -> int:
        with self._lock:
            return len(self._sessions)


# アプリ全体で1つのStoreを共有する(confirmation_store.pyと同じ、
# モジュールレベルSingleton)。
default_conversation_store = ConversationStore()
