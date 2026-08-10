"""InMemoryWorkspaceRepositoryのテスト(FORGE V2 Phase 1)。

fastapi/pydantic/supabaseのいずれにも依存しない、純粋なPythonロジック
のため、このサンドボックスでも実際に実行・検証できる。
"""

from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from app.domain.entities.workspace_factory import create_initial_workspace  # noqa: E402
from app.repositories.in_memory_workspace_repository import InMemoryWorkspaceRepository  # noqa: E402


class TestInMemoryWorkspaceRepository(unittest.TestCase):
    def setUp(self) -> None:
        self.repo = InMemoryWorkspaceRepository()

    def test_get_returns_none_for_unknown_id(self) -> None:
        self.assertIsNone(self.repo.get("nonexistent"))

    def test_get_by_owner_returns_none_for_unknown_owner(self) -> None:
        self.assertIsNone(self.repo.get_by_owner("nonexistent"))

    def test_save_then_get_returns_the_same_workspace(self) -> None:
        workspace = create_initial_workspace("user-1")
        self.repo.save(workspace)
        self.assertEqual(self.repo.get(workspace.id), workspace)

    def test_save_then_get_by_owner_returns_the_same_workspace(self) -> None:
        workspace = create_initial_workspace("user-1")
        self.repo.save(workspace)
        self.assertEqual(self.repo.get_by_owner("user-1"), workspace)

    def test_saving_an_updated_workspace_overwrites_the_previous_state(self) -> None:
        workspace = create_initial_workspace("user-1")
        self.repo.save(workspace)
        updated = workspace.with_display_default_view("list")
        self.repo.save(updated)
        self.assertEqual(self.repo.get(workspace.id).display_default_view, "list")

    def test_different_owners_are_stored_independently(self) -> None:
        w1 = create_initial_workspace("user-1")
        w2 = create_initial_workspace("user-2")
        self.repo.save(w1)
        self.repo.save(w2)
        self.assertEqual(self.repo.get_by_owner("user-1").id, w1.id)
        self.assertEqual(self.repo.get_by_owner("user-2").id, w2.id)

    def test_satisfies_the_workspace_repository_protocol(self) -> None:
        from app.domain.repositories.workspace_repository import WorkspaceRepository

        self.assertIsInstance(self.repo, WorkspaceRepository)


if __name__ == "__main__":
    unittest.main()
