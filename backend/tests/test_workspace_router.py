"""`GET`/`PATCH /v1/workspace`のAPI Contract Test(FORGE V2 Phase 1)。

**重要な注記(未検証)**: Claudeのサンドボックスには`fastapi`・
`pydantic`・`supabase`がインストールされておらず(ネットワーク不可の
ため`pip install`できず)、このファイル自体を一度も実行できていない
(`backend/tests/test_http_api.py`と全く同じ制限・同じ回避パターン)。
構文は`py_compile`で静的に確認済みだが、実際にFastAPIの`TestClient`を
使った検証はCEO環境(`pip install -r requirements.txt`実行後)で
行う必要がある。

さらに、`app/core/security.py`の`_verify_and_decode()`が未実装
(`NotImplementedError`)であるため、**fastapi/pydanticが揃った
CEO環境でも、`_verify_and_decode()`が実装されるまでは、この
Contract Testの認証成功系(200を期待するテスト)は失敗し続ける**。
これはFeature Flag/Router自体の欠陥ではなく、`security.py`の
docstringに明記した通り、意図的に後続作業として残した部分である。

実行方法(CEO環境):
    cd backend
    pip install -r requirements.txt --break-system-packages
    export FORGE_FEATURE_WORKSPACE=true
    python -m unittest tests.test_workspace_router -v
"""

from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

os.environ.setdefault("FORGE_FEATURE_WORKSPACE", "true")

try:
    from fastapi.testclient import TestClient

    from app.main import app

    _FASTAPI_AVAILABLE = True
except ImportError:
    _FASTAPI_AVAILABLE = False


@unittest.skipUnless(_FASTAPI_AVAILABLE, "fastapi/pydantic/supabaseがインストールされていない環境ではスキップする")
class TestWorkspaceRouterContract(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(app)

    def test_get_without_authorization_header_returns_401(self) -> None:
        response = self.client.get("/v1/workspace")
        self.assertEqual(response.status_code, 401)

    def test_get_with_malformed_authorization_header_returns_401(self) -> None:
        response = self.client.get("/v1/workspace", headers={"Authorization": "NotBearer xyz"})
        self.assertEqual(response.status_code, 401)

    def test_patch_without_authorization_header_returns_401(self) -> None:
        response = self.client.patch("/v1/workspace", json={"display_default_view": "list"})
        self.assertEqual(response.status_code, 401)

    # --- 以下、_verify_and_decode()実装後にCEO環境で意味を持つテスト ---
    # (現時点ではNotImplementedErrorにより500相当になり、期待通りには
    # 通らない。security.py完成後、有効なテスト用JWTを用意した上で
    # 有効化する)

    @unittest.skip("app/core/security.py の _verify_and_decode() 実装待ち(CEO環境)")
    def test_get_creates_workspace_on_first_access(self) -> None:
        response = self.client.get("/v1/workspace", headers={"Authorization": "Bearer <valid-test-jwt>"})
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertIn("id", body)
        self.assertEqual(body["display_default_view"], "icon")
        self.assertEqual(body["structure_version"], 1)

    @unittest.skip("app/core/security.py の _verify_and_decode() 実装待ち(CEO環境)")
    def test_get_twice_returns_the_same_workspace(self) -> None:
        first = self.client.get("/v1/workspace", headers={"Authorization": "Bearer <valid-test-jwt>"})
        second = self.client.get("/v1/workspace", headers={"Authorization": "Bearer <valid-test-jwt>"})
        self.assertEqual(first.json()["id"], second.json()["id"])

    @unittest.skip("app/core/security.py の _verify_and_decode() 実装待ち(CEO環境)")
    def test_patch_updates_display_default_view(self) -> None:
        self.client.get("/v1/workspace", headers={"Authorization": "Bearer <valid-test-jwt>"})
        response = self.client.patch(
            "/v1/workspace",
            json={"display_default_view": "list"},
            headers={"Authorization": "Bearer <valid-test-jwt>"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["display_default_view"], "list")

    @unittest.skip("app/core/security.py の _verify_and_decode() 実装待ち(CEO環境)")
    def test_patch_with_invalid_view_type_returns_400(self) -> None:
        self.client.get("/v1/workspace", headers={"Authorization": "Bearer <valid-test-jwt>"})
        response = self.client.patch(
            "/v1/workspace",
            json={"display_default_view": "not_a_real_view"},
            headers={"Authorization": "Bearer <valid-test-jwt>"},
        )
        self.assertEqual(response.status_code, 400)

    @unittest.skip("app/core/security.py の _verify_and_decode() 実装待ち(CEO環境)")
    def test_two_different_users_cannot_see_each_others_workspace(self) -> None:
        r1 = self.client.get("/v1/workspace", headers={"Authorization": "Bearer <user-a-jwt>"})
        r2 = self.client.get("/v1/workspace", headers={"Authorization": "Bearer <user-b-jwt>"})
        self.assertNotEqual(r1.json()["id"], r2.json()["id"])


@unittest.skipIf(_FASTAPI_AVAILABLE, "fastapi無し環境でのFeature Flag OFF時の挙動確認(fastapi有りなら通常のTestClient系テストで代替済み)")
class TestFeatureFlagOffDoesNotAffectExistingBehavior(unittest.TestCase):
    """絶対条件「Feature Flag OFF時に既存挙動へ影響しない」の確認。

    fastapi不在環境では実際のHTTPテストができないため、少なくとも
    `app/main.py`の追記部分が、`is_workspace_enabled()`が`False`の
    場合に`workspace_router`をimportすらしない(遅延import、
    `app/main.py`参照)ことを、ソースコード上で確認する形に留める。
    """

    def test_workspace_router_import_is_lazy_and_conditional(self) -> None:
        with open(os.path.join(os.path.dirname(__file__), "..", "app", "main.py"), encoding="utf-8") as f:
            main_source = f.read()
        self.assertIn("if is_workspace_enabled():", main_source)
        # workspace_routerのimportが、if文の内側(インデントされた行)に
        # あることを確認する(遅延・条件付きimportであることの裏付け)。
        lines = main_source.splitlines()
        flag_check_index = next(i for i, line in enumerate(lines) if "if is_workspace_enabled():" in line)
        following_lines = lines[flag_check_index + 1 : flag_check_index + 3]
        self.assertTrue(any("from app.routers.workspace import" in line for line in following_lines))


if __name__ == "__main__":
    unittest.main()
