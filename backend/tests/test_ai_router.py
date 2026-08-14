"""Quota-Aware AI Router のテスト
(FORGE-QUOTA-AWARE-AI-ROUTER-008 §39・§40、2026-08-13新設)。

**API Keyを1つも必要としない。** Provider失敗の種類・状態遷移・
Circuit Breaker・予算打ち切りは、決定的なTest Doubleで完全に検証できる
(§39)。実APIに繋いで初めて分かることは別にあるが(残リスクは
`FORGE-QUOTA-AWARE-AI-ROUTER-ARCH-REVIEW.md` §17)、Router Logic自体は
ここで証明できる。

§40の12ケースをすべて含む。
"""

from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from app.ai.gateway.ai_errors import ErrorKind, ProviderError, classify_exception  # noqa: E402
from app.ai.gateway.ai_router import (  # noqa: E402
    AIRouter,
    ModelDescriptor,
    NoProviderAvailableError,
    Sensitivity,
    TASK_PROFILES,
    TaskProfile,
    default_catalog,
)
from app.ai.gateway.tasks import ForgeTask  # noqa: E402
from app.ai.gateway.provider_state import Availability, ProviderStateStore  # noqa: E402

_TASK = ForgeTask.CONVERSATION_STEP
_SCHEMA = {"type": "object", "properties": {"x": {"type": "string"}}}


class _FakeAdapter:
    """決定的なTest Double。`behaviour`で毎回の挙動を指定する。"""

    def __init__(self, *behaviours, latency_ms: float = 1.0) -> None:
        self._behaviours = list(behaviours)
        self._index = 0
        self.calls = 0
        self.latency_ms = latency_ms
        self.deadline_seconds: float | None = None

    def with_deadline(self, seconds: float) -> "_FakeAdapter":
        """`SupportsDeadline`(FORGE-AI-FOUNDATION-011 §4)。

        本番のAdapter(`OpenAICompatibleAdapter`・`GeminiProvider`)は
        いずれも締め切りを受け取れるので、Test Doubleも同じ形にする。
        受け取れないDoubleにすると、`local`(公称120秒)が既定予算
        45秒に収まらないという**本番では起きない理由**でテストが
        落ちる——Doubleが本番より不自由だと、測りたいものが測れない。
        """
        self.deadline_seconds = seconds
        return self

    def complete_structured(self, prompt: str, response_schema: dict) -> dict:
        self.calls += 1
        behaviour = self._behaviours[min(self._index, len(self._behaviours) - 1)]
        self._index += 1
        if isinstance(behaviour, BaseException):
            raise behaviour
        return behaviour


class _Clock:
    """時間を手で進められる時計。cooldownの検証に使う
    (`sleep`でテストを遅くしない)。"""

    def __init__(self) -> None:
        self.value = 1000.0

    def __call__(self) -> float:
        return self.value

    def advance(self, seconds: float) -> None:
        self.value += seconds


def _router(adapters: dict, catalog, *, clock: _Clock | None = None) -> AIRouter:
    clock = clock or _Clock()
    return AIRouter(
        resolve=lambda name: adapters[name],
        catalog=catalog,
        state_store=ProviderStateStore(now=clock),
        now=clock,
        monotonic=clock,
    )


_CLOUD_A = ModelDescriptor(provider="cloud_a", is_local=False)
_CLOUD_B = ModelDescriptor(provider="cloud_b", is_local=False)
_LOCAL = ModelDescriptor(provider="local", is_local=True)


class TestCase1_PreferredAvailable(unittest.TestCase):
    def test_uses_the_first_eligible_provider(self) -> None:
        a = _FakeAdapter({"x": "a"})
        b = _FakeAdapter({"x": "b"})
        router = _router({"cloud_a": a, "cloud_b": b}, (_CLOUD_A, _CLOUD_B))

        result = router.generate(_TASK, "p", _SCHEMA)

        self.assertEqual(result.provider_used, "cloud_a")
        self.assertFalse(result.used_fallback)
        self.assertEqual(b.calls, 0, "1つ目が成功したのに2つ目を呼んでいる")

    def test_declared_order_is_respected(self) -> None:
        """順序は`catalog`の宣言順に従う。

        **Localを無条件で優先しない。** §5は「固定ルールで決め打ちせず
        Benchmarkで決定する」と明示しており、Benchmarkが無い現状で
        Localを先に出すのは、測っていない品質を賭けてQuotaを節約して
        いるだけになる(実装中に方針を変えた点、`_order()`参照)。
        """
        local = _FakeAdapter({"x": "local"})
        cloud = _FakeAdapter({"x": "cloud"})
        router = _router({"local": local, "cloud_a": cloud}, (_CLOUD_A, _LOCAL))

        self.assertEqual(router.generate(_TASK, "p", _SCHEMA).provider_used, "cloud_a")
        self.assertEqual(local.calls, 0)


class TestCase2_QuotaFallback(unittest.TestCase):
    def test_quota_exhausted_falls_back_to_next_provider(self) -> None:
        a = _FakeAdapter(RuntimeError("429 You exceeded your current quota"))
        b = _FakeAdapter({"x": "b"})
        router = _router({"cloud_a": a, "cloud_b": b}, (_CLOUD_A, _CLOUD_B))

        result = router.generate(_TASK, "p", _SCHEMA)

        self.assertEqual(result.provider_used, "cloud_b")
        self.assertTrue(result.used_fallback)
        self.assertEqual(result.attempts[0].error_kind, ErrorKind.QUOTA_EXHAUSTED)


class TestCase3_QuotaStateIsRemembered(unittest.TestCase):
    def test_exhausted_provider_is_not_retried_in_later_calls(self) -> None:
        """§40 Case 3。枠切れを学習し、**同じTask内でも次のTaskでも**
        投げ続けない。投げ続けるとQuotaを無駄にし、latencyも延びる。"""
        a = _FakeAdapter(RuntimeError("resource_exhausted: quota"))
        b = _FakeAdapter({"x": "b"})
        router = _router({"cloud_a": a, "cloud_b": b}, (_CLOUD_A, _CLOUD_B))

        router.generate(_TASK, "p", _SCHEMA)
        calls_after_first = a.calls
        router.generate(_TASK, "p", _SCHEMA)

        self.assertEqual(a.calls, calls_after_first, "枠切れProviderへ再び投げている")
        self.assertIs(
            router.states.get("cloud_a").availability, Availability.QUOTA_EXHAUSTED
        )

    def test_quota_recovers_after_the_reset_window(self) -> None:
        clock = _Clock()
        a = _FakeAdapter(RuntimeError("quota exceeded"), {"x": "a"})
        b = _FakeAdapter({"x": "b"})
        router = _router({"cloud_a": a, "cloud_b": b}, (_CLOUD_A, _CLOUD_B), clock=clock)

        router.generate(_TASK, "p", _SCHEMA)
        clock.advance(3601)  # 既定のquota window を超える
        result = router.generate(_TASK, "p", _SCHEMA)

        self.assertEqual(result.provider_used, "cloud_a", "枠が戻っても復帰していない")


class TestCase4_TimeoutFallback(unittest.TestCase):
    def test_timeout_falls_back(self) -> None:
        a = _FakeAdapter(TimeoutError("deadline exceeded"))
        b = _FakeAdapter({"x": "b"})
        router = _router({"cloud_a": a, "cloud_b": b}, (_CLOUD_A, _CLOUD_B))

        result = router.generate(_TASK, "p", _SCHEMA)

        self.assertEqual(result.provider_used, "cloud_b")
        self.assertEqual(result.attempts[0].error_kind, ErrorKind.TIMEOUT)

    def test_latency_budget_stops_the_chain(self) -> None:
        """§28。「1 Provider 60秒 × 4回」を構造的に防ぐ。"""
        clock = _Clock()

        class _SlowAdapter:
            def complete_structured(self, prompt, schema):
                clock.advance(30)  # 30秒消費してから失敗
                raise TimeoutError("slow")

        adapters = {"cloud_a": _SlowAdapter(), "cloud_b": _SlowAdapter(), "local": _SlowAdapter()}
        TASK_PROFILES[_TASK] = TaskProfile(task=_TASK, latency_budget_ms=45_000.0, max_attempts=5)
        try:
            router = _router(adapters, (_CLOUD_A, _CLOUD_B, _LOCAL), clock=clock)
            with self.assertRaises(NoProviderAvailableError) as caught:
                router.generate(_TASK, "p", _SCHEMA)
            self.assertLessEqual(
                len(caught.exception.attempts), 2,
                "時間予算を超えても試し続けている",
            )
        finally:
            TASK_PROFILES.pop(_TASK, None)


class TestCase5_AuthError(unittest.TestCase):
    def test_auth_error_disables_the_provider_and_falls_back(self) -> None:
        a = _FakeAdapter(RuntimeError("401 Unauthorized: invalid api key"))
        b = _FakeAdapter({"x": "b"})
        router = _router({"cloud_a": a, "cloud_b": b}, (_CLOUD_A, _CLOUD_B))

        result = router.generate(_TASK, "p", _SCHEMA)

        self.assertEqual(result.provider_used, "cloud_b")
        state = router.states.get("cloud_a")
        self.assertIs(state.availability, Availability.DISABLED)
        self.assertIs(state.last_error, ErrorKind.AUTH, "設定エラーとして記録されていない")

    def test_disabled_provider_stays_out_even_after_time_passes(self) -> None:
        """認証エラーは時間では直らない。設定を直すまで除外し続ける。"""
        clock = _Clock()
        a = _FakeAdapter(RuntimeError("403 permission denied"))
        b = _FakeAdapter({"x": "b"})
        router = _router({"cloud_a": a, "cloud_b": b}, (_CLOUD_A, _CLOUD_B), clock=clock)

        router.generate(_TASK, "p", _SCHEMA)
        calls = a.calls
        clock.advance(100_000)
        router.generate(_TASK, "p", _SCHEMA)

        self.assertEqual(a.calls, calls)


class TestCase6_AllCloudDownLocalUp(unittest.TestCase):
    def test_falls_back_to_local(self) -> None:
        a = _FakeAdapter(RuntimeError("503 service unavailable"))
        b = _FakeAdapter(RuntimeError("quota exceeded"))
        local = _FakeAdapter({"x": "local"})
        router = _router(
            {"cloud_a": a, "cloud_b": b, "local": local}, (_CLOUD_A, _CLOUD_B, _LOCAL)
        )

        result = router.generate(_TASK, "p", _SCHEMA)

        # Cloudを順に試して両方失敗し、最後にLocalへ落ちたこと。
        self.assertEqual(result.provider_used, "local")
        self.assertEqual([x.provider for x in result.attempts], ["cloud_a", "cloud_b", "local"])
        self.assertEqual(a.calls, 1)
        self.assertEqual(b.calls, 1)


class TestCase7_NothingAvailable(unittest.TestCase):
    def test_raises_instead_of_fabricating_a_result(self) -> None:
        """§7 / §33。**偽のBUILDをしない**。使えるものが無ければ、
        無いと言う。ここでMockへ落ちる経路があってはならない。"""
        a = _FakeAdapter(RuntimeError("503"))
        local = _FakeAdapter(RuntimeError("connection refused"))
        router = _router({"cloud_a": a, "local": local}, (_CLOUD_A, _LOCAL))

        with self.assertRaises(NoProviderAvailableError) as caught:
            router.generate(_TASK, "p", _SCHEMA)

        self.assertIn("利用可能なProviderがありません", str(caught.exception))

    def test_failure_message_says_why(self) -> None:
        """「使えません」だけでは調査できない。理由を持たせる。"""
        a = _FakeAdapter(RuntimeError("429 quota exceeded"))
        router = _router({"cloud_a": a}, (_CLOUD_A,))
        router.generate.__self__  # noqa: B018 - 明示のためのアクセス
        with self.assertRaises(NoProviderAvailableError):
            router.generate(_TASK, "p", _SCHEMA)
        with self.assertRaises(NoProviderAvailableError) as caught:
            router.generate(_TASK, "p", _SCHEMA)
        self.assertIn("利用枠切れ", str(caught.exception))


class TestCase8_StructuredOutputRequirement(unittest.TestCase):
    def test_provider_without_structured_output_is_excluded(self) -> None:
        """§17。厳密なschemaが要るTaskで、対応しないModelを候補から外す。"""
        weak = ModelDescriptor(provider="weak", is_local=False, supports_structured_output=False)
        strong = ModelDescriptor(provider="strong", is_local=False)
        weak_adapter = _FakeAdapter({"x": "weak"})
        router = _router(
            {"weak": weak_adapter, "strong": _FakeAdapter({"x": "strong"})}, (weak, strong)
        )

        result = router.generate(_TASK, "p", _SCHEMA)

        self.assertEqual(result.provider_used, "strong")
        self.assertEqual(weak_adapter.calls, 0)

    def test_non_dict_response_is_treated_as_a_failure(self) -> None:
        """構造化出力が壊れていたら、成功として返さない。"""
        broken = _FakeAdapter("これはdictではない")
        good = _FakeAdapter({"x": "ok"})
        router = _router({"cloud_a": broken, "cloud_b": good}, (_CLOUD_A, _CLOUD_B))

        result = router.generate(_TASK, "p", _SCHEMA)

        self.assertEqual(result.provider_used, "cloud_b")
        self.assertEqual(
            result.attempts[0].error_kind, ErrorKind.STRUCTURED_OUTPUT_FAILURE
        )


class TestCase9_CircuitBreaker(unittest.TestCase):
    def test_opens_after_repeated_server_errors(self) -> None:
        clock = _Clock()
        a = _FakeAdapter(RuntimeError("500 internal server error"))
        b = _FakeAdapter({"x": "b"})
        router = _router({"cloud_a": a, "cloud_b": b}, (_CLOUD_A, _CLOUD_B), clock=clock)

        for _ in range(3):
            router.generate(_TASK, "p", _SCHEMA)

        self.assertIs(router.states.get("cloud_a").availability, Availability.CIRCUIT_OPEN)
        calls = a.calls
        router.generate(_TASK, "p", _SCHEMA)
        self.assertEqual(a.calls, calls, "OPENなのに投げ続けている")


class TestCase10_CircuitRecovery(unittest.TestCase):
    def test_recovers_after_cooldown(self) -> None:
        clock = _Clock()
        a = _FakeAdapter(
            RuntimeError("500"), RuntimeError("500"), RuntimeError("500"), {"x": "recovered"}
        )
        b = _FakeAdapter({"x": "b"})
        router = _router({"cloud_a": a, "cloud_b": b}, (_CLOUD_A, _CLOUD_B), clock=clock)

        for _ in range(3):
            router.generate(_TASK, "p", _SCHEMA)
        self.assertIs(router.states.get("cloud_a").availability, Availability.CIRCUIT_OPEN)

        clock.advance(31)  # cooldown経過
        result = router.generate(_TASK, "p", _SCHEMA)

        self.assertEqual(result.provider_used, "cloud_a", "cooldown後に復帰していない")
        self.assertIs(router.states.get("cloud_a").availability, Availability.AVAILABLE)


class TestCase11_InvalidRequestDoesNotTour(unittest.TestCase):
    def test_invalid_request_stops_immediately(self) -> None:
        """§19 / §11。Forge側のschema誤りは、Providerを変えても直らない。
        巡回するとQuotaを捨てるだけで、原因も分からないままになる。"""
        a = _FakeAdapter(RuntimeError("400 Bad Request: invalid schema"))
        b = _FakeAdapter({"x": "b"})
        c = _FakeAdapter({"x": "c"})
        router = _router(
            {"cloud_a": a, "cloud_b": b, "local": c}, (_CLOUD_A, _CLOUD_B, _LOCAL)
        )

        with self.assertRaises(NoProviderAvailableError) as caught:
            router.generate(_TASK, "p", _SCHEMA)

        self.assertEqual(len(caught.exception.attempts), 1, "他Providerを巡回している")
        self.assertEqual(b.calls, 0)

    def test_invalid_request_does_not_damage_provider_health(self) -> None:
        """Forge側の誤りでProviderを不健康扱いにしない。"""
        a = _FakeAdapter(RuntimeError("invalid_request"))
        router = _router({"cloud_a": a}, (_CLOUD_A,))
        with self.assertRaises(NoProviderAvailableError):
            router.generate(_TASK, "p", _SCHEMA)
        self.assertIs(router.states.get("cloud_a").availability, Availability.AVAILABLE)


class TestCase12_MockExcluded(unittest.TestCase):
    def test_mock_is_never_chosen_automatically(self) -> None:
        """§22。全Cloud失敗 → Mock → 偽のTool、という経路を構造的に塞ぐ。"""
        mock = ModelDescriptor(provider="mock", is_local=True, test_only=True)
        mock_adapter = _FakeAdapter({"x": "mock_result"})
        a = _FakeAdapter(RuntimeError("503"))
        router = _router({"mock": mock_adapter, "cloud_a": a}, (mock, _CLOUD_A))

        with self.assertRaises(NoProviderAvailableError):
            router.generate(_TASK, "p", _SCHEMA)

        self.assertEqual(mock_adapter.calls, 0, "Mockが自動Routingで選ばれた")

    def test_mock_is_available_when_explicitly_requested(self) -> None:
        """明示要求は「テストモード」。既存のHTTP契約を壊さない。"""
        mock = ModelDescriptor(provider="mock", is_local=True, test_only=True)
        mock_adapter = _FakeAdapter({"x": "mock_result"})
        router = _router({"mock": mock_adapter}, (mock,))

        result = router.generate(_TASK, "p", _SCHEMA, provider="mock")

        self.assertEqual(result.provider_used, "mock")


class TestNoInfiniteRetry(unittest.TestCase):
    """§20。同じProviderを二度試さない・試行上限を守る。"""

    def test_same_provider_is_not_attempted_twice(self) -> None:
        a = _FakeAdapter(RuntimeError("503"))
        router = _router({"cloud_a": a}, (_CLOUD_A, _CLOUD_A))
        with self.assertRaises(NoProviderAvailableError) as caught:
            router.generate(_TASK, "p", _SCHEMA)
        self.assertEqual(len(caught.exception.attempts), 1)

    def test_attempt_limit_is_respected(self) -> None:
        adapters = {f"p{i}": _FakeAdapter(RuntimeError("503")) for i in range(6)}
        catalog = tuple(ModelDescriptor(provider=f"p{i}", is_local=False) for i in range(6))
        router = _router(adapters, catalog)
        with self.assertRaises(NoProviderAvailableError) as caught:
            router.generate(_TASK, "p", _SCHEMA)
        self.assertLessEqual(len(caught.exception.attempts), 3)


class TestSensitivityBoundary(unittest.TestCase):
    """§25。現状の値は1つだけだが、境界が構造として効くこと。"""

    def test_local_only_task_never_selects_a_cloud_provider(self) -> None:
        TASK_PROFILES[_TASK] = TaskProfile(task=_TASK, sensitivity=Sensitivity.LOCAL_ONLY)
        try:
            cloud = _FakeAdapter({"x": "cloud"})
            local = _FakeAdapter({"x": "local"})
            router = _router({"cloud_a": cloud, "local": local}, (_CLOUD_A, _LOCAL))
            result = router.generate(_TASK, "p", _SCHEMA)
            self.assertEqual(result.provider_used, "local")
            self.assertEqual(cloud.calls, 0, "外部送信不可のTaskでCloudを呼んだ")
        finally:
            TASK_PROFILES.pop(_TASK, None)


class TestErrorClassification(unittest.TestCase):
    def test_known_shapes(self) -> None:
        cases = {
            "429 You exceeded your current quota": ErrorKind.QUOTA_EXHAUSTED,
            "Rate limit reached for requests": ErrorKind.RATE_LIMITED,
            "401 Unauthorized": ErrorKind.AUTH,
            "model not found: gemini-x": ErrorKind.MODEL_UNAVAILABLE,
            "400 Bad Request": ErrorKind.INVALID_REQUEST,
            "503 Service Unavailable": ErrorKind.PROVIDER_SERVER_ERROR,
        }
        for message, expected in cases.items():
            with self.subTest(message=message):
                self.assertIs(classify_exception(RuntimeError(message), "p").kind, expected)

    def test_types_win_over_message_matching(self) -> None:
        self.assertIs(classify_exception(TimeoutError("x"), "p").kind, ErrorKind.TIMEOUT)
        self.assertIs(
            classify_exception(NotImplementedError("stub"), "p").kind, ErrorKind.NOT_IMPLEMENTED
        )

    def test_unknown_is_safe_to_fall_back(self) -> None:
        """分類できなかったものは、安全側(fallback可)に倒す。
        ただし**分類できていないこと自体は検出されない**——残リスク。"""
        kind = classify_exception(RuntimeError("何か想定外"), "p").kind
        self.assertIs(kind, ErrorKind.UNKNOWN)
        self.assertTrue(kind.should_try_other_providers)

    def test_already_classified_errors_pass_through(self) -> None:
        original = ProviderError(ErrorKind.QUOTA_EXHAUSTED, "p", "枠切れ")
        self.assertIs(classify_exception(original, "p"), original)


class TestDefaultCatalogFollowsTheEnvironment(unittest.TestCase):
    """FORGE-AI-FOUNDATION-010 Phase Bで見つけた実バグの回帰テスト。

    Catalogが固定リストだったため、運用者が`FORGE_DEFAULT_PROVIDER`で
    Providerを指定していてもRouterはそれを読まず、実機で
    **`simulated: true`と返しながら実Geminiを呼んでいた**。
    """

    def setUp(self) -> None:
        self._saved = {
            key: os.environ.get(key)
            for key in ("FORGE_DEFAULT_PROVIDER", "GEMINI_API_KEY")
        }

    def tearDown(self) -> None:
        for key, value in self._saved.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    def _set(self, **env: str) -> None:
        for key in ("FORGE_DEFAULT_PROVIDER", "GEMINI_API_KEY"):
            os.environ.pop(key, None)
        os.environ.update(env)

    def test_an_operator_pin_is_the_only_candidate(self) -> None:
        """運用者が名指ししたら、Routerはそれ以外を候補にしない。

        鍵があっても**Geminiへは行かない**——これが実際に起きていた
        「指定を無視して外部Cloudへ送る」の再発防止である。
        """
        self._set(FORGE_DEFAULT_PROVIDER="mock", GEMINI_API_KEY="dummy-value-not-a-real-key")
        self.assertEqual([m.provider for m in default_catalog()], ["mock"])

    def test_a_pinned_mock_is_selectable(self) -> None:
        """名指しされたMockは`test_only`を解かれる。

        「黙って選ばれない」(§22)のであって、「名指しでも使えない」
        のではない。鍵の無い開発環境でForgeが起動しなくなる。
        """
        self._set(FORGE_DEFAULT_PROVIDER="mock")
        self.assertFalse(default_catalog()[0].test_only)

    def test_gemini_is_not_a_candidate_without_a_key(self) -> None:
        """必ず認証エラーになる候補を並べない(試行予算の無駄)。"""
        self._set()
        self.assertNotIn("gemini", [m.provider for m in default_catalog()])

    def test_gemini_leads_when_a_key_is_present(self) -> None:
        self._set(GEMINI_API_KEY="dummy-value-not-a-real-key")
        self.assertEqual(default_catalog()[0].provider, "gemini")

    def test_mock_is_never_auto_selected_without_a_pin(self) -> None:
        """Catalogには居るが`test_only`。全Cloud失敗 → Mock → 偽のTool、
        という経路を構造で塞ぐ(§22)。"""
        self._set()
        mock = [m for m in default_catalog() if m.provider == "mock"]
        self.assertEqual(len(mock), 1)
        self.assertTrue(mock[0].test_only)

    def test_no_key_and_no_pin_leaves_nothing_auto_selectable_but_local(self) -> None:
        """鍵もpinも無い環境の候補は`local`だけになる。

        Localが動いていなければ`NoProviderAvailableError`になる
        ——**それが正しい失敗**であって、Mockで偽のToolを作らない。
        """
        self._set()
        auto = [m.provider for m in default_catalog() if not m.test_only]
        self.assertEqual(auto, ["local"])

    def test_an_unknown_pinned_name_is_treated_as_cloud(self) -> None:
        """知らない名前をLocalと決めつけない。`LOCAL_ONLY`のTaskへ
        誤って載せる方が、候補を1つ失うより悪い。"""
        self._set(FORGE_DEFAULT_PROVIDER="some-new-provider")
        descriptor = default_catalog()[0]
        self.assertEqual(descriptor.provider, "some-new-provider")
        self.assertFalse(descriptor.is_local)


if __name__ == "__main__":
    unittest.main()
