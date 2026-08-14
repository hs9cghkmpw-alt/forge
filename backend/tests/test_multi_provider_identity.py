"""Multi-Provider Identity(FORGE-AI-FOUNDATION-011 §1、2026-08-14)。

指示書の最低要求をそのまま引く:

>     Cloud A
>     Cloud B
>     Cloud C
>
> を同時登録し、各ProviderのState / Benchmark / ResultのIdentityが
> 混ざらないこと。

---

## 010で何が間違っていたか

`CloudCompatibleProvider.provider_name == "cloud"` 固定だった。
環境変数を差し替えれば中身はGroqにもCerebrasにもなるが、Forgeから
見ると常に同じ`cloud`である。

    今日: cloud = Groq     → 枠切れを学習
    明日: cloud = Cerebras → 「昨日cloudが落ちた」として除外される

**Protocolの共有とIdentityの共有を混同していた。** 通信の形が同じ
ことと、同じ相手であることは別である。

## このファイルが守る不変条件

1. 同一Protocolでも`provider_id`が違えば**別Adapter・別Identity**
2. Quota / Circuit Breaker の状態が混ざらない
3. Benchmarkの記録が混ざらない
4. `RoutedResult.provider_used`が正しい名前を返す
5. Providerが増えても**HTTP通信の実装は増えない**
"""

from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from app.ai.foundation.cloud_provider import OpenAICompatibleCloudProvider  # noqa: E402
from app.ai.foundation.openai_compatible import OpenAICompatibleAdapter  # noqa: E402
from app.ai.gateway.ai_errors import ErrorKind  # noqa: E402
from app.ai.gateway.benchmark_evidence import (  # noqa: E402
    BenchmarkEvidenceStore,
    BenchmarkRun,
    Verification,
)
from app.ai.gateway.provider_registry import (  # noqa: E402
    Deployment,
    ImplementationStatus,
    Protocol,
    configured_providers,
    definition_for,
    env_prefix_for,
    extra_provider_warnings,
    provider_registry,
)
from app.ai.gateway.provider_state import ProviderStateStore  # noqa: E402
from app.ai.gateway.tasks import ForgeTask  # noqa: E402
from app.ai.runtime.provider_router import ProviderRouter  # noqa: E402

# 「Cloud A / B / C」に相当する、実在の3 Provider。
_CLOUD_A, _CLOUD_B, _CLOUD_C = "groq", "cerebras", "openrouter"
_ALL_THREE = (_CLOUD_A, _CLOUD_B, _CLOUD_C)


def _configure(provider_id: str, *, model: str = "m") -> None:
    prefix = env_prefix_for(provider_id)
    os.environ[f"{prefix}_BASE_URL"] = f"https://{provider_id}.test/v1"
    os.environ[f"{prefix}_API_KEY"] = "dummy-value-not-a-real-key"
    os.environ[f"{prefix}_MODEL"] = model


class _EnvSandbox(unittest.TestCase):
    """環境変数を汚さないための共通処理。"""

    _EXTRA_VARS: tuple[str, ...] = ()

    def setUp(self) -> None:
        names = ["FORGE_DEFAULT_PROVIDER", "FORGE_EXTRA_PROVIDERS", *self._EXTRA_VARS]
        for provider_id in (*_ALL_THREE, "myhost", "another"):
            prefix = env_prefix_for(provider_id)
            names += [
                f"{prefix}_BASE_URL", f"{prefix}_API_KEY", f"{prefix}_MODEL",
                f"{prefix}_EXTRA_HEADERS", f"{prefix}_TIMEOUT_SECONDS",
            ]
        self._saved = {name: os.environ.get(name) for name in names}
        for name in names:
            os.environ.pop(name, None)

    def tearDown(self) -> None:
        for name, value in self._saved.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value


class TestThreeCloudsRegisterAtOnce(_EnvSandbox):
    """§1の最低要求: Cloud A / B / C を同時に載せられること。"""

    def test_all_three_are_declared_with_distinct_identities(self) -> None:
        ids = [d.provider_id for d in provider_registry()]
        for provider_id in _ALL_THREE:
            with self.subTest(provider=provider_id):
                self.assertIn(provider_id, ids)
        self.assertEqual(len(set(ids)), len(ids), "provider_idが重複している")

    def test_all_three_are_discovered_when_configured(self) -> None:
        for provider_id in _ALL_THREE:
            _configure(provider_id)
        discovered = [d.provider_id for d in configured_providers()]
        for provider_id in _ALL_THREE:
            with self.subTest(provider=provider_id):
                self.assertIn(provider_id, discovered)

    def test_configuring_one_does_not_configure_the_others(self) -> None:
        """**環境変数が分かれていること**の確認。

        1つの`FORGE_CLOUD_*`を共有していた010では、これが成立しなかった。
        """
        _configure(_CLOUD_A)
        discovered = [d.provider_id for d in configured_providers()]
        self.assertIn(_CLOUD_A, discovered)
        self.assertNotIn(_CLOUD_B, discovered)
        self.assertNotIn(_CLOUD_C, discovered)

    def test_each_resolves_to_its_own_adapter_instance(self) -> None:
        router = ProviderRouter()
        adapters = {p: router.resolve(p) for p in _ALL_THREE}
        self.assertEqual(len({id(a) for a in adapters.values()}), 3)
        for provider_id, adapter in adapters.items():
            with self.subTest(provider=provider_id):
                self.assertEqual(adapter.provider_name, provider_id)

    def test_each_reads_its_own_endpoint(self) -> None:
        _configure(_CLOUD_A, model="model-a")
        _configure(_CLOUD_B, model="model-b")
        router = ProviderRouter()
        self.assertEqual(router.resolve(_CLOUD_A).base_url, f"https://{_CLOUD_A}.test/v1")
        self.assertEqual(router.resolve(_CLOUD_B).base_url, f"https://{_CLOUD_B}.test/v1")
        self.assertEqual(router.resolve(_CLOUD_A).model, "model-a")
        self.assertEqual(router.resolve(_CLOUD_B).model, "model-b")


class TestStateDoesNotMixAcrossProviders(_EnvSandbox):
    """Quota / Circuit Breaker が混ざらないこと。"""

    def test_a_quota_exhaustion_on_one_does_not_exclude_another(self) -> None:
        """**010の`cloud`枠で壊れていたのはここである。**

        昨日のGroqの枠切れが、今日のCerebrasを除外していた。
        """
        states = ProviderStateStore(now=lambda: 1_800_000_000.0)
        states.record_failure(_CLOUD_A, ErrorKind.QUOTA_EXHAUSTED)
        self.assertFalse(states.get(_CLOUD_A).is_selectable(now=1_800_000_000.0))
        self.assertTrue(states.get(_CLOUD_B).is_selectable(now=1_800_000_000.0))

    def test_circuit_breaker_counts_are_per_provider(self) -> None:
        states = ProviderStateStore(now=lambda: 1_800_000_000.0)
        for _ in range(3):
            states.record_failure(_CLOUD_A, ErrorKind.PROVIDER_SERVER_ERROR)
        self.assertEqual(states.get(_CLOUD_A).consecutive_failures, 3)
        self.assertEqual(states.get(_CLOUD_B).consecutive_failures, 0)
        self.assertEqual(states.get(_CLOUD_C).consecutive_failures, 0)

    def test_success_on_one_does_not_clear_another(self) -> None:
        states = ProviderStateStore(now=lambda: 1_800_000_000.0)
        states.record_failure(_CLOUD_A, ErrorKind.PROVIDER_SERVER_ERROR)
        states.record_success(_CLOUD_B, latency_ms=10.0)
        self.assertEqual(states.get(_CLOUD_A).consecutive_failures, 1)


class TestBenchmarkRecordsDoNotMix(_EnvSandbox):
    """測定結果が混ざらないこと。"""

    _NOW = 1_800_000_000.0

    def _run(self, provider: str, accuracy: float) -> BenchmarkRun:
        return BenchmarkRun(
            task=ForgeTask.CONVERSATION_STEP, provider=provider,
            model=f"{provider}-model", dataset_id="impact-v1", dataset_size=16,
            verification=Verification.REAL, task_accuracy=accuracy,
            schema_valid_rate=1.0, recorded_at=self._NOW,
        )

    def test_three_providers_produce_three_records(self) -> None:
        store = BenchmarkEvidenceStore(now=lambda: self._NOW)
        store.record(self._run(_CLOUD_A, 0.9))
        store.record(self._run(_CLOUD_B, 0.5))
        store.record(self._run(_CLOUD_C, 0.7))
        runs = store.runs_for(ForgeTask.CONVERSATION_STEP)
        self.assertEqual(len(runs), 3)
        self.assertEqual({r.provider for r in runs}, set(_ALL_THREE))

    def test_the_ranking_keeps_them_apart(self) -> None:
        """010の`cloud`枠なら、3つの測定が1つの記録へ上書きし合った。"""
        store = BenchmarkEvidenceStore(now=lambda: self._NOW)
        store.record(self._run(_CLOUD_A, 0.9))
        store.record(self._run(_CLOUD_B, 0.5))
        store.record(self._run(_CLOUD_C, 0.7))
        self.assertEqual(
            store.ranking_for(ForgeTask.CONVERSATION_STEP),
            (_CLOUD_A, _CLOUD_C, _CLOUD_B),
        )

    def test_a_model_change_is_visible_per_provider(self) -> None:
        """`model`もProviderごとに記録される。Provider名だけでは
        「同じgroqでもモデルが違う」を表せない。"""
        store = BenchmarkEvidenceStore(now=lambda: self._NOW)
        store.record(self._run(_CLOUD_A, 0.9))
        store.record(self._run(_CLOUD_B, 0.5))
        by_provider = {r.provider: r.model for r in store.runs_for(ForgeTask.CONVERSATION_STEP)}
        self.assertEqual(by_provider[_CLOUD_A], f"{_CLOUD_A}-model")
        self.assertEqual(by_provider[_CLOUD_B], f"{_CLOUD_B}-model")


class TestTheGenericAdapterIsReused(_EnvSandbox):
    """§1「Provider追加ごとにHTTP通信実装をコピーしないこと」。"""

    def test_every_openai_compatible_cloud_shares_one_implementation(self) -> None:
        router = ProviderRouter()
        for provider_id in _ALL_THREE:
            with self.subTest(provider=provider_id):
                adapter = router.resolve(provider_id)
                self.assertIsInstance(adapter, OpenAICompatibleAdapter)
                self.assertIsInstance(adapter, OpenAICompatibleCloudProvider)

    def test_adding_a_provider_needs_no_new_http_code(self) -> None:
        """**このテストが本題である。**

        `FORGE_EXTRA_PROVIDERS`で名前を足すだけで、コード変更なしに
        Providerが1つ増える。増えるのは宣言であって実装ではない。
        """
        os.environ["FORGE_EXTRA_PROVIDERS"] = "myhost"
        _configure("myhost")
        self.assertIn("myhost", [d.provider_id for d in provider_registry()])
        self.assertIn("myhost", [d.provider_id for d in configured_providers()])
        adapter = ProviderRouter().resolve("myhost")
        self.assertIsInstance(adapter, OpenAICompatibleAdapter)
        self.assertEqual(adapter.provider_name, "myhost")
        self.assertEqual(adapter.base_url, "https://myhost.test/v1")

    def test_the_protocol_factory_covers_unknown_openai_compatible_names(self) -> None:
        """専用実装が無くてもProtocolで作れること(名前ごとの分岐が無い)。"""
        definition = definition_for(_CLOUD_A)
        self.assertIs(definition.protocol, Protocol.OPENAI_COMPATIBLE)
        self.assertIs(definition.deployment, Deployment.CLOUD)
        self.assertIs(definition.implementation_status, ImplementationStatus.IMPLEMENTED)
        self.assertNotIn(_CLOUD_A, ProviderRouter._SPECIFIC_FACTORIES)  # noqa: SLF001


class TestExtraProvidersCannotBreakIdentity(_EnvSandbox):
    """環境変数からの追加が、既存Identityを壊さないこと。"""

    def test_an_existing_provider_name_cannot_be_overridden(self) -> None:
        """`gemini`を別のエンドポイントへ向けられると、
        Benchmarkの記録が意味を失う。"""
        os.environ["FORGE_EXTRA_PROVIDERS"] = "gemini"
        ids = [d.provider_id for d in provider_registry()]
        self.assertEqual(ids.count("gemini"), 1)
        self.assertTrue(any("上書きできない" in w for w in extra_provider_warnings()))

    def test_a_malformed_name_is_dropped_with_a_reason(self) -> None:
        """設定ミス1つでForge全体を止めない。ただし黙って消さない。"""
        os.environ["FORGE_EXTRA_PROVIDERS"] = "Bad Name!"
        self.assertNotIn("Bad Name!", [d.provider_id for d in provider_registry()])
        self.assertTrue(extra_provider_warnings())

    def test_a_broken_extra_provider_does_not_stop_the_router(self) -> None:
        os.environ["FORGE_EXTRA_PROVIDERS"] = "gemini,,Bad!,myhost"
        router = ProviderRouter()
        self.assertTrue(router.is_registered("myhost"))
        self.assertTrue(router.is_registered("gemini"))


if __name__ == "__main__":
    unittest.main()
