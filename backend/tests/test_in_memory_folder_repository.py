"""InMemoryFolderRepositoryのテスト(FORGE V2 Phase 2 Step 1)。

fastapi/pydantic/supabaseのいずれにも依存しない、純粋なPythonロジック
のため、このサンドボックスでも実際に実行・検証できる。
"""

from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from app.domain.entities.folder import Folder  # noqa: E402
from app.repositories.in_memory_folder_repository import InMemoryFolderRepository  # noqa: E402


class TestInMemoryFolderRepository(unittest.TestCase):
    def setUp(self) -> None:
        self.repo = InMemoryFolderRepository()

    def test_get_returns_none_for_unknown_id(self) -> None:
        self.assertIsNone(self.repo.get("nonexistent"))

    def test_list_by_workspace_returns_empty_tuple_when_none_exist(self) -> None:
        self.assertEqual(self.repo.list_by_workspace("w1"), ())

    def test_save_then_get_returns_the_same_folder(self) -> None:
        folder = Folder(id="f1", workspace_id="w1", name="営業")
        self.repo.save(folder)
        self.assertEqual(self.repo.get("f1"), folder)

    def test_list_by_workspace_only_returns_matching_workspace(self) -> None:
        f1 = Folder(id="f1", workspace_id="w1", name="A")
        f2 = Folder(id="f2", workspace_id="w1", name="B")
        f3 = Folder(id="f3", workspace_id="w2", name="C")
        for f in (f1, f2, f3):
            self.repo.save(f)
        result_ids = {f.id for f in self.repo.list_by_workspace("w1")}
        self.assertEqual(result_ids, {"f1", "f2"})

    def test_save_overwrites_existing_folder(self) -> None:
        folder = Folder(id="f1", workspace_id="w1", name="営業")
        self.repo.save(folder)
        renamed = folder.with_name("Sales")
        self.repo.save(renamed)
        self.assertEqual(self.repo.get("f1").name, "Sales")

    def test_delete_removes_the_folder(self) -> None:
        folder = Folder(id="f1", workspace_id="w1", name="営業")
        self.repo.save(folder)
        self.repo.delete("f1")
        self.assertIsNone(self.repo.get("f1"))

    def test_delete_of_unknown_id_does_not_raise(self) -> None:
        self.repo.delete("nonexistent")  # 例外を送出しないことの確認

    def test_satisfies_the_folder_repository_protocol(self) -> None:
        from app.domain.repositories.folder_repository import FolderRepository

        self.assertIsInstance(self.repo, FolderRepository)


if __name__ == "__main__":
    unittest.main()
