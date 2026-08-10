"""Folder Entityのテスト(FORGE V2 Phase 2 Step 1)。

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


class TestFolderEntity(unittest.TestCase):
    def _make(self, **overrides) -> Folder:
        defaults = dict(id="f1", workspace_id="w1", name="営業")
        defaults.update(overrides)
        return Folder(**defaults)

    def test_valid_construction(self) -> None:
        f = self._make()
        self.assertEqual(f.id, "f1")
        self.assertEqual(f.workspace_id, "w1")
        self.assertEqual(f.name, "営業")
        self.assertIsNone(f.parent_folder_id)
        self.assertEqual(f.application_ids, ())

    def test_empty_id_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            self._make(id="")

    def test_empty_workspace_id_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            self._make(workspace_id="")

    def test_empty_name_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            self._make(name="")

    def test_whitespace_only_name_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            self._make(name="   ")

    def test_direct_self_parenting_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            self._make(id="f1", parent_folder_id="f1")

    def test_is_frozen(self) -> None:
        f = self._make()
        with self.assertRaises(Exception):  # noqa: B017
            f.name = "x"  # type: ignore[misc]

    def test_with_name_returns_new_instance(self) -> None:
        f = self._make()
        renamed = f.with_name("Sales")
        self.assertEqual(renamed.name, "Sales")
        self.assertEqual(f.name, "営業", "元のインスタンスは不変")
        self.assertIsNot(f, renamed)

    def test_with_name_rejects_empty(self) -> None:
        f = self._make()
        with self.assertRaises(ValueError):
            f.with_name("")

    def test_with_parent_folder_id_returns_new_instance(self) -> None:
        f = self._make()
        moved = f.with_parent_folder_id("f2")
        self.assertEqual(moved.parent_folder_id, "f2")
        self.assertIsNone(f.parent_folder_id)

    def test_with_parent_folder_id_to_none_clears_parent(self) -> None:
        f = self._make(parent_folder_id="f2")
        cleared = f.with_parent_folder_id(None)
        self.assertIsNone(cleared.parent_folder_id)


if __name__ == "__main__":
    unittest.main()
