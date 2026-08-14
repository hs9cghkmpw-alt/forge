"""Hard Latency Budget(FORGE-AI-FOUNDATION-011 §4、2026-08-14)。

指示書の要求をそのまま引く:

>     budget = 45 sec
>     Provider A = 30 sec failure
>     Provider B
>
> の場合、Provider Bへ使えるのは残り約15秒であり、
> 新たに60秒待ってはいけません。

---

## 直した問題

`TaskProfile.latency_budget_ms`は既定45秒だが、Providerのtimeoutは
Cloud 60秒・Local 120秒だった。Routerは**呼ぶ前に**
`elapsed >= budget`を見るだけだったので、

    elapsed = 0 → 予算内と判定 → Provider呼び出し開始 → 120秒待つ

が成立した。**45秒という宣言が、実行を何も拘束していなかった。**

fallback後はさらに悪い。1つ目が30秒使っても2つ目は自分のtimeoutで
走るので、合計90秒になりうる。

## 直し方

Task全体の残り時間を、**実際にHTTPを叩く層まで届ける**。
`LLMAdapter`の契約は変えず、任意のCapability
(`SupportsDeadline.with_deadline()`)として足した——契約へ引数を
足すと全実装とすべてのTest Doubleが同時に壊れるが、deadlineを
扱えるのはHTTPを張る一部のAdapterだけである。

締め切りを受け取れないAdapterは、Registryの
`nominal_timeout_seconds`と残り予算を比べ、**入りきらないと
分かっている試行は始めない**。
"""

from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from app.ai.foundation.deadline import apply_deadline, supports_deadline  # noqa: E402
from app.ai.foundation.openai_compatible import OpenAICompatibleAdapter  # noqa: E402
from app.ai.foundation.providers import GeminiProvider, MockLLMAdapter  # noqa: E402
from app.ai.gateway.ai_router import (  # noqa: E402
    AIRouter,
    ModelDescriptor,
    NoProviderAvailableError,
    TASK_PROFILES,
    TaskProfile,
)
from app.ai.gateway.tasks import ForgeTask  # noqa: E402

_TASK = ForgeTask.CONVERSATION_STEP
_SCHEMA = {"type": "object", "properties": {"x": {"type": "string"}}}


class _StopClock:
    """手で進める時計。`sleep`でテストを遅くしない。"""

    def __init__(self) -> None:
        self.seconds = 0.0

    def __call__(self) -> float:
        return self.seconds

    def advance(self, seconds: float) -> None:
        self.seconds += seconds


class _TimedAdapter:
    """呼ばれると時計を進めるAdapter。渡された締め切りを記録する。"""

    def __init__(self, clock: _StopClock, *, takes: float, result=None) -> None:
        self._clock = clock
        self._takes = takes
        self._result = result
        self.deadlines: list[float] = []

    def with_deadline(self, seconds: float) -> "_TimedAdapter":
        clone = _TimedAdapter(self._clock, takes=self._takes, result=self._result)
        clone.deadlines = self.deadlines
        self.deadlines.append(seconds)
        return clone

    def complete_structured(self, prompt: str, response_schema: dict) -> dict:
        self._clock.advance(self._takes)
        if isinstance(self._result, BaseException):
            raise self._result
        if self._result is None:
            raise RuntimeError("503 service unavailable")
        return self._result


class _DeadlineBlindAdapter:
    """締め切りを受け取れないAdapter(`with_deadline`を持たない)。"""

    def __init__(self, result=None) -> None:
        self._result = result
        self.calls = 0

    def complete_structured(self, prompt: str, response_schema: dict) -> dict:
        self.calls += 1
        if self._result is None:
            raise RuntimeError("503 service unavailable")
        return self._result


def _router(adapters: dict, order: tuple[str, ...], clock: _StopClock) -> AIRouter:
    return AIRouter(
        resolve=lambda name: adapters[name],
        catalog=tuple(
            ModelDescriptor(provider=name, is_local=False) for name in order
        ),
        now=lambda: 1_800_000_000.0,
        monotonic=clock,
    )


class _BudgetCase(unittest.TestCase):
    """Taskの予算を45秒に固定する(既定値と同じだが、明示する)。"""

    budget_ms = 45_000.0

    def setUp(self) -> None:
        TASK_PROFILES[_TASK] = TaskProfile(task=_TASK, latency_budget_ms=self.budget_ms)
        self.addCleanup(TASK_PROFILES.pop, _TASK, None)
        self.clock = _StopClock()


class TestTheRequiredScenario(_BudgetCase):
    """§4の最低要求: A が30秒使ったら、B に残るのは約15秒。"""

    def test_the_second_provider_only_gets_the_remaining_budget(self) -> None:
        first = _TimedAdapter(self.clock, takes=30.0)                    # 30秒使って失敗
        second = _TimedAdapter(self.clock, takes=1.0, result={"x": "b"})  # 成功
        router = _router({"a": first, "b": second}, ("a", "b"), self.clock)

        result = router.generate(_TASK, "p", _SCHEMA)

        self.assertEqual(result.provider_used, "b")
        self.assertEqual(first.deadlines, [45.0], "1つ目には予算全部を渡す")
        self.assertEqual(
            second.deadlines, [15.0],
            "2つ目が新しく60秒待とうとしている(残り時間が伝わっていない)",
        )

    def test_the_budget_is_never_exceeded_across_fallbacks(self) -> None:
        """3回fallbackしても合計は予算内に収まる。"""
        adapters = {
            "a": _TimedAdapter(self.clock, takes=20.0),
            "b": _TimedAdapter(self.clock, takes=20.0),
            "c": _TimedAdapter(self.clock, takes=20.0),
        }
        router = _router(adapters, ("a", "b", "c"), self.clock)
        with self.assertRaises(NoProviderAvailableError):
            router.generate(_TASK, "p", _SCHEMA)
        self.assertLessEqual(
            self.clock.seconds, self.budget_ms / 1000.0 + 20.0,
            "予算を大きく超えて待っている",
        )

    def test_an_exhausted_budget_stops_further_attempts(self) -> None:
        first = _TimedAdapter(self.clock, takes=45.0)
        second = _TimedAdapter(self.clock, takes=1.0, result={"x": "b"})
        router = _router({"a": first, "b": second}, ("a", "b"), self.clock)
        with self.assertRaises(NoProviderAvailableError) as caught:
            router.generate(_TASK, "p", _SCHEMA)
        self.assertEqual(second.deadlines, [], "予算を使い切ったのに次を始めている")
        self.assertIn("時間予算", str(caught.exception))


class TestAdaptersThatCannotBeClamped(_BudgetCase):
    """締め切りを受け取れないAdapterの扱い。"""

    def test_an_unregistered_adapter_is_allowed_because_there_is_no_basis(self) -> None:
        """Registryに宣言が無ければ、除外する根拠が無い。

        根拠なく除外すると、実際には即答するAdapterまで締め出す
        ——予算を守る仕組みが、予算内で終わるものを止めるのは
        本末転倒である。
        """
        blind = _DeadlineBlindAdapter({"x": "ok"})
        router = _router({"unknown_fake": blind}, ("unknown_fake",), self.clock)
        result = router.generate(_TASK, "p", _SCHEMA)
        self.assertEqual(result.value, {"x": "ok"})

    def test_a_registered_slow_adapter_is_not_started_when_it_cannot_fit(self) -> None:
        """`local`は公称120秒。締め切りを渡せないなら、45秒の予算には
        入りきらないので**始めない**。始めれば超過が確定している。"""
        blind = _DeadlineBlindAdapter({"x": "ok"})
        router = _router({"local": blind}, ("local",), self.clock)
        with self.assertRaises(NoProviderAvailableError) as caught:
            router.generate(_TASK, "p", _SCHEMA)
        self.assertEqual(blind.calls, 0, "入りきらないのに呼んでいる")
        self.assertIn("残り時間", str(caught.exception))

    def test_not_starting_is_not_recorded_as_a_provider_failure(self) -> None:
        """**Providerは何も悪くない。** Circuit Breakerを進めない。"""
        blind = _DeadlineBlindAdapter({"x": "ok"})
        router = _router({"local": blind}, ("local",), self.clock)
        with self.assertRaises(NoProviderAvailableError):
            router.generate(_TASK, "p", _SCHEMA)
        state = router.states.get("local")
        self.assertEqual(state.consecutive_failures, 0)
        self.assertEqual(state.total_failures, 0)

    def test_a_fast_registered_adapter_still_fits(self) -> None:
        """Mockは公称1秒。予算が少なくても通る。"""
        router = _router({"mock": _DeadlineBlindAdapter({"x": "ok"})}, ("mock",), self.clock)
        self.clock.advance(44.0)  # 残り1秒
        result = router.generate(_TASK, "p", _SCHEMA)
        self.assertEqual(result.value, {"x": "ok"})


class TestProductionAdaptersAcceptADeadline(unittest.TestCase):
    """本番のAdapterが実際に締め切りを受け取れること。

    受け取れないと、上の`_BudgetCase`が守っているものが本番では
    働かない——「Test Doubleでしか動かない予算」になる。
    """

    def test_the_openai_compatible_adapter_supports_it(self) -> None:
        adapter = OpenAICompatibleAdapter(
            provider_name="p", base_url="http://t/v1", model="m", timeout_seconds=60.0
        )
        self.assertTrue(supports_deadline(adapter))
        clamped = apply_deadline(adapter, 15.0)
        self.assertEqual(clamped._timeout, 15.0)  # noqa: SLF001

    def test_gemini_supports_it(self) -> None:
        adapter = GeminiProvider(api_key="dummy-value-not-a-real-key", timeout=30.0)
        self.assertTrue(supports_deadline(adapter))
        self.assertEqual(apply_deadline(adapter, 5.0)._timeout, 5.0)  # noqa: SLF001

    def test_clamping_never_extends_the_provider_timeout(self) -> None:
        """残り予算が長くても、Provider側のtimeoutより長く待たない
        ——待っても何も起きない。"""
        adapter = OpenAICompatibleAdapter(
            provider_name="p", base_url="http://t/v1", model="m", timeout_seconds=30.0
        )
        self.assertEqual(apply_deadline(adapter, 300.0)._timeout, 30.0)  # noqa: SLF001

    def test_clamping_does_not_mutate_the_shared_instance(self) -> None:
        """**共有インスタンスを書き換えない。**

        `ProviderRouter`は起動時に作った1つを使い回すので、書き換えると
        同時に走る別のリクエストの予算まで動いてしまう。
        """
        adapter = OpenAICompatibleAdapter(
            provider_name="p", base_url="http://t/v1", model="m", timeout_seconds=60.0
        )
        apply_deadline(adapter, 5.0)
        self.assertEqual(adapter._timeout, 60.0)  # noqa: SLF001

    def test_a_deadline_is_never_zero_or_negative(self) -> None:
        adapter = OpenAICompatibleAdapter(
            provider_name="p", base_url="http://t/v1", model="m", timeout_seconds=60.0
        )
        self.assertGreater(apply_deadline(adapter, -5.0)._timeout, 0.0)  # noqa: SLF001

    def test_the_mock_adapter_does_not_need_a_deadline(self) -> None:
        """即答するものに締め切りは要らない。Registryの公称1秒で通る。"""
        self.assertFalse(supports_deadline(MockLLMAdapter()))


if __name__ == "__main__":
    unittest.main()
