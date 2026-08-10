"""WorkspaceFactoryのテスト(FORGE V2 Phase 1)。

fastapi/pydantic/supabaseのいずれにも依存しない、純粋なPythonロジック
のため、このサンドボックスでも実際に実行・検証できる。
"""

from __future__ import annotations

import os
import sys
import unittest
import uuid

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from app.domain.entities.workspace_factory import create_initial_workspace  # noqa: E402


class TestWorkspaceFactory(unittest.TestCase):
    def test_creates_a_valid_workspace_for_the_given_owner(self) -> None:
        workspace = create_initial_workspace("user-abc")
        self.assertEqual(workspace.owner_user_id, "user-abc")
        self.assertEqual(workspace.structure_version, 1)
        self.assertEqual(workspace.display_default_view, "icon")

    def test_assigns_a_valid_uuid_as_id(self) -> None:
        workspace = create_initial_workspace("user-abc")
        # raises ValueError if not a valid UUID string
        uuid.UUID(workspace.id)

    def test_two_calls_produce_different_ids(self) -> None:
        w1 = create_initial_workspace("user-a")
        w2 = create_initial_workspace("user-b")
        self.assertNotEqual(w1.id, w2.id)

    def test_created_at_is_a_non_empty_string(self) -> None:
        workspace = create_initial_workspace("user-abc")
        self.assertTrue(workspace.created_at)
        self.assertIsInstance(workspace.created_at, str)

    def test_empty_owner_user_id_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            create_initial_workspace("")

    def test_result_is_not_yet_persisted(self) -> None:
        """Factory自体はRepositoryを呼ばない、という設計上の確認
        (Type Design Review11章)。この確認は、Factoryの戻り値だけを
        見て「保存された痕跡が無い」ことを直接テストすることはできない
        (Factory自体がRepositoryへの参照を一切持たないことは、
        コードレビュー・型シグネチャ(引数にRepositoryを取らない)で
        確認する事項であり、ここでは`create_initial_workspace`の
        シグネチャがowner_user_idの1引数のみであることを確認する形で
        間接的に裏付ける。"""
        import inspect

        signature = inspect.signature(create_initial_workspace)
        self.assertEqual(list(signature.parameters.keys()), ["owner_user_id"])


if __name__ == "__main__":
    unittest.main()
