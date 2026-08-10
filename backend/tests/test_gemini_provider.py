"""GeminiProvider(FORGE-AI-CONNECT-001)のテスト。

**重要な限界**: ここでは`httpx.MockTransport`で実際のネットワーク呼び出しを
すべて置き換えている。つまり、ここで検証しているのは「リクエストの組み立て方」
「レスポンスの解析方法」「エラー時にRuntimeErrorへ変換する経路」のみであり、
**実際のGemini APIが本当にこの形式でリクエストを受け付け、この形式で
レスポンスを返すかどうかは検証していない**(Claudeのサンドボックスに
実際のAPIキーが無く、外部ネットワーク上のGemini APIを一度も呼べていない
ため)。CEO環境で実際のAPIキーを設定し、実際に1回呼び出して確認するまでは、
「Gemini接続が動作する」とは言い切れない。

実行方法:
    cd backend
    python -m pytest tests/test_gemini_provider.py -v
"""

from __future__ import annotations

import json
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import httpx  # noqa: E402

from app.ai.foundation.providers import GeminiProvider  # noqa: E402

_SAMPLE_SCHEMA = {
    "type": "object",
    "properties": {
        "goal": {"type": "string"},
        "required_actions": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["goal", "required_actions"],
}


def _mock_client(handler) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler))


class TestGeminiProviderNoApiKey(unittest.TestCase):
    def test_raises_runtime_error_when_no_api_key(self) -> None:
        # 環境変数の実際の値に依存しないよう、明示的に空文字を渡して
        # 「キーが無い」状態を再現する(Noneではなく空文字を渡すと、
        # os.environ.get()へフォールバックしないことをここで検証している)。
        provider = GeminiProvider(api_key="")
        with self.assertRaises(RuntimeError) as ctx:
            provider.complete_structured("test prompt", _SAMPLE_SCHEMA)
        self.assertIn("GEMINI_API_KEY", str(ctx.exception))

    def test_does_not_raise_not_implemented_error(self) -> None:
        """`_UnimplementedProvider`を継承していた頃と違い、これは
        `NotImplementedError`ではなく`RuntimeError`であるべき(呼び出し方の
        問題であり、「未実装」ではないため)。"""
        provider = GeminiProvider(api_key="")
        with self.assertRaises(RuntimeError):
            try:
                provider.complete_structured("test prompt", _SAMPLE_SCHEMA)
            except NotImplementedError:
                self.fail("GeminiProvider should no longer raise NotImplementedError")


class TestGeminiProviderRequestConstruction(unittest.TestCase):
    def test_sends_prompt_and_schema_to_gemini_endpoint(self) -> None:
        captured: dict = {}

        def handler(request: httpx.Request) -> httpx.Response:
            captured["url"] = str(request.url)
            captured["body"] = json.loads(request.content)
            return httpx.Response(
                200,
                json={
                    "candidates": [
                        {"content": {"parts": [{"text": json.dumps({"goal": "x", "required_actions": []})}]}}
                    ]
                },
            )

        provider = GeminiProvider(api_key="fake-key-for-test", client=_mock_client(handler))
        provider.complete_structured("買い物リストを作って", _SAMPLE_SCHEMA)

        self.assertIn("generateContent", captured["url"])
        self.assertIn("key=fake-key-for-test", captured["url"])
        self.assertEqual(captured["body"]["contents"][0]["parts"][0]["text"], "買い物リストを作って")
        self.assertEqual(captured["body"]["generationConfig"]["responseSchema"], _SAMPLE_SCHEMA)
        self.assertEqual(captured["body"]["generationConfig"]["responseMimeType"], "application/json")


class TestGeminiProviderSuccessResponse(unittest.TestCase):
    def test_parses_structured_json_from_response(self) -> None:
        expected = {"goal": "買い物リストを作る", "required_actions": ["add_item", "check_item"]}

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200,
                json={"candidates": [{"content": {"parts": [{"text": json.dumps(expected)}]}}]},
            )

        provider = GeminiProvider(api_key="fake-key-for-test", client=_mock_client(handler))
        result = provider.complete_structured("買い物リストを作って", _SAMPLE_SCHEMA)

        self.assertEqual(result, expected)


class TestGeminiProviderErrorHandling(unittest.TestCase):
    def test_http_error_status_raises_runtime_error(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(400, json={"error": {"message": "invalid API key"}})

        provider = GeminiProvider(api_key="fake-key-for-test", client=_mock_client(handler))
        with self.assertRaises(RuntimeError) as ctx:
            provider.complete_structured("test", _SAMPLE_SCHEMA)
        self.assertIn("400", str(ctx.exception))

    def test_missing_candidates_raises_runtime_error(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json={"promptFeedback": {"blockReason": "SAFETY"}})

        provider = GeminiProvider(api_key="fake-key-for-test", client=_mock_client(handler))
        with self.assertRaises(RuntimeError):
            provider.complete_structured("test", _SAMPLE_SCHEMA)

    def test_non_json_text_raises_runtime_error(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200,
                json={"candidates": [{"content": {"parts": [{"text": "this is not json"}]}}]},
            )

        provider = GeminiProvider(api_key="fake-key-for-test", client=_mock_client(handler))
        with self.assertRaises(RuntimeError):
            provider.complete_structured("test", _SAMPLE_SCHEMA)


if __name__ == "__main__":
    unittest.main()
