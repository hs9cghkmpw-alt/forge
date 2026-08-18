"""`FORGE_EXTRA_PROVIDERS`で足したOpenAI互換Cloudが、実際にHTTPを
話せることの検査（2026-08-17、TD67）。

---

## なぜこのテストが要るのか

TD67は「第二のCloud Providerは**実APIで一度も検証していない**」と
いう負債である。宣言（Registry）とAdapterは書いたが、
**環境変数を置いたら本当に繋がるのか**を誰も確かめていなかった。

実APIを呼べば確かめられるが、それはできない/やらない。

* CIにAPIキーを置かない（`CLAUDE.md` §4）
* 実Cloud APIをCIから呼ばない
* この開発環境は`api.openai.com`等へegress禁止

そこで**OpenAI互換の偽エンドポイントをlocalhostに立てて**、
Registry → 環境変数の解決 → Adapter → HTTPリクエストの形、までを
通す。**実APIの挙動は検証していない**——検証しているのは
*Forge側の配線*であり、そこを混同しない（§12: 実測と公称を分ける）。

## このテストが落ちる条件

* `FORGE_EXTRA_PROVIDERS`が追加Providerを拾わなくなった
* 環境変数の命名規約（`FORGE_<ID>_BASE_URL`等）が変わった
* AdapterがOpenAI互換でないパス・認証方式を送るようになった
"""

from __future__ import annotations

import json
import os
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer

from app.ai.foundation.cloud_provider import OpenAICompatibleCloudProvider
from app.ai.gateway.provider_registry import (
    configured_providers,
    definition_for,
    extra_provider_warnings,
)

_PROVIDER_ID = "test_openai_compatible"
_PREFIX = "FORGE_TEST_OPENAI_COMPATIBLE"

# **本物ではない。** 形が正しいだけの文字列で、どのサービスでも通らない。
_DUMMY_KEY = "dummy-value-not-a-real-key"


class _FakeOpenAIHandler(BaseHTTPRequestHandler):
    """受け取ったリクエストを記録して、OpenAI互換の応答を返すだけ。"""

    received: list[dict] = []

    def do_POST(self) -> None:  # noqa: N802 (BaseHTTPRequestHandlerの規約)
        body = self.rfile.read(int(self.headers.get("Content-Length", 0)))
        authorization = self.headers.get("Authorization") or ""
        type(self).received.append({
            "path": self.path,
            "authorization": authorization,
            "body": json.loads(body or b"{}"),
        })
        payload = {
            "id": "chatcmpl-fake",
            "object": "chat.completion",
            "choices": [{
                "index": 0,
                "finish_reason": "stop",
                "message": {"role": "assistant", "content": json.dumps({"ok": True})},
            }],
        }
        out = json.dumps(payload).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(out)))
        self.end_headers()
        self.wfile.write(out)

    def log_message(self, *args) -> None:  # テスト出力を汚さない
        pass


class TestAnExtraCloudProviderCanBeAddedByConfigurationAlone(unittest.TestCase):
    """**コードを1行も足さずに**Cloud Providerを増やせること（011 §1）。"""

    def setUp(self) -> None:
        _FakeOpenAIHandler.received = []
        self._server = HTTPServer(("127.0.0.1", 0), _FakeOpenAIHandler)
        threading.Thread(target=self._server.serve_forever, daemon=True).start()
        port = self._server.server_address[1]

        self._saved = {k: os.environ.get(k) for k in (
            "FORGE_EXTRA_PROVIDERS",
            f"{_PREFIX}_BASE_URL", f"{_PREFIX}_API_KEY", f"{_PREFIX}_MODEL",
        )}
        os.environ["FORGE_EXTRA_PROVIDERS"] = _PROVIDER_ID
        os.environ[f"{_PREFIX}_BASE_URL"] = f"http://127.0.0.1:{port}/v1"
        os.environ[f"{_PREFIX}_API_KEY"] = _DUMMY_KEY
        os.environ[f"{_PREFIX}_MODEL"] = "some-model"

    def tearDown(self) -> None:
        self._server.shutdown()
        self._server.server_close()
        for key, value in self._saved.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    def test_the_provider_is_declared_without_touching_the_registry(self) -> None:
        self.assertEqual(extra_provider_warnings(), ())
        definition = definition_for(_PROVIDER_ID)
        self.assertIsNotNone(definition, "FORGE_EXTRA_PROVIDERSが拾われていない")
        self.assertEqual(definition.api_key_env, f"{_PREFIX}_API_KEY")
        self.assertEqual(definition.base_url_env, f"{_PREFIX}_BASE_URL")
        self.assertEqual(definition.model_env, f"{_PREFIX}_MODEL")

    def test_it_becomes_a_configured_provider_once_the_env_is_complete(self) -> None:
        self.assertIn(_PROVIDER_ID, [d.provider_id for d in configured_providers()])

    def test_the_settings_are_resolved_from_the_environment(self) -> None:
        provider = OpenAICompatibleCloudProvider(_PROVIDER_ID)
        self.assertEqual(provider.provider_name, _PROVIDER_ID)
        self.assertEqual(provider.model, "some-model")
        self.assertTrue(provider.base_url.startswith("http://127.0.0.1:"))

    def test_it_speaks_the_openai_chat_completions_protocol(self) -> None:
        """**ここがTD67の核心。** 宣言だけでなく、実際にHTTPが飛ぶこと。

        実APIの挙動は検証していない（Test Double）。検証しているのは
        Forge側の配線である。
        """
        provider = OpenAICompatibleCloudProvider(_PROVIDER_ID)
        result = provider.complete_structured(
            "短い指示", {"type": "object", "properties": {"ok": {"type": "boolean"}}}
        )
        self.assertEqual(result, {"ok": True})

        self.assertEqual(len(_FakeOpenAIHandler.received), 1)
        request = _FakeOpenAIHandler.received[0]
        self.assertEqual(request["path"], "/v1/chat/completions")
        self.assertEqual(request["body"]["model"], "some-model")
        self.assertIn("messages", request["body"])

    def test_the_api_key_travels_as_a_bearer_token(self) -> None:
        provider = OpenAICompatibleCloudProvider(_PROVIDER_ID)
        provider.complete_structured("短い指示", {"type": "object"})
        authorization = _FakeOpenAIHandler.received[0]["authorization"]
        self.assertTrue(authorization.startswith("Bearer "), "Bearer認証で送っていない")
        # **鍵そのものは検査しない**が、環境変数の値が届いていることは要る。
        self.assertTrue(authorization.endswith(_DUMMY_KEY))

    def test_a_missing_setting_keeps_the_provider_out_of_the_candidates(self) -> None:
        """**設定が欠けたProviderを候補にしない。** 途中まで設定した
        Providerへ routing して実行時に落ちる、を防ぐ。"""
        del os.environ[f"{_PREFIX}_MODEL"]
        self.assertNotIn(_PROVIDER_ID, [d.provider_id for d in configured_providers()])

    def test_an_existing_provider_id_cannot_be_hijacked(self) -> None:
        """`gemini`を別のエンドポイントへ向けられると、Benchmarkの記録が
        意味を失う。予約語は拒否し、**理由を言う**（黙って消さない）。"""
        os.environ["FORGE_EXTRA_PROVIDERS"] = "gemini"
        self.assertIsNone(
            next((d for d in configured_providers() if d.provider_id == "gemini"
                  and d.base_url_env == "FORGE_GEMINI_BASE_URL"), None),
        )
        self.assertTrue(any("gemini" in w for w in extra_provider_warnings()))


if __name__ == "__main__":
    unittest.main()
