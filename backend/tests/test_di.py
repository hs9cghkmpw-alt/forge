"""`app/core/di.py`のテスト(FORGE V2 Phase 1)。

fastapi/pydantic/supabaseのいずれにも依存しない、純粋なPythonロジック
のため、このサンドボックスでも実際に実行・検証できる(`supabase`
backendを選択した場合の`NotImplementedError`送出まで含めて検証する、
実際のSupabase接続そのものはCEO環境が必要)。
"""

from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from app.core import di  # noqa: E402
from app.repositories.in_memory_workspace_repository import InMemoryWorkspaceRepository  # noqa: E402


class TestWorkspaceRepositoryDI(unittest.TestCase):
    def setUp(self) -> None:
        self._original = os.environ.get(di._ENV_VAR_NAME)
        di.reset_workspace_repository_singleton_for_testing()

    def tearDown(self) -> None:
        if self._original is None:
            os.environ.pop(di._ENV_VAR_NAME, None)
        else:
            os.environ[di._ENV_VAR_NAME] = self._original
        di.reset_workspace_repository_singleton_for_testing()

    def test_defaults_to_in_memory_backend(self) -> None:
        os.environ.pop(di._ENV_VAR_NAME, None)
        repo = di.get_workspace_repository()
        self.assertIsInstance(repo, InMemoryWorkspaceRepository)

    def test_explicit_memory_backend(self) -> None:
        os.environ[di._ENV_VAR_NAME] = "memory"
        repo = di.get_workspace_repository()
        self.assertIsInstance(repo, InMemoryWorkspaceRepository)

    def test_returns_the_same_instance_on_repeated_calls(self) -> None:
        """シングルトンであることの確認(1 User=1 Workspaceの保証には、
        プロセス内で同じRepositoryインスタンスが使われ続けることが
        前提になる)。"""
        repo1 = di.get_workspace_repository()
        repo2 = di.get_workspace_repository()
        self.assertIs(repo1, repo2)

    def test_reset_creates_a_new_instance(self) -> None:
        repo1 = di.get_workspace_repository()
        di.reset_workspace_repository_singleton_for_testing()
        repo2 = di.get_workspace_repository()
        self.assertIsNot(repo1, repo2)

    def test_supabase_backend_raises_not_implemented_in_this_environment(self) -> None:
        os.environ[di._ENV_VAR_NAME] = "supabase"
        with self.assertRaises(NotImplementedError):
            di.get_workspace_repository()

    def test_unknown_backend_raises_value_error(self) -> None:
        os.environ[di._ENV_VAR_NAME] = "not_a_real_backend"
        with self.assertRaises(ValueError):
            di.get_workspace_repository()


if __name__ == "__main__":
    unittest.main()
