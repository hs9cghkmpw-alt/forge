"""Feature Flag(`is_workspace_enabled`)のテスト(FORGE V2 Phase 1)。

fastapi/pydantic/supabaseのいずれにも依存しない、純粋なPythonロジック
のため、このサンドボックスでも実際に実行・検証できる。
"""

from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from app.core.feature_flags import _ENV_VAR_NAME, is_workspace_enabled  # noqa: E402


class TestFeatureFlags(unittest.TestCase):
    def setUp(self) -> None:
        self._original = os.environ.get(_ENV_VAR_NAME)

    def tearDown(self) -> None:
        if self._original is None:
            os.environ.pop(_ENV_VAR_NAME, None)
        else:
            os.environ[_ENV_VAR_NAME] = self._original

    def test_defaults_to_disabled_when_unset(self) -> None:
        os.environ.pop(_ENV_VAR_NAME, None)
        self.assertFalse(is_workspace_enabled())

    def test_enabled_when_set_to_true(self) -> None:
        os.environ[_ENV_VAR_NAME] = "true"
        self.assertTrue(is_workspace_enabled())

    def test_is_case_insensitive(self) -> None:
        os.environ[_ENV_VAR_NAME] = "TRUE"
        self.assertTrue(is_workspace_enabled())
        os.environ[_ENV_VAR_NAME] = "True"
        self.assertTrue(is_workspace_enabled())

    def test_disabled_when_set_to_false(self) -> None:
        os.environ[_ENV_VAR_NAME] = "false"
        self.assertFalse(is_workspace_enabled())

    def test_disabled_for_unrecognized_value(self) -> None:
        os.environ[_ENV_VAR_NAME] = "yes"  # 既定の許可値("true")以外は無効側に倒す(安全側の既定)
        self.assertFalse(is_workspace_enabled())

    def test_tolerates_surrounding_whitespace(self) -> None:
        os.environ[_ENV_VAR_NAME] = "  true  "
        self.assertTrue(is_workspace_enabled())


if __name__ == "__main__":
    unittest.main()
