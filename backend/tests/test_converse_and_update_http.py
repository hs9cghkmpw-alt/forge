"""`POST /api/v1/ai/converse`・`POST /api/v1/ai/update`のHTTP APIテスト
(FORGE-PRODUCT-VISION-002、2026-08-11)。

`test_http_api.py`と同じ構成(`fastapi.testclient.TestClient`)。
`mock` Providerはキーワードベースのヒューリスティックであり、ASK/BUILD/
UPDATE分岐を狙って制御できないため、ここでは主にHTTPの往復契約
(request_id/session_idの往復、エラー変換)を検証する——分岐ロジック
自体の詳細は`test_conversation_engine.py`(FakeProvider)が担当する。
"""

from __future__ import annotations

import os
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

# `app.main`はプロセス内で1度しかimportされない(以降は`sys.modules`
# キャッシュを再利用する)ため、Feature Flag Router(workspace/folder)の
# 登録可否は「このプロセスで最初に`app.main`をimportした時点の環境変数」
# で確定してしまう。`test_workspace_router.py`・`test_folder_router.py`は
# それぞれ自分のFlagを`setdefault`してから importするが、`unittest
# discover`のファイル発見順(アルファベット順)によっては、このファイルの
# ような「Flagを一切設定しないままimportするファイル」が先に走り、
# 後続の`test_workspace_router.py`等の`setdefault`が手遅れになる
# (実機のフルスイート実行で発見した実バグ、2026-08-11)。この
# ファイル自体はworkspace/folder機能を使わないが、既存ファイルと
# 同じ防御パターンを踏襲し、他ファイルのテストを巻き込んで壊さない
# ようにする。
os.environ.setdefault("FORGE_FEATURE_WORKSPACE", "true")
os.environ.setdefault("FORGE_FEATURE_FOLDER", "true")

try:
    from fastapi.testclient import TestClient

    from app.main import app

    _FASTAPI_AVAILABLE = True
except ImportError:
    _FASTAPI_AVAILABLE = False


@unittest.skipUnless(_FASTAPI_AVAILABLE, "fastapi/pydanticがインストールされていない環境ではスキップする")
class TestConverseEndpoint(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(app)

    def test_first_turn_without_session_id_returns_a_new_session_id(self) -> None:
        response = self.client.post(
            "/api/v1/ai/converse", json={"message": "買い物で何を買うか忘れる", "provider": "mock"},
        )
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertIn(body["status"], ("ask", "build"))
        self.assertTrue(body.get("session_id"))

    def test_unknown_session_id_returns_a_clean_error(self) -> None:
        response = self.client.post(
            "/api/v1/ai/converse",
            json={"session_id": "does-not-exist", "message": "そうそう", "provider": "mock"},
        )
        self.assertEqual(response.status_code, 422)
        body = response.json()
        self.assertEqual(body["status"], "error")
        self.assertEqual(body["error"]["sub_reason"], "conversation_session_not_found")

    def test_provider_failure_during_step_is_converted_to_a_clean_provider_error(self) -> None:
        """実機確認(2026-08-11)で発見した実バグの回帰テスト:
        `ConversationEngine.step()`のProvider呼び出し失敗が、以前は
        汎用の500(「予期しないエラーが発生しました」)まで素通りして
        いた。`ProviderError`(友好的なメッセージ・503)へ変換される
        ことを確認する。"""
        with patch(
            "app.routers.ai.ConversationEngine.step",
            side_effect=RuntimeError("Gemini APIの無料枠の利用上限に達しました。(詳細: status=429)"),
        ):
            response = self.client.post(
                "/api/v1/ai/converse", json={"message": "買い物で忘れる", "provider": "gemini"},
            )
        self.assertEqual(response.status_code, 503)
        body = response.json()
        self.assertEqual(body["status"], "error")
        self.assertEqual(body["error"]["category"], "provider_error")
        self.assertEqual(body["error"]["sub_reason"], "rate_limited")
        self.assertIn("利用上限", body["error"]["message"])


@unittest.skipUnless(_FASTAPI_AVAILABLE, "fastapi/pydanticがインストールされていない環境ではスキップする")
class TestUpdateEndpoint(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(app)

    _VALID_DOC = {
        "version": "1.0", "initial_screen_id": "s1", "app": {"title": "買い物メモ"},
        "screens": [{
            "id": "s1", "title": "買い物メモ",
            "state": {"items": {"type": "checklist", "value": []}, "new_item_text": {"type": "string", "value": ""}},
            "body": {
                "type": "column", "id": "root",
                "children": [
                    {"type": "checklist", "id": "list_view", "state_ref": "items", "empty_state_text": "まだありません"},
                    {"type": "row", "id": "add_row", "children": [
                        {"type": "text_field", "id": "add_field", "state_ref": "new_item_text", "placeholder": "追加"},
                        {"type": "button", "id": "add_button", "label": "追加",
                         "action": {"type": "add_item", "target_state_ref": "items", "source_state_ref": "new_item_text"}},
                    ]},
                ],
            },
        }],
    }

    def test_update_with_mock_provider_returns_a_result_shape(self) -> None:
        """mock Providerは`response_schema`の`properties`が空(`{}`)の
        場合、名前ベースのヒューリスティックが何も合成できず`{}`を返す
        (`MockLLMAdapter.complete_structured()`参照)——つまりmockでは
        `apply_update()`は必ずValidator不合格になる。ここではHTTPの
        往復契約(422・エラー構造)だけを検証する(分岐ロジック自体は
        `test_forge_operation.py`のFakeProviderが担当)。"""
        response = self.client.post(
            "/api/v1/ai/update",
            json={"forge_document": self._VALID_DOC, "change_request": "予算も管理したい", "provider": "mock"},
        )
        self.assertEqual(response.status_code, 422)
        body = response.json()
        self.assertEqual(body["status"], "error")
        self.assertEqual(body["error"]["category"], "validation_error")


if __name__ == "__main__":
    unittest.main()
