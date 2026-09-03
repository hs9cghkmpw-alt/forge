"""Structured Output mode と HTTP 400 の読み分け
(FORGE-AI-FOUNDATION-011 §2、2026-08-14)。

指示書が挙げた4つのRegressionをそのまま実装し、判別不能な400の扱いを
1つ足してある。

---

## 修正した実バグ(修正前に再現を確認した)

    Provider A: json_schema unsupported
        ↓ HTTP 400
      INVALID_REQUEST(「Forge側の誤り」)
        ↓
      should_try_other_providers == False
        ↓
      **全Routing停止**

`json_object`へのfallbackは「JSON抽出に失敗した場合」にしか書かれて
おらず、400では`_chat()`内で例外になって到達しなかった。

## 分け方の要点

同じHTTP 400でも、**緩めてよい400と、緩めてはいけない400がある**。

* 緩めてよい — 相手がそのmodeを知らない。緩めれば通る。
* 緩めてはいけない — Forgeのスキーマが不正。緩めるとスキーマ制約が
  外れ、**Forge自身のバグを黙って回避して「成功」を返す**。

判別できないときは「緩めないが、他のProviderへは進む」。緩めれば
バグを隠しうるし、止めれば相手の癖1つでForgeが止まる。

## 検証区分(§39)

すべて **DOUBLE**。実HTTPは発生しない。「Groqが実際にこの形の400を
返す」ことは確認していない。
"""

from __future__ import annotations

import os
import sys
import unittest
from typing import Any
from unittest.mock import patch

import httpx

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from app.ai.foundation.openai_compatible import OpenAICompatibleAdapter  # noqa: E402
from app.ai.gateway.ai_errors import ErrorKind, ProviderError  # noqa: E402
from app.ai.gateway.provider_registry import StructuredOutputMode, weaker_mode  # noqa: E402
from app.ai.gateway.structured_output_capability import (  # noqa: E402
    FourHundredReading,
    default_capability_store,
    read_four_hundred,
)

import pytest

from app.ai.gateway.external_call_policy import allow_mocked_transport


# FORGE-EXTERNAL-CALL-DEFAULT-DENY(2026-09-03)。
#
# このファイルは `httpx.Client.post` を差し替えており、**ネットワークへは
# 一切出ない**。`external_call_policy` は既定で実 Provider への通信を拒否
# するので、「ここは出ていない」ことを明示的に宣言する。
#
# 環境変数ではなく呼び出し側の明示にしてあるのは、`.env` の中身で挙動が
# 変わる経路をもう一度作らないためである（それが 2026-09-02 の事故の形）。
@pytest.fixture(autouse=True)
def _network_is_mocked_in_this_module():
    with allow_mocked_transport():
        yield



_SCHEMA = {"type": "object", "properties": {"x": {"type": "integer"}}}


def _resp(status: int, body: dict[str, Any]) -> httpx.Response:
    return httpx.Response(
        status, json=body, request=httpx.Request("POST", "http://t/v1/chat/completions")
    )


def _ok() -> httpx.Response:
    return _resp(200, {"choices": [{"message": {"content": '{"x": 1}'}}]})


def _error(message: str, *, status: int = 400, kind: str = "invalid_request_error") -> httpx.Response:
    return _resp(status, {"error": {"message": message, "type": kind}})


class _AdapterCase(unittest.TestCase):
    """応答列を与えて、送信されたmodeを観測する共通土台。"""

    def setUp(self) -> None:
        default_capability_store().reset()
        self.addCleanup(default_capability_store().reset)

    def _run(
        self, *responses: httpx.Response, schema: dict[str, Any] | None = None,
        provider: str = "testcloud", model: str = "m",
    ) -> tuple[Any, list[str | None], Exception | None]:
        queue = list(responses)
        sent: list[str | None] = []
        adapter = OpenAICompatibleAdapter(
            provider_name=provider, base_url="http://t/v1", model=model
        )

        def post(url: str, *, json: dict[str, Any], headers: dict[str, str]) -> httpx.Response:  # noqa: A002
            sent.append((json.get("response_format") or {}).get("type"))
            return queue.pop(0) if queue else _ok()

        with patch.object(httpx.Client, "post", side_effect=post):
            try:
                value = adapter.complete_structured(
                    "prompt", _SCHEMA if schema is None else schema
                )
            except Exception as exc:  # noqa: BLE001 — 分類そのものが検査対象
                return None, sent, exc
        return value, sent, None


class TestTheFourRequiredScenarios(_AdapterCase):
    """指示書§2が列挙したRegression 1〜4。"""

    def test_1_json_schema_success(self) -> None:
        value, sent, error = self._run(_ok())
        self.assertIsNone(error)
        self.assertEqual(value, {"x": 1})
        self.assertEqual(sent, ["json_schema"])

    def test_2_json_schema_400_due_to_unsupported_mode_falls_back_to_json_object(self) -> None:
        """**これが直した実バグそのものである。**"""
        value, sent, error = self._run(
            _error("response_format.type: json_schema is not supported"), _ok()
        )
        self.assertIsNone(error, f"fallbackへ到達していない: {error}")
        self.assertEqual(value, {"x": 1})
        self.assertEqual(sent, ["json_schema", "json_object"])

    def test_3_a_genuinely_invalid_forge_schema_does_not_fall_back(self) -> None:
        """**緩めてはいけない400。**

        緩めるとスキーマ制約が外れ、Forge自身のバグを回避したまま
        「成功」を返すことになる。巡回も止める(相手を変えても同じ)。
        """
        _, sent, error = self._run(
            _error("Invalid schema for response_format: 'properties' is required")
        )
        self.assertIsInstance(error, ProviderError)
        self.assertIs(error.kind, ErrorKind.INVALID_REQUEST)
        self.assertFalse(error.kind.should_try_other_providers)
        self.assertEqual(sent, ["json_schema"], "緩めてはいけない場面で緩めている")

    def test_4_when_json_object_is_also_unsupported_other_providers_are_still_tried(self) -> None:
        """§2「別Providerへ進めるかをPolicyで判断」。

        「このProviderが対応していない」は、**他のProviderについては
        何も言っていない**。巡回は止めない。故障でもないので
        Circuit Breakerにも数えない。
        """
        _, sent, error = self._run(
            _error("response_format is not supported"),
            _error("response_format is not supported"),
        )
        self.assertIsInstance(error, ProviderError)
        self.assertIs(error.kind, ErrorKind.UNSUPPORTED_OUTPUT_MODE)
        self.assertTrue(error.kind.should_try_other_providers)
        self.assertFalse(error.kind.counts_toward_circuit_breaker)
        self.assertEqual(sent, ["json_schema", "json_object"], "2段以上緩めている")


class TestAnOpaque400IsHandledSafely(_AdapterCase):
    """判別できない400。**どちらの害も避ける位置に置く。**"""

    def test_it_does_not_downgrade_but_does_let_routing_continue(self) -> None:
        _, sent, error = self._run(_resp(400, {"error": {"message": "Bad request."}}))
        self.assertIs(error.kind, ErrorKind.UNSUPPORTED_OUTPUT_MODE)
        self.assertTrue(error.kind.should_try_other_providers)
        self.assertEqual(sent, ["json_schema"], "根拠なく緩めている")

    def test_a_mode_that_worked_before_makes_an_opaque_400_our_fault(self) -> None:
        """一度通ったmodeでの不透明な400は、**中身の問題**である。

        相手はそのmodeを理解できるのだから、断られたのはこちらの
        送った内容が原因と考える方が正しい。
        """
        default_capability_store().note_worked(
            "testcloud", "m", StructuredOutputMode.JSON_SCHEMA
        )
        _, _, error = self._run(_resp(400, {"error": {"message": "Bad request."}}))
        self.assertIs(error.kind, ErrorKind.INVALID_REQUEST)
        self.assertFalse(error.kind.should_try_other_providers)


class TestTheAdapterLearnsInsteadOfRepeatingTheMistake(_AdapterCase):
    """宣言より事実を優先する(§46と同じ姿勢)。"""

    def test_the_second_call_starts_at_the_mode_that_worked(self) -> None:
        queue = [
            _error("json_schema is not supported"), _ok(),  # 1回目: 学習
            _ok(), _ok(),                                    # 2・3回目
        ]
        sent: list[str | None] = []
        adapter = OpenAICompatibleAdapter(
            provider_name="testcloud", base_url="http://t/v1", model="m"
        )

        def post(url: str, *, json: dict[str, Any], headers: dict[str, str]) -> httpx.Response:  # noqa: A002
            sent.append((json.get("response_format") or {}).get("type"))
            return queue.pop(0)

        with patch.object(httpx.Client, "post", side_effect=post):
            for _ in range(3):
                adapter.complete_structured("prompt", _SCHEMA)

        self.assertEqual(sent, ["json_schema", "json_object", "json_object", "json_object"])

    def test_learning_is_per_model_not_only_per_provider(self) -> None:
        """同じProviderでもモデルによって対応が違う。Providerだけで
        覚えると、モデルを変えた瞬間に嘘になる。"""
        store = default_capability_store()
        store.note_unsupported("testcloud", "m1", StructuredOutputMode.JSON_SCHEMA)
        self.assertIn(
            StructuredOutputMode.JSON_SCHEMA, store.known_unsupported("testcloud", "m1")
        )
        self.assertEqual(store.known_unsupported("testcloud", "m2"), frozenset())


class TestReadingA400(unittest.TestCase):
    """読み分けそのもの。"""

    def test_it_recognises_an_unsupported_mode(self) -> None:
        for message in (
            "response_format.type: json_schema is not supported",
            "Unknown parameter: 'response_format'.",
            "json_object is not supported by this model",
            "response_format に対応していません",
        ):
            with self.subTest(message=message):
                self.assertIs(read_four_hundred(message), FourHundredReading.MODE_UNSUPPORTED)

    def test_it_recognises_our_own_bad_schema(self) -> None:
        for message in (
            "Invalid schema for response_format: 'properties' is required",
            "failed to parse schema",
            "context_length_exceeded",
        ):
            with self.subTest(message=message):
                self.assertIs(
                    read_four_hundred(message), FourHundredReading.FORGE_REQUEST_INVALID
                )

    def test_schema_invalidity_wins_over_a_mode_mention(self) -> None:
        """「スキーマが不正」は`response_format`という語を含みうる。
        取り違えると**Forgeのバグを黙って回避する**方向へ倒れるので、
        安全側(緩めない)を先に見る。"""
        self.assertIs(
            read_four_hundred("Invalid schema for response_format: not supported type"),
            FourHundredReading.FORGE_REQUEST_INVALID,
        )

    def test_an_opaque_message_is_ambiguous_not_a_guess(self) -> None:
        """分類できていないことを、分類結果に混ぜない。"""
        self.assertIs(read_four_hundred("Bad request"), FourHundredReading.AMBIGUOUS)
        self.assertIs(read_four_hundred(""), FourHundredReading.AMBIGUOUS)


class TestTheModeLadder(unittest.TestCase):
    """強い順に並んでいること、1段ずつしか下がらないこと。"""

    def test_each_step_is_exactly_one_weaker(self) -> None:
        self.assertIs(
            weaker_mode(StructuredOutputMode.STRICT_JSON_SCHEMA),
            StructuredOutputMode.JSON_SCHEMA,
        )
        self.assertIs(
            weaker_mode(StructuredOutputMode.JSON_SCHEMA), StructuredOutputMode.JSON_OBJECT
        )
        self.assertIs(
            weaker_mode(StructuredOutputMode.JSON_OBJECT), StructuredOutputMode.PROMPT_JSON
        )

    def test_the_weakest_mode_cannot_be_weakened(self) -> None:
        self.assertIsNone(weaker_mode(StructuredOutputMode.PROMPT_JSON))

    def test_prompt_json_sends_no_response_format_at_all(self) -> None:
        """最後の砦。`response_format`という語を知らないProviderでも通る。"""
        adapter = OpenAICompatibleAdapter(
            provider_name="testcloud", base_url="http://t/v1", model="m"
        )
        payload = adapter._payload("p", _SCHEMA, StructuredOutputMode.PROMPT_JSON)  # noqa: SLF001
        self.assertNotIn("response_format", payload)

    def test_strict_mode_sets_strict_true(self) -> None:
        adapter = OpenAICompatibleAdapter(
            provider_name="testcloud", base_url="http://t/v1", model="m"
        )
        payload = adapter._payload("p", _SCHEMA, StructuredOutputMode.STRICT_JSON_SCHEMA)  # noqa: SLF001
        self.assertTrue(payload["response_format"]["json_schema"]["strict"])


if __name__ == "__main__":
    unittest.main()
