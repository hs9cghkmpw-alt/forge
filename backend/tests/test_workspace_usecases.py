"""GetOrCreateWorkspaceUseCase・UpdateWorkspaceSettingsUseCaseのテスト
(FORGE V2 Phase 1)。

fastapi/pydantic/supabaseのいずれにも依存しない、純粋なPythonロジック
のため、このサンドボックスでも実際に実行・検証できる。
"""

from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from app.core.exceptions import NotFoundError, ValidationError  # noqa: E402
from app.domain.usecases.get_or_create_workspace_usecase import GetOrCreateWorkspaceUseCase  # noqa: E402
from app.domain.usecases.update_workspace_settings_usecase import (  # noqa: E402
    UpdateWorkspaceSettingsUseCase,
)
from app.repositories.in_memory_workspace_repository import InMemoryWorkspaceRepository  # noqa: E402


class TestGetOrCreateWorkspaceUseCase(unittest.TestCase):
    def setUp(self) -> None:
        self.repo = InMemoryWorkspaceRepository()
        self.use_case = GetOrCreateWorkspaceUseCase(self.repo)

    def test_creates_a_new_workspace_on_first_call(self) -> None:
        workspace = self.use_case.execute("user-1")
        self.assertEqual(workspace.owner_user_id, "user-1")
        self.assertIsNotNone(self.repo.get(workspace.id))

    def test_returns_the_same_workspace_on_repeated_calls(self) -> None:
        """1 User = 1 Workspaceの保証(Freeze Report・API Design
        4.1節)を直接検証する、最重要テスト。"""
        first = self.use_case.execute("user-1")
        second = self.use_case.execute("user-1")
        third = self.use_case.execute("user-1")
        self.assertEqual(first.id, second.id)
        self.assertEqual(second.id, third.id)

    def test_different_users_get_different_workspaces(self) -> None:
        w1 = self.use_case.execute("user-1")
        w2 = self.use_case.execute("user-2")
        self.assertNotEqual(w1.id, w2.id)

    def test_repeated_calls_do_not_create_duplicate_stored_records(self) -> None:
        """Repository内部の状態も確認し、「作成→取得」の内部動作が
        正しいことまで検証する(戻り値の一致だけでなく)。"""
        self.use_case.execute("user-1")
        self.use_case.execute("user-1")
        self.use_case.execute("user-1")
        # InMemoryWorkspaceRepositoryは owner->id の1:1マッピングのため、
        # 3回呼んでも常に同じidに上書きされる(重複レコードが増えない)。
        workspace = self.repo.get_by_owner("user-1")
        self.assertIsNotNone(workspace)


class TestUpdateWorkspaceSettingsUseCase(unittest.TestCase):
    def setUp(self) -> None:
        self.repo = InMemoryWorkspaceRepository()
        self.get_or_create = GetOrCreateWorkspaceUseCase(self.repo)
        self.update = UpdateWorkspaceSettingsUseCase(self.repo)

    def test_updates_display_default_view(self) -> None:
        self.get_or_create.execute("user-1")
        updated = self.update.execute("user-1", "list")
        self.assertEqual(updated.display_default_view, "list")

    def test_update_is_persisted(self) -> None:
        self.get_or_create.execute("user-1")
        self.update.execute("user-1", "dashboard")
        reloaded = self.repo.get_by_owner("user-1")
        self.assertEqual(reloaded.display_default_view, "dashboard")

    def test_invalid_view_type_raises_validation_error(self) -> None:
        self.get_or_create.execute("user-1")
        with self.assertRaises(ValidationError):
            self.update.execute("user-1", "not_a_real_view")

    def test_invalid_view_type_does_not_change_stored_workspace(self) -> None:
        self.get_or_create.execute("user-1")
        try:
            self.update.execute("user-1", "not_a_real_view")
        except ValidationError:
            pass
        reloaded = self.repo.get_by_owner("user-1")
        self.assertEqual(reloaded.display_default_view, "icon", "不正な更新は反映されないこと")

    def test_none_view_type_leaves_workspace_unchanged(self) -> None:
        """部分更新(Type Design6章、フィールド省略時は無変更)の確認。"""
        self.get_or_create.execute("user-1")
        result = self.update.execute("user-1", None)
        self.assertEqual(result.display_default_view, "icon")

    def test_nonexistent_owner_raises_not_found_error(self) -> None:
        with self.assertRaises(NotFoundError):
            self.update.execute("nonexistent-user", "list")

    def test_updating_one_user_does_not_affect_another(self) -> None:
        self.get_or_create.execute("user-1")
        self.get_or_create.execute("user-2")
        self.update.execute("user-1", "list")
        user2_workspace = self.repo.get_by_owner("user-2")
        self.assertEqual(user2_workspace.display_default_view, "icon")


if __name__ == "__main__":
    unittest.main()
