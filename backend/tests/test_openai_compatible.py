"""Generic OpenAI-Compatible Adapter と 失敗の正規化
(FORGE-AI-FOUNDATION-010 Phase E・G・H、2026-08-13)。

## 検証区分の申告(§39)

このファイルの検証は全て **DOUBLE**(Test Double)である。実HTTPは
一切発生しない——`httpx.Client.post`を差し替えている。

したがってここで確かめられるのは「**こういう応答が来たら、Forgeは
こう解釈する**」という契約だけである。「Groqが実際にこの形の429を
返す」ことは確かめていない(この開発環境はProvider公式ドキュメント
のドメインへegress禁止であり、実APIも叩いていない)。

**REAL検証が済んでいるのはGeminiだけ**である(`/converse`経由の
2回の実呼び出し、Phase B)。Multi-Cloud Routingを「実機で確認済み」
とは書かない(§62)。
"""

from __future__ import annotations

import json
import os
import sys
import unittest
from typing import Any
from unittest.mock import patch

import httpx

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from app.ai.foundation.cloud_provider import CloudCompatibleProvider  # noqa: E402
from app.ai.foundation.local_provider import LocalModelError, LocalModelProvider  # noqa: E402
from app.ai.foundation.openai_compatible import (  # noqa: E402
    OpenAICompatibleAdapter,
    classify_http_failure,
    extract_json_object,
)
from app.ai.gateway.ai_errors import ErrorKind, ProviderError, classify_exception  # noqa: E402


def _response(
    status: int = 200,
    *,
    content: str | None = None,
    body: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
) -> httpx.Response:
    if body is None:
        # `content or "{}"` としない——空文字も**渡されたとおり**に返す
        # (空応答を検査するテストが、黙って`{}`にすり替わっていた)。
        body = {"choices": [{"message": {"content": "{}" if content is None else content}}]}
    return httpx.Response(
        status_code=status,
        json=body,
        headers=headers or {},
        request=httpx.Request("POST", "http://test/v1/chat/completions"),
    )


class _Capture:
    """送信内容を記録しつつ、決められた応答を返す。"""

    def __init__(self, *responses: httpx.Response) -> None:
        self._responses = list(responses)
        self.requests: list[dict[str, Any]] = []

    def __call__(self, url: str, *, json: dict[str, Any], headers: dict[str, str]) -> httpx.Response:  # noqa: A002
        self.requests.append({"url": url, "json": json, "headers": headers})
        return self._responses.pop(0) if self._responses else _response()


def _adapter(**kwargs) -> OpenAICompatibleAdapter:
    defaults = {
        "provider_name": "test",
        "base_url": "http://runtime.test/v1",
        "model": "test-model",
    }
    return OpenAICompatibleAdapter(**{**defaults, **kwargs})


class TestTheAdapterSpeaksOpenAICompatible(unittest.TestCase):
    """Phase E: 1つの実装で任意のOpenAI互換エンドポイントを賄う。"""

    def _run(self, capture: _Capture, adapter: OpenAICompatibleAdapter, schema: dict) -> Any:
        with patch.object(httpx.Client, "post", side_effect=capture, autospec=False):
            return adapter.complete_structured("こんにちは", schema)

    def test_it_posts_to_the_chat_completions_path(self) -> None:
        capture = _Capture(_response(content='{"ok": true}'))
        result = self._run(capture, _adapter(), {})
        self.assertEqual(result, {"ok": True})
        self.assertEqual(
            capture.requests[0]["url"], "http://runtime.test/v1/chat/completions"
        )

    def test_a_schema_becomes_json_schema_response_format(self) -> None:
        capture = _Capture(_response(content='{"x": "y"}'))
        schema = {"type": "object", "properties": {"x": {"type": "string"}}}
        self._run(capture, _adapter(), schema)
        sent = capture.requests[0]["json"]["response_format"]
        self.assertEqual(sent["type"], "json_schema")
        self.assertEqual(sent["json_schema"]["schema"], schema)

    def test_an_empty_schema_means_freeform_json(self) -> None:
        """`{}`=スキーマ強制なし。`forge_operation.py`が依存する規約であり、
        Provider間で揃っていなければならない(`GeminiProvider`も同じ)。"""
        capture = _Capture(_response(content='{"anything": 1}'))
        self._run(capture, _adapter(), {})
        self.assertEqual(
            capture.requests[0]["json"]["response_format"], {"type": "json_object"}
        )

    def test_it_is_deterministic(self) -> None:
        """Benchmarkの再現性のため`temperature=0`で固定する。"""
        capture = _Capture(_response(content="{}"))
        self._run(capture, _adapter(), {})
        self.assertEqual(capture.requests[0]["json"]["temperature"], 0.0)

    def test_it_retries_once_with_a_looser_format_when_the_schema_is_not_honored(self) -> None:
        """小さいモデルは`json_schema`をしばしば守れない。1回だけ緩めて
        取り直す。**2回目は無い**(無限に粘らない)。"""
        capture = _Capture(
            _response(content="申し訳ありませんが……"),   # JSONにならない
            _response(content='```json\n{"x": "y"}\n```'),  # フェンス付き
        )
        result = self._run(capture, _adapter(), {"type": "object"})
        self.assertEqual(result, {"x": "y"})
        self.assertEqual(len(capture.requests), 2)
        self.assertEqual(
            capture.requests[1]["json"]["response_format"], {"type": "json_object"}
        )

    def test_freeform_requests_are_not_retried(self) -> None:
        """スキーマを渡していないなら、緩める余地が無い。"""
        capture = _Capture(_response(content="これはJSONではありません"))
        with self.assertRaises(Exception):
            self._run(capture, _adapter(), {})
        self.assertEqual(len(capture.requests), 1)

    def test_it_never_returns_an_empty_dict_to_fake_success(self) -> None:
        """TD40の教訓——空`{}`を返して「成功」に見せかけない。"""
        capture = _Capture(_response(content=""), _response(content=""))
        with self.assertRaises(Exception):
            self._run(capture, _adapter(), {"type": "object"})

    def test_a_non_openai_shaped_response_is_a_structured_output_failure(self) -> None:
        capture = _Capture(_response(body={"unexpected": "shape"}))
        with patch.object(httpx.Client, "post", side_effect=capture):
            with self.assertRaises(ProviderError) as caught:
                _adapter().complete_structured("p", {})
        self.assertIs(caught.exception.kind, ErrorKind.STRUCTURED_OUTPUT_FAILURE)


class TestApiKeysStayOutOfEverythingButTheHeader(unittest.TestCase):
    """§14〜§18: 鍵はインスタンスにも例外にも残さない。"""

    def setUp(self) -> None:
        self._saved = os.environ.get("TEST_SECRET_TOKEN")
        os.environ["TEST_SECRET_TOKEN"] = "dummy-value-not-a-real-key"

    def tearDown(self) -> None:
        if self._saved is None:
            os.environ.pop("TEST_SECRET_TOKEN", None)
        else:
            os.environ["TEST_SECRET_TOKEN"] = self._saved

    def test_the_key_is_read_from_the_environment_at_send_time(self) -> None:
        capture = _Capture(_response(content="{}"))
        adapter = _adapter(api_key_env="TEST_SECRET_TOKEN")
        with patch.object(httpx.Client, "post", side_effect=capture):
            adapter.complete_structured("p", {})
        self.assertEqual(
            capture.requests[0]["headers"]["Authorization"],
            "Bearer dummy-value-not-a-real-key",
        )

    def test_the_key_is_not_stored_on_the_instance(self) -> None:
        adapter = _adapter(api_key_env="TEST_SECRET_TOKEN")
        self.assertNotIn("dummy-value-not-a-real-key", repr(vars(adapter)))

    def test_a_missing_key_is_not_guessed_into_an_error(self) -> None:
        """鍵が無くても**こちらでは失敗させない**。

        Providerに401を返させて、Phase Gの分類が`AUTH`として扱う。
        推測でエラーを作ると、鍵不要のRuntimeまで巻き込む。
        """
        os.environ.pop("TEST_SECRET_TOKEN", None)
        capture = _Capture(_response(content="{}"))
        adapter = _adapter(api_key_env="TEST_SECRET_TOKEN")
        with patch.object(httpx.Client, "post", side_effect=capture):
            adapter.complete_structured("p", {})
        self.assertNotIn("Authorization", capture.requests[0]["headers"])

    def test_the_prompt_is_never_included_in_an_error(self) -> None:
        """プロンプトは利用者の入力そのものである。例外へ載せない。"""
        capture = _Capture(_response(500, body={"error": {"message": "boom"}}))
        with patch.object(httpx.Client, "post", side_effect=capture):
            with self.assertRaises(ProviderError) as caught:
                _adapter().complete_structured("秘密の相談ごと", {})
        self.assertNotIn("秘密の相談ごと", str(caught.exception))


class TestFailuresAreClassifiedByTheStrongestEvidence(unittest.TestCase):
    """Phase G: 構造化 → ステータス → ヘッダ → 本文 → 文字列 の順。"""

    def test_a_structured_error_type_wins_over_the_status_code(self) -> None:
        """429だが`insufficient_quota`——**枠切れ**であって流量制限ではない。

        復帰条件が違う(`reset_at`待ち vs cooldown)ので、取り違えると
        戻らないProviderを叩き続けるか、戻るProviderを長く捨てる。
        """
        error = classify_http_failure(
            provider="p", status_code=429,
            body_text=json.dumps({"error": {"type": "insufficient_quota", "message": "no credit"}}),
        )
        self.assertIs(error.kind, ErrorKind.QUOTA_EXHAUSTED)

    def test_a_structured_rate_limit_stays_a_rate_limit(self) -> None:
        error = classify_http_failure(
            provider="p", status_code=429,
            body_text=json.dumps({"error": {"type": "rate_limit_exceeded"}}),
        )
        self.assertIs(error.kind, ErrorKind.RATE_LIMITED)

    def test_the_status_code_is_used_when_there_is_no_structured_error(self) -> None:
        cases = {
            401: ErrorKind.AUTH,
            403: ErrorKind.AUTH,
            404: ErrorKind.MODEL_UNAVAILABLE,
            422: ErrorKind.INVALID_REQUEST,
            429: ErrorKind.RATE_LIMITED,
            500: ErrorKind.PROVIDER_SERVER_ERROR,
            503: ErrorKind.PROVIDER_SERVER_ERROR,
        }
        for status, expected in cases.items():
            with self.subTest(status=status):
                self.assertIs(
                    classify_http_failure(provider="p", status_code=status).kind, expected
                )

    def test_an_unknown_5xx_is_still_a_server_error(self) -> None:
        self.assertIs(
            classify_http_failure(provider="p", status_code=599).kind,
            ErrorKind.PROVIDER_SERVER_ERROR,
        )

    def test_the_status_code_wins_over_a_message_that_says_nothing(self) -> None:
        """**Phase Gの要点**。

        以前の分類は文字列マッチだけだったので、429であっても本文に
        "rate limit"という語が無ければ`UNKNOWN`へ落ちていた。
        ステータスという明確な事実がある以上、そちらを使う。
        """
        error = classify_http_failure(
            provider="p", status_code=429, body_text="Too many requests, friend."
        )
        self.assertIs(error.kind, ErrorKind.RATE_LIMITED)
        self.assertNotEqual(error.kind, ErrorKind.UNKNOWN)

    def test_retry_after_is_read_from_the_header(self) -> None:
        """**いつ復帰するか**はヘッダにしか無い。"""
        error = classify_http_failure(
            provider="p", status_code=429, headers={"Retry-After": "42"}
        )
        self.assertEqual(error.retry_after_seconds, 42.0)

    def test_a_missing_retry_after_is_none_not_zero(self) -> None:
        """`None`を「すぐ再試行してよい」と読ませない。"""
        self.assertIsNone(
            classify_http_failure(provider="p", status_code=429).retry_after_seconds
        )

    def test_the_body_catches_quota_that_the_status_code_misses(self) -> None:
        """枠切れは429以外(402等)でも来る。"""
        error = classify_http_failure(
            provider="p", status_code=402, body_text="You exceeded your current quota."
        )
        self.assertIs(error.kind, ErrorKind.QUOTA_EXHAUSTED)

    def test_a_body_hint_never_downgrades_a_server_error(self) -> None:
        """本文は弱い証拠。5xxという強い証拠を上書きしない。"""
        error = classify_http_failure(
            provider="p", status_code=503, body_text="quota service unavailable"
        )
        self.assertIs(error.kind, ErrorKind.PROVIDER_SERVER_ERROR)

    def test_an_invalid_request_does_not_travel_to_other_providers(self) -> None:
        """Forge側の誤りは、相手を変えても直らない(§19)。"""
        error = classify_http_failure(provider="p", status_code=400)
        self.assertFalse(error.kind.should_try_other_providers)

    def test_the_classified_error_passes_through_the_router_unchanged(self) -> None:
        """Adapterが分類済みなら、Routerは再分類しない。

        文字列マッチへ落ちると、せっかくのHTTPステータスが失われる。
        """
        original = classify_http_failure(provider="p", status_code=401)
        self.assertIs(classify_exception(original, "p"), original)


class TestLocalKeepsItsOwnVoice(unittest.TestCase):
    """共通化しても、Localに固有な意味は失わない。"""

    def test_a_connection_failure_says_the_runtime_is_not_running(self) -> None:
        """「ネットワーク障害」ではなく「Ollamaを起動してください」。
        運用者が直せる言葉にする。"""
        with patch.object(httpx.Client, "post", side_effect=httpx.ConnectError("refused")):
            with self.assertRaises(LocalModelError) as caught:
                LocalModelProvider().complete_structured("p", {})
        self.assertIn("起動している", str(caught.exception))

    def test_a_local_failure_is_classified_as_a_local_resource_error(self) -> None:
        """`ProviderStateStore`がCircuit Breakerの対象として扱えること。"""
        error = classify_exception(LocalModelError("runtime down"), "local")
        self.assertIs(error.kind, ErrorKind.LOCAL_RESOURCE_ERROR)

    def test_extract_json_object_still_raises_local_model_error(self) -> None:
        """`local_provider.extract_json_object`は既存の呼び出し側との
        後方互換のため、失敗時の型を`LocalModelError`へ固定している
        (共通実装は`ResponseFormatError`を投げる)。"""
        from app.ai.foundation.local_provider import (  # noqa: PLC0415
            extract_json_object as local_extract,
        )

        with self.assertRaises(LocalModelError):
            local_extract("これはJSONではありません")

    def test_it_still_tolerates_fences_and_chatter(self) -> None:
        self.assertEqual(
            extract_json_object('はい、どうぞ: ```json\n{"a": 1}\n``` 以上です'), {"a": 1}
        )


class TestTheSecondCloudSlot(unittest.TestCase):
    """Phase H: 環境変数3つでCloud Providerが1つ増える。"""

    _VARS = (
        "FORGE_CLOUD_BASE_URL", "FORGE_CLOUD_API_KEY",
        "FORGE_CLOUD_MODEL", "FORGE_CLOUD_EXTRA_HEADERS",
        # conftestが`mock`へ固定しているが、pinがあるとCatalogはそれ1つに
        # なる(運用者の明示指定をRouterが上書きしない、Phase B)。
        # Auto Discoveryを見たいのでここでは外す。
        "FORGE_DEFAULT_PROVIDER",
    )

    def setUp(self) -> None:
        self._saved = {key: os.environ.get(key) for key in self._VARS}
        for key in self._VARS:
            os.environ.pop(key, None)

    def tearDown(self) -> None:
        for key, value in self._saved.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    def test_it_can_be_constructed_while_unconfigured(self) -> None:
        """`ProviderRouter`は起動時に全Providerを構築する。1つ未設定な
        だけでForge全体が起動しなくなってはならない。"""
        provider = CloudCompatibleProvider()
        self.assertEqual(provider.base_url, "")

    def test_configuration_is_read_lazily(self) -> None:
        """構築時に環境を焼き付けない。

        `ProviderRouter`の構築はプロセス起動時に1度だけなので、
        焼き付けると「Auto Discoveryは候補に載せるのに、Adapterは
        空のURLへ投げる」というずれが起きる。
        """
        provider = CloudCompatibleProvider()
        os.environ["FORGE_CLOUD_BASE_URL"] = "https://example.test/v1/"
        os.environ["FORGE_CLOUD_MODEL"] = "some-model"
        self.assertEqual(provider.base_url, "https://example.test/v1")
        self.assertEqual(provider.model, "some-model")

    def test_extra_headers_are_merged_without_provider_specific_branches(self) -> None:
        """OpenRouterの`HTTP-Referer`等。**if文をProviderごとに増やさない。**"""
        os.environ["FORGE_CLOUD_BASE_URL"] = "https://example.test/v1"
        os.environ["FORGE_CLOUD_MODEL"] = "m"
        os.environ["FORGE_CLOUD_EXTRA_HEADERS"] = json.dumps({"X-Title": "Forge"})
        capture = _Capture(_response(content="{}"))
        with patch.object(httpx.Client, "post", side_effect=capture):
            CloudCompatibleProvider().complete_structured("p", {})
        self.assertEqual(capture.requests[0]["headers"]["X-Title"], "Forge")

    def test_broken_extra_headers_do_not_stop_forge(self) -> None:
        """壊れたJSONで起動を止めない。ヘッダが要るProviderだけが
        401として現れ、分類される。"""
        os.environ["FORGE_CLOUD_BASE_URL"] = "https://example.test/v1"
        os.environ["FORGE_CLOUD_MODEL"] = "m"
        os.environ["FORGE_CLOUD_EXTRA_HEADERS"] = "{ not json"
        capture = _Capture(_response(content="{}"))
        with patch.object(httpx.Client, "post", side_effect=capture):
            CloudCompatibleProvider().complete_structured("p", {})
        self.assertIn("Content-Type", capture.requests[0]["headers"])

    def test_it_needs_all_three_variables_to_be_discovered(self) -> None:
        from app.ai.gateway.provider_registry import definition_for  # noqa: PLC0415

        definition = definition_for("cloud")
        self.assertFalse(definition.is_configured)
        self.assertEqual(
            set(definition.missing_variables()),
            {"FORGE_CLOUD_BASE_URL", "FORGE_CLOUD_API_KEY", "FORGE_CLOUD_MODEL"},
        )
        os.environ["FORGE_CLOUD_BASE_URL"] = "https://example.test/v1"
        os.environ["FORGE_CLOUD_API_KEY"] = "dummy-value-not-a-real-key"
        self.assertFalse(definition.is_configured, "モデル名が無ければ何を投げるか決まらない")
        os.environ["FORGE_CLOUD_MODEL"] = "m"
        self.assertTrue(definition.is_configured)

    def test_it_joins_routing_once_configured(self) -> None:
        """**設定するだけでRoutingへ載る**(コード変更が要らない)ことの確認。"""
        from app.ai.gateway.ai_router import default_catalog  # noqa: PLC0415

        self.assertNotIn("cloud", [m.provider for m in default_catalog()])
        os.environ["FORGE_CLOUD_BASE_URL"] = "https://example.test/v1"
        os.environ["FORGE_CLOUD_API_KEY"] = "dummy-value-not-a-real-key"
        os.environ["FORGE_CLOUD_MODEL"] = "m"
        catalog = {m.provider: m for m in default_catalog()}
        self.assertIn("cloud", catalog)
        self.assertFalse(catalog["cloud"].is_local, "Cloudとして扱われていない")


if __name__ == "__main__":
    unittest.main()
