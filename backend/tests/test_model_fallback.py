"""同一Provider内のModel fallback(FORGE-ROADMAP R0.1、2026-08-17)。

---

## 何を直したテストか

CEOが実際に使ったところ、AI連携が失敗した。再現したら**6回中6回失敗**
していた。

    試行: [gemini(provider_server_error), local(local_resource_error)]

原因は3つ重なっていた。

1. **環境** — 既定Model(`gemini-flash-latest`)が混んでいた。同時刻の
   実測は `[200, 503, 503]`。同じ鍵で`gemini-flash-lite-latest`は
   `[200, 200, 200]`。Google自身が「一時的だ」と言う503である。
2. **設計** — §20「同じProviderを二度試さない」を、一時的な失敗にも
   当てていた。恒久的な失敗には正しいが、一時的な失敗に当てると
   **混雑がそのまま「AIが使えません」になる**。
3. **設計** — `ProviderDefinition.models`は「診断とBenchmarkのため」
   であり、Routingには使っていなかった。「別のModelなら通る」という
   事実が実行へ反映される経路が無かった。

## このファイルが守る不変条件

* 一時的な失敗なら、同じProviderの別Modelを試す
* **恒久的な失敗では試さない**(鍵が無いのにModelを変えても無意味)
* Providerの外から見た振る舞いは変わらない
  ——Circuit Breakerは「geminiが**全Modelで**失敗した」ときだけ数える
  (011 §1: 識別键は`provider_id`であってModelではない)
* 予算(011 §4)を食い破らない
"""

from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from app.ai.gateway.ai_errors import ErrorKind  # noqa: E402
from app.ai.gateway.ai_router import (  # noqa: E402
    AIRouter,
    ModelDescriptor,
    NoProviderAvailableError,
)
from app.ai.gateway.tasks import ForgeTask  # noqa: E402
from app.ai.foundation.model_choice import supports_model_choice  # noqa: E402

_TASK = ForgeTask.CONVERSATION_STEP
_SCHEMA = {"type": "object", "properties": {"ok": {"type": "boolean"}}}


class _FakeAdapter:
    """Model名で応答を変えるAdapter。

    `with_model`と`with_deadline`の両方を持つのは、本番のAdapterが
    どちらも持っているからである(片方だけのFakeで測ると、本番では
    通らない経路を「通った」と判定しうる)。
    """

    def __init__(self, working: set[str], *, model: str = "default", error: Exception | None = None):
        self.working = working
        self._model = model
        self.error = error or RuntimeError("Gemini APIがエラーを返しました(status=503): high demand")
        self.calls: list[str] = []

    @property
    def model(self) -> str:
        return self._model

    def with_model(self, model: str) -> "_FakeAdapter":
        clone = _FakeAdapter(self.working, model=model, error=self.error)
        clone.calls = self.calls  # 呼び出し記録は共有する
        return clone

    def with_deadline(self, seconds: float) -> "_FakeAdapter":
        return self

    def complete_structured(self, prompt: str, response_schema: dict) -> dict:
        self.calls.append(self._model)
        if self._model in self.working:
            return {"ok": True}
        raise self.error


def _router(adapter: object, *, provider: str = "gemini") -> AIRouter:
    return AIRouter(
        resolve=lambda name: adapter,
        catalog=(ModelDescriptor(provider=provider, is_local=False),),
        experience=None,  # このファイルの関心事ではない
    )


class TestATransientFailureTriesAnotherModel(unittest.TestCase):
    def test_the_default_model_is_tried_first(self) -> None:
        """**既定を飛ばさない。** 候補宣言があるからといって、今まで
        動いていたModelを使わなくなってはならない。"""
        adapter = _FakeAdapter({"default"})
        result = _router(adapter).generate(_TASK, "p", _SCHEMA)
        self.assertEqual(adapter.calls, ["default"])
        self.assertEqual(result.provider_used, "gemini")

    def test_a_503_moves_on_to_the_next_model(self) -> None:
        """実機で起きたことそのもの: 既定が503、次のModelは応答する。"""
        adapter = _FakeAdapter({"gemini-flash-lite-latest"})
        result = _router(adapter).generate(_TASK, "p", _SCHEMA)
        self.assertEqual(result.value, {"ok": True})
        self.assertEqual(
            adapter.calls[0], "default", "既定Modelを先に試していない。"
        )
        self.assertIn(
            "gemini-flash-lite-latest", adapter.calls,
            "既定が一時的に失敗しても、次のModelを試していない。"
            "候補が実質1つの環境では、これが無いと混雑がそのまま"
            "「AIが使えません」になる。",
        )

    def test_the_successful_model_is_the_one_reported(self) -> None:
        adapter = _FakeAdapter({"gemini-flash-lite-latest"})
        result = _router(adapter).generate(_TASK, "p", _SCHEMA)
        succeeded = [a for a in result.attempts if a.ok]
        self.assertEqual(succeeded[-1].model, "gemini-flash-lite-latest")

    def test_all_models_failing_is_still_a_provider_failure(self) -> None:
        adapter = _FakeAdapter(set())
        with self.assertRaises(NoProviderAvailableError) as raised:
            _router(adapter).generate(_TASK, "p", _SCHEMA)
        self.assertGreater(len(adapter.calls), 1, "1つも巡っていない。")
        # Providerとしては**1回**の失敗として見える(Model単位に割らない)。
        self.assertEqual(len(raised.exception.attempts), 1)


class TestAPermanentFailureDoesNotWasteTime(unittest.TestCase):
    """Modelを変えても直らない失敗で巡らないこと。

    巡ると、時間と(Cloudなら)枠を捨てるだけになる。
    """

    def test_an_auth_error_stops_at_the_first_model(self) -> None:
        adapter = _FakeAdapter(set(), error=RuntimeError("401 unauthorized: invalid api key"))
        with self.assertRaises(NoProviderAvailableError):
            _router(adapter).generate(_TASK, "p", _SCHEMA)
        self.assertEqual(
            adapter.calls, ["default"],
            "鍵が違うのにModelを変えて試している。鍵は同じなので直らない。",
        )

    def test_a_forge_side_schema_error_stops_at_the_first_model(self) -> None:
        adapter = _FakeAdapter(set(), error=RuntimeError("400 bad request: invalid schema"))
        with self.assertRaises(NoProviderAvailableError):
            _router(adapter).generate(_TASK, "p", _SCHEMA)
        self.assertEqual(adapter.calls, ["default"])

    def test_the_taxonomy_says_which_is_which(self) -> None:
        """区別の根拠は`ErrorKind`側にある(Routerに条件を散らさない)。"""
        for kind in (ErrorKind.PROVIDER_SERVER_ERROR, ErrorKind.TIMEOUT, ErrorKind.NETWORK):
            with self.subTest(kind=kind):
                self.assertTrue(kind.is_transient)
                self.assertTrue(kind.another_model_may_work)
        for kind in (ErrorKind.AUTH, ErrorKind.INVALID_REQUEST, ErrorKind.NOT_IMPLEMENTED):
            with self.subTest(kind=kind):
                self.assertFalse(kind.is_transient)
                self.assertFalse(kind.another_model_may_work)

    def test_a_dead_model_moves_on_but_is_not_called_transient(self) -> None:
        """`MODEL_UNAVAILABLE`は一時的ではないが、**別Modelなら通る**。

        実際に踏んだ形である——`gemini-2.0-flash`が404(提供終了)に
        なっても、`gemini-flash-latest`は動いていた。
        """
        self.assertFalse(ErrorKind.MODEL_UNAVAILABLE.is_transient)
        self.assertTrue(ErrorKind.MODEL_UNAVAILABLE.another_model_may_work)

    def test_quota_is_not_treated_as_transient(self) -> None:
        """枠切れ・流量制限は時間で回復するが、**1リクエストの中では
        待てない**。既存の`reset_at`/cooldownが担当する領分へ、
        二重に手を出さない。"""
        for kind in (ErrorKind.QUOTA_EXHAUSTED, ErrorKind.RATE_LIMITED):
            with self.subTest(kind=kind):
                self.assertFalse(kind.is_transient)


class TestQuotaScopeDecidesWhetherAnotherModelHelps(unittest.TestCase):
    """枠切れだけは`ErrorKind`では決まらない(R0.1)。

    枠がModel単位で切れるのか鍵単位で切れるのかは、**相手の課金設計**
    であってエラーの種類ではない。実機で読んだGeminiの429本文:

        "quotaId": "GenerateRequestsPerDayPerProjectPerModel-FreeTier"
        "quotaValue": 20

    Modelごとに1日20回である。ここで諦めると、まだ20回残っている
    別Modelを持っているのに「AIが使えません」と言うことになる。
    """

    _QUOTA = RuntimeError(
        "Gemini APIがエラーを返しました(status=429): "
        "You exceeded your current quota"
    )

    def test_gemini_is_declared_per_model_because_that_was_measured(self) -> None:
        from app.ai.gateway.provider_registry import QuotaScope, definition_for  # noqa: PLC0415

        self.assertIs(definition_for("gemini").quota_scope, QuotaScope.PER_MODEL)

    def test_a_per_model_quota_moves_on_to_another_model(self) -> None:
        adapter = _FakeAdapter({"gemini-flash-lite-latest"}, error=self._QUOTA)
        result = _router(adapter).generate(_TASK, "p", _SCHEMA)
        self.assertEqual(result.value, {"ok": True})
        self.assertGreater(
            len(adapter.calls), 1,
            "既定Modelの枠が切れただけで諦めている。枠はModel単位なので、"
            "別Modelにはまだ残っている。",
        )

    def test_an_unknown_quota_scope_does_not_gamble(self) -> None:
        """**分からないものを楽観側へ倒さない。**

        枠が鍵単位で切れる相手にModelを巡ると、確実に失敗する
        呼び出しを積むだけになる。

        判定そのものを直接見る。**Model候補が並んでいるProviderでしか
        差が出ない**ので、経路全体で測ろうとすると、候補が1つしか
        無いProviderでは「巡らなかった」が偶然成立してしまい、
        賭けを許しても落ちないテストになる(実際に一度そう書いて、
        配線を壊しても落ちないことを確認して書き直した)。
        """
        router = _router(_FakeAdapter(set()))
        # gemini は実測に基づき PER_MODEL を宣言しているので巡ってよい。
        self.assertTrue(
            router._another_model_may_work("gemini", ErrorKind.QUOTA_EXHAUSTED)  # noqa: SLF001
        )
        # 宣言が無い/UNKNOWN の相手では巡らない。
        for provider in ("local", "groq", "存在しないProvider"):
            with self.subTest(provider=provider):
                self.assertFalse(
                    router._another_model_may_work(  # noqa: SLF001
                        provider, ErrorKind.QUOTA_EXHAUSTED
                    ),
                    f"{provider} は枠の単位を宣言していないのに、別Modelへ賭けている。",
                )

    def test_a_declared_per_provider_quota_stops(self) -> None:
        """`PER_PROVIDER`と宣言した相手では、Modelを変えない。

        `UNKNOWN`と同じ結果になるが、**理由が違う**——片方は
        「分からないから賭けない」、もう片方は「同じ枠だと分かって
        いる」。値として区別できることを固定しておく。
        """
        from dataclasses import replace  # noqa: PLC0415
        from unittest.mock import patch  # noqa: PLC0415

        from app.ai.gateway.provider_registry import QuotaScope, definition_for  # noqa: PLC0415

        shared = replace(definition_for("gemini"), quota_scope=QuotaScope.PER_PROVIDER)
        adapter = _FakeAdapter({"gemini-flash-lite-latest"}, error=self._QUOTA)
        with patch("app.ai.gateway.ai_router.definition_for", return_value=shared):
            with self.assertRaises(NoProviderAvailableError):
                _router(adapter).generate(_TASK, "p", _SCHEMA)
        self.assertEqual(
            adapter.calls, ["default"],
            "枠が鍵単位だと分かっているのにModelを巡り、確実に失敗する"
            "呼び出しを積んでいる。",
        )


class TestTheMessageMatchesWhatTheUserShouldDo(unittest.TestCase):
    """枠切れと障害を同じ文言で案内しない(R0.1)。

    以前はどちらも「しばらく待ってからもう一度お試しください」だった。
    実測したGemini無料枠は**1日20回/Model**なので、枠を使い切った
    利用者が5分後に再試行しても同じ結果になる。**打つ手が違うものを
    同じ文言で案内しない。**
    """

    def _error(self, kind: ErrorKind) -> NoProviderAvailableError:
        from app.ai.gateway.ai_router import RouteAttempt  # noqa: PLC0415

        return NoProviderAvailableError(
            _TASK, (RouteAttempt(provider="gemini", ok=False, latency_ms=1.0, error_kind=kind),), ()
        )

    def test_quota_exhaustion_is_recognised(self) -> None:
        self.assertTrue(self._error(ErrorKind.QUOTA_EXHAUSTED).is_quota_exhaustion)
        self.assertFalse(self._error(ErrorKind.PROVIDER_SERVER_ERROR).is_quota_exhaustion)

    def test_no_attempt_at_all_is_not_called_quota_exhaustion(self) -> None:
        """呼んでもいないものを枠切れとは言わない。"""
        self.assertFalse(NoProviderAvailableError(_TASK, (), ("設定が無い",)).is_quota_exhaustion)

    def test_the_two_messages_differ(self) -> None:
        from app.routers.ai import _no_provider_message  # noqa: PLC0415

        quota = _no_provider_message(self._error(ErrorKind.QUOTA_EXHAUSTED))
        outage = _no_provider_message(self._error(ErrorKind.PROVIDER_SERVER_ERROR))
        self.assertNotEqual(quota, outage)
        self.assertNotIn(
            "しばらく", quota,
            "1日単位の枠切れに「しばらく待って」と案内している。5分後も同じ結果になる。",
        )
        self.assertIn("しばらく", outage)

    def test_neither_message_names_a_provider(self) -> None:
        """FORGE-PROVIDER-INDEPENDENT-UI(2026-09-02)。

        以前この文言は「別のAI Providerを設定してください」と書き、
        `(内訳: {exc})` で Provider 名の一覧まで見せていた。
        **利用者に Provider 選択を担当させない**(Constitution §4・§9)。
        """
        from app.ai.runtime.provider_independent_messages import (  # noqa: PLC0415
            mentions_provider_identity,
        )
        from app.routers.ai import _no_provider_message  # noqa: PLC0415

        for kind in (ErrorKind.QUOTA_EXHAUSTED, ErrorKind.PROVIDER_SERVER_ERROR):
            message = _no_provider_message(self._error(kind))
            self.assertFalse(
                mentions_provider_identity(message),
                f"利用者向け文言に Provider の身元が出ている: {message}",
            )


class TestProviderIdentityIsUnchanged(unittest.TestCase):
    """011 §1を壊していないこと。

    Modelを増やしても、Quota・Circuit Breaker・Benchmark・Experienceの
    識別键は`provider_id`のままでなければならない。
    """

    def test_a_recovered_provider_is_recorded_as_a_success(self) -> None:
        """別Modelで成功したなら、Providerは**成功**である。
        失敗を数えると、実際には応答しているProviderのCircuit Breakerが
        じわじわ開く。"""
        adapter = _FakeAdapter({"gemini-flash-lite-latest"})
        router = _router(adapter)
        router.generate(_TASK, "p", _SCHEMA)
        state = router.states.get("gemini")
        self.assertEqual(state.consecutive_failures, 0)

    def test_the_experience_record_keys_on_the_provider_not_the_model(self) -> None:
        from app.ai.gateway.learning_foundation import ExperienceStore  # noqa: PLC0415

        store = ExperienceStore()
        adapter = _FakeAdapter({"gemini-flash-lite-latest"})
        AIRouter(
            resolve=lambda name: adapter,
            catalog=(ModelDescriptor(provider="gemini", is_local=False),),
            experience=store,
        ).generate(_TASK, "p", _SCHEMA)
        records = store.all_records()
        self.assertEqual([r.provider for r in records], ["gemini"])
        self.assertEqual(records[0].model, "gemini-flash-lite-latest")


class TestAdaptersThatCannotSwitchAreUnaffected(unittest.TestCase):
    """`with_model`を持たないAdapterは**従来どおり**動くこと。

    `LLMAdapter`の契約は変えていない(`deadline.py`と同じ方針)。
    """

    def test_an_adapter_without_with_model_is_called_once(self) -> None:
        class _Plain:
            model = "fixed"

            def __init__(self) -> None:
                self.calls = 0

            def complete_structured(self, prompt: str, response_schema: dict) -> dict:
                self.calls += 1
                raise RuntimeError("503 high demand")

        adapter = _Plain()
        self.assertFalse(supports_model_choice(adapter))
        with self.assertRaises(NoProviderAvailableError):
            _router(adapter).generate(_TASK, "p", _SCHEMA)
        self.assertEqual(adapter.calls, 1)


class TestTheRegistryOnlyClaimsModelsThatWereActuallyCalled(unittest.TestCase):
    """§12「公称値を大量に固定しない」。

    ここに書いてよいのは**実際に呼んで200が返ったModelだけ**である。
    ドキュメントに載っていたから書く、をやると、巡る時間が増える
    だけで一度も成功しない列ができる。
    """

    def test_the_retired_model_is_gone(self) -> None:
        from app.ai.gateway.provider_registry import definition_for  # noqa: PLC0415

        gemini = definition_for("gemini")
        self.assertIsNotNone(gemini)
        self.assertNotIn(
            "gemini-2.0-flash", gemini.models,
            "2026-08-17時点で404(提供終了)を実測したModelが残っている。",
        )

    def test_no_provider_lists_a_model_twice(self) -> None:
        from app.ai.gateway.provider_registry import provider_registry  # noqa: PLC0415

        for definition in provider_registry():
            with self.subTest(provider=definition.provider_id):
                self.assertEqual(
                    len(definition.models), len(set(definition.models)),
                    "同じModelを二度試すことになる。",
                )


if __name__ == "__main__":
    unittest.main()
