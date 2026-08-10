"""`POST/PATCH/DELETE /v1/folders`・`POST /v1/folders/{id}/move`の
API Contract Test(FORGE V2 Phase 2 Step 1)。

**重要な注記(未検証)**: `backend/tests/test_workspace_router.py`と
全く同じ制限(fastapi/pydantic/supabase不在、`_verify_and_decode()`
未実装)。認証エラー系(401)のみ実行・検証済み、認証成功系はCEO環境
での`security.py`実装後に有効化する。

実行方法(CEO環境):
    cd backend
    pip install -r requirements.txt --break-system-packages
    export FORGE_FEATURE_WORKSPACE=true FORGE_FEATURE_FOLDER=true
    python -m unittest tests.test_folder_router -v
"""

from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

os.environ.setdefault("FORGE_FEATURE_WORKSPACE", "true")
os.environ.setdefault("FORGE_FEATURE_FOLDER", "true")

try:
    from fastapi.testclient import TestClient

    from app.main import app

    _FASTAPI_AVAILABLE = True
except ImportError:
    _FASTAPI_AVAILABLE = False


@unittest.skipUnless(_FASTAPI_AVAILABLE, "fastapi/pydantic/supabaseがインストールされていない環境ではスキップする")
class TestFolderRouterContract(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(app)

    def test_create_without_authorization_returns_401(self) -> None:
        response = self.client.post("/v1/folders", json={"name": "営業"})
        self.assertEqual(response.status_code, 401)

    def test_rename_without_authorization_returns_401(self) -> None:
        response = self.client.patch("/v1/folders/some-id", json={"name": "x"})
        self.assertEqual(response.status_code, 401)

    def test_delete_without_authorization_returns_401(self) -> None:
        response = self.client.delete("/v1/folders/some-id")
        self.assertEqual(response.status_code, 401)

    def test_move_without_authorization_returns_401(self) -> None:
        response = self.client.post("/v1/folders/some-id/move", json={"new_parent_folder_id": None})
        self.assertEqual(response.status_code, 401)

    # --- 以下、_verify_and_decode()実装後にCEO環境で意味を持つテスト ---

    @unittest.skip("app/core/security.py の _verify_and_decode() 実装待ち(CEO環境)")
    def test_create_folder_succeeds(self) -> None:
        response = self.client.post(
            "/v1/folders", json={"name": "営業"}, headers={"Authorization": "Bearer <valid-test-jwt>"}
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["name"], "営業")

    @unittest.skip("app/core/security.py の _verify_and_decode() 実装待ち(CEO環境)")
    def test_create_with_empty_name_returns_400(self) -> None:
        response = self.client.post(
            "/v1/folders", json={"name": ""}, headers={"Authorization": "Bearer <valid-test-jwt>"}
        )
        self.assertEqual(response.status_code, 400)

    @unittest.skip("app/core/security.py の _verify_and_decode() 実装待ち(CEO環境)")
    def test_delete_without_cascade_returns_409_when_children_exist(self) -> None:
        headers = {"Authorization": "Bearer <valid-test-jwt>"}
        parent = self.client.post("/v1/folders", json={"name": "Parent"}, headers=headers).json()
        self.client.post(
            "/v1/folders", json={"name": "Child", "parent_folder_id": parent["id"]}, headers=headers
        )
        response = self.client.delete(f"/v1/folders/{parent['id']}", headers=headers)
        self.assertEqual(response.status_code, 409)

    @unittest.skip("app/core/security.py の _verify_and_decode() 実装待ち(CEO環境)")
    def test_delete_with_cascade_returns_200(self) -> None:
        headers = {"Authorization": "Bearer <valid-test-jwt>"}
        parent = self.client.post("/v1/folders", json={"name": "Parent"}, headers=headers).json()
        response = self.client.delete(f"/v1/folders/{parent['id']}?cascade=true", headers=headers)
        self.assertEqual(response.status_code, 200)


@unittest.skipIf(_FASTAPI_AVAILABLE, "fastapi無し環境でのFeature Flag OFF時の挙動確認")
class TestFolderFeatureFlagOffDoesNotAffectExistingBehavior(unittest.TestCase):
    """絶対条件「Feature Flag OFF時に既存挙動へ影響しない」の確認
    (ソースコード上での静的確認、`test_workspace_router.py`と同じ
    アプローチ)。"""

    def test_folder_router_import_is_lazy_and_conditional(self) -> None:
        with open(os.path.join(os.path.dirname(__file__), "..", "app", "main.py"), encoding="utf-8") as f:
            main_source = f.read()
        self.assertIn("if is_folder_enabled():", main_source)
        lines = main_source.splitlines()
        flag_check_index = next(i for i, line in enumerate(lines) if "if is_folder_enabled():" in line)
        following_lines = lines[flag_check_index + 1 : flag_check_index + 3]
        self.assertTrue(any("from app.routers.folder import" in line for line in following_lines))

    def test_folder_flag_is_independent_from_workspace_flag(self) -> None:
        """WorkspaceのFlagとFolderのFlagが、別々の環境変数名を使う
        独立したFlagであることの確認(2つの機能を別々にON/OFF
        できることの裏付け)。"""
        from app.core.feature_flags import _ENV_VAR_NAME, _FOLDER_ENV_VAR_NAME

        self.assertNotEqual(_ENV_VAR_NAME, _FOLDER_ENV_VAR_NAME)


if __name__ == "__main__":
    unittest.main()
