"""**呼んでいない Provider の名前を Evidence へ書かない**（TD104）。

---

## 何が壊れていたか

```python
provider_name = provider.last_provider_used or request.provider or "unknown"
```

`or request.provider` が問題である。`last_provider_used` が `None`
（**1回も Model を呼んでいない**）とき、**指定されただけの Provider 名**へ
落ちる。Fast path は LLM を 0 回しか呼ばないので、`provider=gemini` を
指定した要求は「Gemini が答えた」という Evidence を残していた。呼んでいない。

指定（configured）は設定であって、使った事実（actually used）ではない。

## 配線破壊試験

`routers/ai.py` の `attribution.reported_provider` を
`provider.last_provider_used or request.provider or "unknown"` へ戻すと
`TestZeroModelCallsDoNotNameAProvider` が落ちる。
"""

from __future__ import annotations

import pathlib
import sys
import unittest
from unittest.mock import patch

_ROOT = pathlib.Path(__file__).resolve().parents[2]
for path in (str(_ROOT), str(_ROOT / "backend")):
    if path not in sys.path:
        sys.path.insert(0, path)

from app.ai.runtime.conversation_types import (  # noqa: E402
    ConversationAction,
    ConversationReadiness,
    ConversationStepResult,
    NeedModel,
)
from app.ai.gateway.model_call_ledger import (  # noqa: E402
    NO_MODEL_CALL,
    UNRECORDED_PROVIDER,
    ModelCall,
    ModelCallLedger,
    current_ledger,
    record_model_call,
    record_routed_result,
    recording,
)

try:
    from fastapi.testclient import TestClient  # noqa: E402

    from app.main import app  # noqa: E402

    _FASTAPI_AVAILABLE = True
except Exception:  # noqa: BLE001
    _FASTAPI_AVAILABLE = False


class _FakeAttempt:
    def __init__(self, provider: str, ok: bool, model: str = "") -> None:
        self.provider = provider
        self.ok = ok
        self.model = model
        self.latency_ms = 1.0
        self.detail = ""


class _FakeRouted:
    def __init__(self, provider_used: str, attempts: tuple[_FakeAttempt, ...]) -> None:
        self.provider_used = provider_used
        self.attempts = attempts


class TestTheLedgerSeparatesConfiguredFromUsed(unittest.TestCase):
    def test_zero_calls_produce_no_provider_name(self) -> None:
        """**これが TD104 の核心である。**"""
        attribution = ModelCallLedger().attribution(configured_provider="gemini")

        self.assertEqual(attribution.configured_provider, "gemini")
        self.assertIsNone(attribution.actually_used_provider)
        self.assertEqual(attribution.reported_provider, NO_MODEL_CALL)
        self.assertEqual(attribution.model_calls, 0)
        self.assertTrue(attribution.deterministic_path)
        self.assertFalse(attribution.fallback_used)

    def test_a_successful_call_is_attributed_to_who_answered(self) -> None:
        ledger = ModelCallLedger()
        ledger.record(ModelCall(provider="local", model="qwen2.5:1.5b", ok=True))

        attribution = ledger.attribution(configured_provider=None)
        self.assertEqual(attribution.actually_used_provider, "local")
        self.assertEqual(attribution.actually_used_model, "qwen2.5:1.5b")
        self.assertEqual(attribution.reported_provider, "local")
        self.assertFalse(attribution.deterministic_path)

    def test_a_failed_attempt_still_counts_as_a_call(self) -> None:
        """呼んだのだから 0 回ではない。**失敗を「無かったこと」にしない。**"""
        ledger = ModelCallLedger()
        ledger.record(ModelCall(provider="gemini", model="", ok=False))

        attribution = ledger.attribution(configured_provider=None)
        self.assertEqual(attribution.model_calls, 1)
        self.assertEqual(attribution.successful_model_calls, 0)
        self.assertFalse(attribution.deterministic_path)
        self.assertIsNone(attribution.actually_used_provider)
        self.assertEqual(attribution.reported_provider, UNRECORDED_PROVIDER)
        self.assertEqual(attribution.failed_providers, ("gemini",))

    def test_fallback_is_visible(self) -> None:
        ledger = ModelCallLedger()
        ledger.record(ModelCall(provider="gemini", model="", ok=False))
        ledger.record(ModelCall(provider="local", model="qwen", ok=True))

        attribution = ledger.attribution(configured_provider="gemini")
        self.assertTrue(attribution.fallback_used)
        self.assertEqual(attribution.attempted_providers, ("gemini", "local"))
        self.assertEqual(attribution.actually_used_provider, "local")
        self.assertEqual(attribution.configured_provider, "gemini")

    def test_the_dict_form_keeps_both_facts(self) -> None:
        payload = ModelCallLedger().attribution(configured_provider="gemini").to_dict()
        self.assertEqual(payload["configured_provider"], "gemini")
        self.assertIsNone(payload["actually_used_provider"])
        self.assertTrue(payload["deterministic_path"])


class TestRecordingIsOptionalButNeverOptimistic(unittest.TestCase):
    def test_recording_outside_a_context_is_a_no_op(self) -> None:
        self.assertIsNone(current_ledger())
        record_model_call(ModelCall(provider="gemini", model="", ok=True))  # 落ちない

    def test_a_routed_result_is_copied_attempt_by_attempt(self) -> None:
        with recording() as ledger:
            record_routed_result(_FakeRouted("local", (
                _FakeAttempt("gemini", ok=False),
                _FakeAttempt("local", ok=True, model="qwen"),
            )))
        self.assertEqual(ledger.model_calls, 2)
        self.assertEqual(ledger.attribution(configured_provider=None).actually_used_provider, "local")

    def test_a_result_without_attempts_still_counts_one_call(self) -> None:
        """**呼ばれた事実を落とさない。** 落とすと 0 回に見える。"""
        with recording() as ledger:
            record_routed_result(_FakeRouted("local", ()))
        self.assertEqual(ledger.model_calls, 1)

    def test_the_ledger_does_not_leak_past_its_block(self) -> None:
        with recording():
            pass
        self.assertIsNone(current_ledger())


@unittest.skipUnless(_FASTAPI_AVAILABLE, "fastapi/pydanticがインストールされていない環境ではskipする")
class TestZeroModelCallsDoNotNameAProvider(unittest.TestCase):
    """**本番経路での配線試験。**

    `provider` を明示したうえで、Model を 1 回も呼ばずに答えるターンを
    通す。応答が「指定した Provider が答えた」と言ってはならない。

    Model を呼ばない会話ターンは `ConversationEngine.step` を差し替えて
    作る。**Fast path だけでは 0 回にならない**——Fast path が BUILD を
    決めても、そのあと Cognitive Pipeline が Model を呼ぶからである
    （0 回になるのは Reuse-first が効いたときの姿である）。
    """

    def setUp(self) -> None:
        self.client = TestClient(app)

    @staticmethod
    def _ask_without_calling_any_model(_engine, _session, has_existing_tool=False):  # noqa: ANN001, ANN205, ARG004
        # class 属性へ差し替えるので、第1引数は Engine 自身になる。
        return ConversationStepResult(
            action=ConversationAction.ASK,
            need_model=NeedModel(
                problem="何を記録したいか分からない",
                known=(),
                unknowns=(),
                assumptions=(),
                confidence=0.2,
            ),
            question="何を記録しておきたいですか？",
            readiness=ConversationReadiness.INSUFFICIENT_INFORMATION,
        )

    def _turn(self, provider: str | None) -> dict:
        payload = {"message": "いろいろ記録して一覧で見返したい"}
        if provider is not None:
            payload["provider"] = provider
        with patch(
            "app.routers.ai.ConversationEngine.step",
            new=self._ask_without_calling_any_model,
        ):
            response = self.client.post("/api/v1/ai/converse", json=payload)
        self.assertEqual(response.status_code, 200, response.text)
        body = response.json()
        self.assertEqual(body["status"], "ask")
        return body

    def test_a_configured_provider_is_not_reported_as_used(self) -> None:
        """**これが TD104 の形そのものである。**

        指定は `"mock"`。Cloud を指定しないのは、この Process に鍵が無く
        `bind()` 自体が失敗して会話まで到達しないからである（その結合は
        別問題として TD105 に残した）。指定名が「使われた」に化けるか
        どうかは `"mock"` でも同じ形で見える。
        """
        body = self._turn("mock")

        self.assertNotEqual(
            body["provider"], "mock",
            "1回も呼んでいないのに「mockが答えた」と記録している",
        )
        self.assertEqual(body["provider"], NO_MODEL_CALL)
        self.assertFalse(
            body["simulated"],
            "**決定的な応答を「模擬出力」と呼んでいる。** Mockは呼ばれていない",
        )

    def test_the_attribution_keeps_both_facts(self) -> None:
        attribution = self._turn("mock")["attribution"]

        self.assertEqual(attribution["configured_provider"], "mock")
        self.assertIsNone(attribution["actually_used_provider"])
        self.assertEqual(attribution["model_calls"], 0)
        self.assertTrue(attribution["deterministic_path"])
        self.assertFalse(attribution["fallback_used"])

    def test_no_configured_provider_also_names_nobody(self) -> None:
        body = self._turn(None)
        self.assertEqual(body["provider"], NO_MODEL_CALL)
        self.assertIsNone(body["attribution"]["configured_provider"])


@unittest.skipUnless(_FASTAPI_AVAILABLE, "fastapi/pydanticがインストールされていない環境ではskipする")
class TestTheLedgerIsActuallyWiredOnTheProductionPath(unittest.TestCase):
    """**数えていなければ「0回」に見えてしまう。**

    Ledger を本番経路へ繋いだことを、実際に Model が呼ばれるターンで
    確かめる。ここが 0 のままなら、上の試験は「常に0回」を見ているだけの
    置物になる。
    """

    def setUp(self) -> None:
        self.client = TestClient(app)

    def test_a_real_turn_records_the_calls_it_made(self) -> None:
        response = self.client.post(
            "/api/v1/ai/converse",
            json={"message": "鍵の持ち出しを記録したい", "provider": "mock"},
        )
        self.assertEqual(response.status_code, 200, response.text)
        attribution = response.json()["attribution"]

        self.assertGreater(
            attribution["model_calls"], 0,
            "本番経路でModel呼び出しが1件も数えられていない（Ledgerが未配線）",
        )
        self.assertFalse(attribution["deterministic_path"])
        self.assertEqual(attribution["actually_used_provider"], "mock")
        self.assertEqual(attribution["configured_provider"], "mock")


if __name__ == "__main__":
    unittest.main()
