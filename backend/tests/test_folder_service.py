"""FolderServiceのテスト(FORGE V2 Phase 2 Step 1)。

CEO指示の必須ケース(Folder作成・改名・移動・循環移動拒否・空名前
拒否・他Workspace移動拒否・cascade無し削除拒否・cascade有り削除
成功)を全て含む。fastapi/pydantic/supabaseのいずれにも依存しない、
純粋なPythonロジックのため、このサンドボックスでも実際に実行・
検証できる。
"""

from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from app.core.exceptions import ConflictError, NotFoundError, ValidationError  # noqa: E402
from app.repositories.in_memory_folder_repository import InMemoryFolderRepository  # noqa: E402
from app.services.folder_service import FolderService  # noqa: E402


class TestFolderServiceCreate(unittest.TestCase):
    def setUp(self) -> None:
        self.repo = InMemoryFolderRepository()
        self.service = FolderService(self.repo)

    def test_creates_a_top_level_folder(self) -> None:
        folder = self.service.create("w1", "営業", None)
        self.assertEqual(folder.workspace_id, "w1")
        self.assertEqual(folder.name, "営業")
        self.assertIsNone(folder.parent_folder_id)
        self.assertIsNotNone(self.repo.get(folder.id))

    def test_creates_a_child_folder(self) -> None:
        parent = self.service.create("w1", "営業", None)
        child = self.service.create("w1", "案件管理", parent.id)
        self.assertEqual(child.parent_folder_id, parent.id)

    def test_empty_name_is_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            self.service.create("w1", "", None)

    def test_whitespace_only_name_is_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            self.service.create("w1", "   ", None)

    def test_nonexistent_parent_is_rejected(self) -> None:
        with self.assertRaises(NotFoundError):
            self.service.create("w1", "x", "nonexistent-parent")

    def test_parent_from_another_workspace_is_rejected(self) -> None:
        other_ws_parent = self.service.create("w2", "OtherWS", None)
        with self.assertRaises(ValidationError):
            self.service.create("w1", "x", other_ws_parent.id)


class TestFolderServiceRename(unittest.TestCase):
    def setUp(self) -> None:
        self.repo = InMemoryFolderRepository()
        self.service = FolderService(self.repo)

    def test_renames_a_folder(self) -> None:
        folder = self.service.create("w1", "営業", None)
        renamed = self.service.rename("w1", folder.id, "Sales")
        self.assertEqual(renamed.name, "Sales")
        self.assertEqual(self.repo.get(folder.id).name, "Sales", "永続化されていること")

    def test_empty_new_name_is_rejected(self) -> None:
        folder = self.service.create("w1", "営業", None)
        with self.assertRaises(ValidationError):
            self.service.rename("w1", folder.id, "")

    def test_nonexistent_folder_is_rejected(self) -> None:
        with self.assertRaises(NotFoundError):
            self.service.rename("w1", "nonexistent", "x")

    def test_renaming_another_workspaces_folder_is_rejected(self) -> None:
        folder = self.service.create("w1", "営業", None)
        with self.assertRaises(NotFoundError):
            self.service.rename("w2", folder.id, "x")


class TestFolderServiceMove(unittest.TestCase):
    def setUp(self) -> None:
        self.repo = InMemoryFolderRepository()
        self.service = FolderService(self.repo)

    def test_moves_a_folder_under_a_new_parent(self) -> None:
        a = self.service.create("w1", "A", None)
        b = self.service.create("w1", "B", None)
        moved = self.service.move("w1", a.id, b.id)
        self.assertEqual(moved.parent_folder_id, b.id)

    def test_moves_a_folder_to_top_level(self) -> None:
        a = self.service.create("w1", "A", None)
        b = self.service.create("w1", "B", a.id)
        moved = self.service.move("w1", b.id, None)
        self.assertIsNone(moved.parent_folder_id)

    def test_direct_circular_move_is_rejected(self) -> None:
        """A を A 自身の子にしようとする、最も単純な循環。"""
        a = self.service.create("w1", "A", None)
        with self.assertRaises(ValidationError):
            self.service.move("w1", a.id, a.id)

    def test_indirect_circular_move_is_rejected(self) -> None:
        """A → B → C という階層がある状態で、A を C の子にしようと
        すると、A→B→C→A という循環になるため拒否される
        (CEO指示の必須ケース「循環移動拒否」)。"""
        a = self.service.create("w1", "A", None)
        b = self.service.create("w1", "B", a.id)
        c = self.service.create("w1", "C", b.id)
        with self.assertRaises(ValidationError):
            self.service.move("w1", a.id, c.id)

    def test_moving_under_a_folder_in_another_workspace_is_rejected(self) -> None:
        """CEO指示の必須ケース「他Workspace移動拒否」。"""
        a = self.service.create("w1", "A", None)
        other_ws_folder = self.service.create("w2", "OtherWS", None)
        with self.assertRaises(ValidationError):
            self.service.move("w1", a.id, other_ws_folder.id)

    def test_moving_to_nonexistent_parent_is_rejected(self) -> None:
        a = self.service.create("w1", "A", None)
        with self.assertRaises(NotFoundError):
            self.service.move("w1", a.id, "nonexistent")

    def test_valid_move_is_not_treated_as_circular(self) -> None:
        """非循環な、深い階層への移動が誤って拒否されないことの確認
        (循環検出ロジックの偽陽性が無いことの裏付け)。"""
        a = self.service.create("w1", "A", None)
        b = self.service.create("w1", "B", None)
        c = self.service.create("w1", "C", b.id)
        moved = self.service.move("w1", a.id, c.id)
        self.assertEqual(moved.parent_folder_id, c.id)


class TestFolderServiceDelete(unittest.TestCase):
    def setUp(self) -> None:
        self.repo = InMemoryFolderRepository()
        self.service = FolderService(self.repo)

    def test_deletes_an_empty_folder_without_cascade(self) -> None:
        folder = self.service.create("w1", "Empty", None)
        self.service.delete("w1", folder.id, cascade=False)
        self.assertIsNone(self.repo.get(folder.id))

    def test_delete_without_cascade_is_rejected_when_children_exist(self) -> None:
        """CEO指示の必須ケース「cascade無し削除拒否」。"""
        parent = self.service.create("w1", "Parent", None)
        self.service.create("w1", "Child", parent.id)
        with self.assertRaises(ConflictError):
            self.service.delete("w1", parent.id, cascade=False)
        self.assertIsNotNone(self.repo.get(parent.id), "拒否された場合、Folder自体は削除されないこと")

    def test_delete_with_cascade_succeeds_when_children_exist(self) -> None:
        """CEO指示の必須ケース「cascade有り削除成功」。"""
        parent = self.service.create("w1", "Parent", None)
        child = self.service.create("w1", "Child", parent.id)
        self.service.delete("w1", parent.id, cascade=True)
        self.assertIsNone(self.repo.get(parent.id))
        self.assertIsNone(self.repo.get(child.id), "子Folderも削除されること")

    def test_delete_with_cascade_removes_deeply_nested_children(self) -> None:
        a = self.service.create("w1", "A", None)
        b = self.service.create("w1", "B", a.id)
        c = self.service.create("w1", "C", b.id)
        self.service.delete("w1", a.id, cascade=True)
        self.assertIsNone(self.repo.get(a.id))
        self.assertIsNone(self.repo.get(b.id))
        self.assertIsNone(self.repo.get(c.id))

    def test_deleting_nonexistent_folder_is_rejected(self) -> None:
        with self.assertRaises(NotFoundError):
            self.service.delete("w1", "nonexistent", cascade=False)

    def test_deleting_another_workspaces_folder_is_rejected(self) -> None:
        folder = self.service.create("w1", "A", None)
        with self.assertRaises(NotFoundError):
            self.service.delete("w2", folder.id, cascade=False)


if __name__ == "__main__":
    unittest.main()
