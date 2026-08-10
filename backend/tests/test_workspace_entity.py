"""Workspace Entityのテスト(FORGE V2 Phase 1)。

fastapi/pydantic/supabaseのいずれにも依存しない、純粋なPythonロジック
のため、このサンドボックスでも実際に実行・検証できる。
"""

from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from app.domain.entities.workspace import VALID_VIEW_TYPES, Workspace, is_valid_view_type  # noqa: E402


class TestWorkspaceEntity(unittest.TestCase):
    def _make(self, **overrides) -> Workspace:
        defaults = dict(id="w1", owner_user_id="u1", created_at="2026-07-22T00:00:00+00:00")
        defaults.update(overrides)
        return Workspace(**defaults)

    def test_valid_construction(self) -> None:
        w = self._make()
        self.assertEqual(w.id, "w1")
        self.assertEqual(w.owner_user_id, "u1")
        self.assertEqual(w.structure_version, 1)
        self.assertEqual(w.display_default_view, "icon")

    def test_empty_id_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            self._make(id="")

    def test_empty_owner_user_id_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            self._make(owner_user_id="")

    def test_structure_version_below_1_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            self._make(structure_version=0)

    def test_invalid_display_default_view_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            self._make(display_default_view="not_a_real_view")

    def test_all_valid_view_types_are_accepted(self) -> None:
        for view in VALID_VIEW_TYPES:
            w = self._make(display_default_view=view)
            self.assertEqual(w.display_default_view, view)

    def test_is_frozen(self) -> None:
        w = self._make()
        with self.assertRaises(Exception):  # noqa: B017 — frozen dataclassの属性代入を確認するテストのため
            w.title = "x"  # type: ignore[attr-defined]

    def test_with_display_default_view_returns_new_instance(self) -> None:
        w = self._make()
        updated = w.with_display_default_view("list")
        self.assertEqual(updated.display_default_view, "list")
        self.assertEqual(w.display_default_view, "icon", "元のインスタンスは不変のまま")
        self.assertIsNot(w, updated)

    def test_with_display_default_view_rejects_invalid_value(self) -> None:
        w = self._make()
        with self.assertRaises(ValueError):
            w.with_display_default_view("bogus")

    def test_with_structure_version_incremented(self) -> None:
        w = self._make()
        updated = w.with_structure_version_incremented()
        self.assertEqual(updated.structure_version, 2)
        self.assertEqual(w.structure_version, 1)

    def test_is_valid_view_type_helper(self) -> None:
        self.assertTrue(is_valid_view_type("icon"))
        self.assertFalse(is_valid_view_type("not_a_view"))


if __name__ == "__main__":
    unittest.main()
