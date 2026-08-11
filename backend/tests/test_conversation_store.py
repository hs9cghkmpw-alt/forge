"""ConversationStoreのテスト(FORGE-PRODUCT-VISION-002、2026-08-11)。

`confirmation_store.py`と同じ設計方針を踏襲するため、テストの構造も
`test_confirmation_store.py`を踏襲する。fastapi/pydanticに依存しない、
純粋なPythonロジックのため、このサンドボックスでも実際に実行・検証
できる。
"""

from __future__ import annotations

import os
import sys
import time
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from app.ai.runtime.conversation_store import (  # noqa: E402
    ConversationNotFoundError,
    ConversationStore,
)
from app.ai.runtime.conversation_types import ConversationTurn  # noqa: E402


class TestConversationStore(unittest.TestCase):
    def setUp(self) -> None:
        self.store = ConversationStore()

    def test_create_returns_a_session_with_an_id_and_no_turns(self) -> None:
        session = self.store.create()
        self.assertTrue(session.session_id)
        self.assertEqual(session.turns, ())

    def test_get_returns_the_same_session(self) -> None:
        created = self.store.create()
        fetched = self.store.get(created.session_id)
        self.assertEqual(fetched.session_id, created.session_id)

    def test_get_unknown_session_id_raises(self) -> None:
        with self.assertRaises(ConversationNotFoundError):
            self.store.get("does-not-exist")

    def test_add_turn_appends_and_persists(self) -> None:
        session = self.store.create()
        self.store.add_turn(session.session_id, ConversationTurn(role="user", text="買い物で忘れる"))
        fetched = self.store.get(session.session_id)
        self.assertEqual(len(fetched.turns), 1)
        self.assertEqual(fetched.turns[0].text, "買い物で忘れる")

    def test_add_turn_accumulates_multiple_turns_in_order(self) -> None:
        session = self.store.create()
        self.store.add_turn(session.session_id, ConversationTurn(role="user", text="買い物で忘れる"))
        self.store.add_turn(session.session_id, ConversationTurn(role="forge", text="お店で消していく感じ?"))
        self.store.add_turn(session.session_id, ConversationTurn(role="user", text="そうそう"))
        fetched = self.store.get(session.session_id)
        self.assertEqual([t.role for t in fetched.turns], ["user", "forge", "user"])

    def test_add_turn_on_unknown_session_raises(self) -> None:
        with self.assertRaises(ConversationNotFoundError):
            self.store.add_turn("does-not-exist", ConversationTurn(role="user", text="x"))

    def test_discard_removes_the_session(self) -> None:
        session = self.store.create()
        self.store.discard(session.session_id)
        with self.assertRaises(ConversationNotFoundError):
            self.store.get(session.session_id)

    def test_discard_unknown_session_is_a_noop(self) -> None:
        self.store.discard("does-not-exist")  # クラッシュしないことのみ確認

    def test_expired_session_is_treated_as_not_found(self) -> None:
        session = self.store.create()
        with self.store._lock:  # noqa: SLF001 — TTL経過をテストのために直接シミュレートする
            self.store._expiry[session.session_id] = time.time() - 60 * 31
        with self.assertRaises(ConversationNotFoundError):
            self.store.get(session.session_id)

    def test_size_reflects_active_sessions(self) -> None:
        self.assertEqual(self.store.size(), 0)
        self.store.create()
        self.store.create()
        self.assertEqual(self.store.size(), 2)


if __name__ == "__main__":
    unittest.main()
