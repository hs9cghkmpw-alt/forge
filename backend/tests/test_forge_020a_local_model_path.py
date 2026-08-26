"""FORGE-020A — **Local Model への本番経路**と、実測の数え方。

---

## 見つけた欠陥（このファイルはそれを固定する）

`local`（`LocalModelProvider`）は

* Provider Registry に `IMPLEMENTED` / `Deployment.LOCAL` として在る
* `ProviderRouter._SPECIFIC_FACTORIES` に実装が結び付いている

のに、**HTTPからは1つも選べなかった**。`/generate` `/converse` `/update`
の3つとも Literal に `local` が無かった。

代わりに `/generate` が受理していた `oss` は `NotImplementedError` を
投げるスタブで、Registry 自身が「`local` が実質的な後継」と書いている。

> **動く方を隠して、動かない方を公開していた。**

Forge が繰り返している「作ったが本番から呼ばれない」の7例目である
（TD59 / 007 §10 / 010 Phase B / TD64 / TD69 / 016A / これ）。

Vision §39 Level 0 は

    Runtime → LocalModelProvider → AIRouter → Forge pipeline
      → Validator → Evidence

を通ることの証明なので、**ここが塞がっていると実機でも測れない。**

## 数え方も固定する

CEO 決定（2026-08-26）:

> Real Local Model runs は、実際の open-weight model から応答が返り、
> Forge production path を通った場合だけ加算する。
> fake server / mock / fixture は加算しない。
"""

from __future__ import annotations

import os
import sys
import typing
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

os.environ.setdefault("FORGE_FEATURE_WORKSPACE", "true")
os.environ.setdefault("FORGE_FEATURE_FOLDER", "true")

from app.ai.gateway.benchmark_evidence import Verification  # noqa: E402
from app.ai.gateway.generation_evidence import GenerationSource  # noqa: E402
from app.ai.gateway.learning_events import Deployment  # noqa: E402
from app.ai.gateway.provider_registry import (  # noqa: E402
    Deployment as RegistryDeployment,
)
from app.ai.gateway.local_model_evidence import (  # noqa: E402
    Level0Outcome,
    LocalRuntimeBackend,
    RealLocalModelRun,
    RealLocalModelRunLog,
    WeightIdentity,
)
from app.ai.gateway.provider_registry import (  # noqa: E402
    ImplementationStatus,
    provider_registry,
)
from app.ai.gateway.tasks import ForgeTask  # noqa: E402
from app.schemas.ai import (  # noqa: E402
    ConverseRequest,
    GenerationOptionsDTO,
    UpdateRequest,
)


def _accepted_providers(model, field: str = "provider") -> frozenset[str]:  # noqa: ANN001
    """その Request が HTTP で受理する Provider 名。"""
    annotation = model.model_fields[field].annotation
    literal = typing.get_args(annotation)[0]
    return frozenset(typing.get_args(literal))


class TestLocalProvidersAreSelectableOverHttp(unittest.TestCase):
    """**実装済みの Local Provider は、HTTPから選べること。**

    これが今回の欠陥を捕まえる guard である。

    ---

    ## なぜ「全 Provider」ではなく「Local な Provider」なのか

    最初は「Registry が IMPLEMENTED と言う Provider は全部 HTTP から
    選べること」と書いたが、それは**強すぎて嘘になる**。

    `groq` / `cerebras` / `openrouter` / `together` / `deepinfra` は
    IMPLEMENTED だが、利用者が名指しする想定ではない——環境変数が
    揃ったものを **AIRouter が自動で並べる**（010 Phase F）。
    HTTP に列挙されていないのは欠陥ではなく設計である。

    一方 **Local は名指しできなければならない。** Vision §39 Level 0 は
    「Local Model を通したこと」の証明なので、Router の気分で選ばれる
    のを待つのでは測れない。

    範囲を「Local かつ実装済み」に絞ると、主張が真になる。
    """

    def _implemented_local(self) -> frozenset[str]:
        """**`Deployment` は2つある。** 間違えると guard が黙って効かなくなる。

        `provider_registry.Deployment` と `learning_events.Deployment` は
        別の enum で、値は同じでも `is` 比較は必ず `False` になる。
        最初にこれを取り違えて、**条件が常に空集合になっていた**
        （テストは緑のまま守っていない状態）。Registry を見るので
        `RegistryDeployment` を使う。
        """
        return frozenset(
            d.provider_id for d in provider_registry()
            if d.implementation_status is ImplementationStatus.IMPLEMENTED
            and d.deployment is RegistryDeployment.LOCAL
        )

    def test_there_is_at_least_one_implemented_local_provider(self) -> None:
        """前提の確認。**これが空なら下の3つは無意味になる。**"""
        self.assertTrue(self._implemented_local(), "実装済みの Local Provider が無い")

    def test_generate_accepts_every_implemented_local_provider(self) -> None:
        missing = self._implemented_local() - _accepted_providers(GenerationOptionsDTO)
        self.assertEqual(
            missing, frozenset(),
            f"実装済みなのに /generate から選べない Local Provider: {sorted(missing)}",
        )

    def test_converse_accepts_every_implemented_local_provider(self) -> None:
        """**会話がForgeの本線である。** ここが塞がると本線を通れない。"""
        missing = self._implemented_local() - _accepted_providers(ConverseRequest)
        self.assertEqual(
            missing, frozenset(),
            f"実装済みなのに /converse から選べない Local Provider: {sorted(missing)}",
        )

    def test_update_accepts_every_implemented_local_provider(self) -> None:
        missing = self._implemented_local() - _accepted_providers(UpdateRequest)
        self.assertEqual(
            missing, frozenset(),
            f"実装済みなのに /update から選べない Local Provider: {sorted(missing)}",
        )

    def test_every_accepted_provider_name_exists_in_the_registry(self) -> None:
        """**Registry に無い名前を受理しない。** 綴り間違いを通さない。"""
        known = {d.provider_id for d in provider_registry()}
        for model in (GenerationOptionsDTO, ConverseRequest, UpdateRequest):
            unknown = _accepted_providers(model) - known
            self.assertEqual(
                unknown, frozenset(),
                f"{model.__name__} が Registry に無い Provider 名を受理する: "
                f"{sorted(unknown)}",
            )

    def test_local_is_implemented_in_the_registry(self) -> None:
        local = next(
            (d for d in provider_registry() if d.provider_id == "local"), None,
        )
        self.assertIsNotNone(local, "Registry に 'local' が無い")
        self.assertIs(local.implementation_status, ImplementationStatus.IMPLEMENTED)
        self.assertIs(local.deployment, RegistryDeployment.LOCAL)
        self.assertTrue(local.supports_structured_output)

    def test_local_has_a_concrete_adapter(self) -> None:
        """Registry の宣言だけでなく、**実装が結び付いている**こと。"""
        from app.ai.foundation.local_provider import LocalModelProvider
        from app.ai.runtime.provider_router import ProviderRouter

        self.assertIs(ProviderRouter._SPECIFIC_FACTORIES["local"], LocalModelProvider)

    def test_the_superseded_stub_is_not_the_only_local_option(self) -> None:
        """**動く方を隠して動かない方を公開する**、をしない。

        `oss` は `NotImplementedError` を投げるスタブで、Registry 自身が
        「`local` が実質的な後継」と書いている。`oss` だけが選べて
        `local` が選べない状態が、今回の欠陥そのものだった。
        """
        accepted = _accepted_providers(GenerationOptionsDTO)
        if "oss" in accepted:
            self.assertIn(
                "local", accepted,
                "スタブ(oss)だけが選べて、実装(local)が選べない",
            )


try:
    from fastapi.testclient import TestClient

    from app.main import app

    _FASTAPI_AVAILABLE = True
except ImportError:  # pragma: no cover
    _FASTAPI_AVAILABLE = False


@unittest.skipUnless(_FASTAPI_AVAILABLE, "fastapi/pydanticが無い環境ではスキップする")
class TestLocalIsNotRejectedBySchema(unittest.TestCase):
    """**schema で門前払いされないこと。**

    Runtime が無い環境では当然失敗するが、失敗の**種類**が違う。

    * `422 schema_invalid` … 経路が無い（これが今回の欠陥）
    * Provider 起因の失敗 … 経路は在る。Runtime が居ないだけ

    後者であることを固定する。
    """

    def setUp(self) -> None:
        self.client = TestClient(app)

    def _generate(self, provider: str):  # noqa: ANN202
        return self.client.post(
            "/api/v1/ai/generate",
            json={"input": {"natural_language": "支出を記録したい",
                            "generation_options": {"provider": provider}}},
        )

    def test_local_is_not_rejected_as_an_unknown_value(self) -> None:
        response = self._generate("local")
        if response.status_code == 422:
            body = response.json()
            self.assertNotEqual(
                (body.get("error") or {}).get("sub_reason"), "schema_invalid",
                "provider='local' が schema で弾かれている（本番経路が無い）",
            )

    def test_an_unknown_provider_is_still_rejected(self) -> None:
        """**何でも通すようにしたわけではない。**"""
        response = self._generate("definitely_not_a_provider")
        self.assertEqual(response.status_code, 422)


class TestRealLocalModelRunCounting(unittest.TestCase):
    """**何を「実モデルで動いた」と数えるか。**"""

    def _passing_run(self, **overrides) -> RealLocalModelRun:  # noqa: ANN003
        defaults = {
            "provider": "local",
            "model": "qwen2.5:1.5b-instruct",
            # **本番の `/generate` が実際に通す Task**（020A1）。
            # `prompt_pipeline.py` が `bind(ForgeTask.COGNITIVE_STAGE)` を
            # 呼ぶ。以前ここは FORGE_LANGUAGE_UPDATE を書いており、
            # **別の Task の成績として集計される**状態だった。
            "task": ForgeTask.COGNITIVE_STAGE,
            "observed_tasks": (ForgeTask.COGNITIVE_STAGE,),
            "domain_resolution": "generated",
            "runtime_backend": LocalRuntimeBackend.OLLAMA,
            "runtime_version": "0.5.0",
            "model_id": "qwen2.5:1.5b-instruct",
            "model_digest": "sha256:abc123",
            "quantization": "Q4_K_M",
            "deployment": Deployment.LOCAL,
            "latency_ms": 1234.0,
            "structured_output_ok": True,
            "validator_passed": True,
            "generation_evidence_uid": "gen-uid-1",
            "generation_source": GenerationSource.LOCAL_AI,
            "host_id": "real-machine",
            "verification": Verification.REAL,
        }
        defaults.update(overrides)
        return RealLocalModelRun(**defaults)

    def test_a_complete_real_run_is_counted(self) -> None:
        run = self._passing_run()
        self.assertTrue(run.counts_as_real_local, run.why_not_counted())
        self.assertIs(run.level0_outcome, Level0Outcome.PASSED)

    def test_a_mock_provider_is_never_counted(self) -> None:
        run = self._passing_run(provider="mock")
        self.assertFalse(run.counts_as_real_local)

    def test_a_fake_server_is_never_counted(self) -> None:
        """011 の偽 OpenAI 互換サーバ（TD67）を Level 0 にしない。"""
        run = self._passing_run(runtime_backend=LocalRuntimeBackend.TEST_DOUBLE)
        self.assertFalse(run.counts_as_real_local)

    def test_an_unidentified_runtime_is_not_counted(self) -> None:
        run = self._passing_run(runtime_backend=LocalRuntimeBackend.UNKNOWN)
        self.assertFalse(run.counts_as_real_local)

    def test_a_run_without_a_weight_digest_still_passes_level0(self) -> None:
        """**重みの digest は Level 0 の条件ではない**（020A1で変更）。

        以前はここで `model_digest=""` を「数えない」としていた。
        1つの欄に「重みの同一性」と「fixture 除け」を兼務させていたので、
        digest を返さない本物の Runtime（llama-server 等）が永久に
        Level 0 へ到達できなかった。

        Level 0 が証明するのは**経路**である。重みの同一性は
        `weight_identity` が別に持ち、**Level 0.5 が要求する**。
        """
        run = self._passing_run(model_digest="")
        self.assertTrue(run.counts_as_real_local, run.why_not_counted())
        self.assertIs(run.weight_identity, WeightIdentity.UNVERIFIED)
        # **Baseline へは進ませない。** 緩めた分をここで受け止める。
        self.assertFalse(run.ready_for_baseline)

    def test_a_run_with_a_digest_is_ready_for_baseline(self) -> None:
        run = self._passing_run()
        self.assertIs(run.weight_identity, WeightIdentity.VERIFIED_DIGEST)
        self.assertTrue(run.ready_for_baseline)

    def test_a_model_id_is_not_a_weight_digest(self) -> None:
        """**名前を digest 扱いしない**（020A1）。

        OpenAI 互換 `/v1/models` の `id` はただの名前である。同じ名前で
        中身の違う重みを配ることは誰にでもできる。
        """
        run = self._passing_run(model_id="qwen2.5:1.5b-instruct", model_digest="")
        self.assertIs(run.weight_identity, WeightIdentity.UNVERIFIED)

    def test_a_run_without_a_model_id_is_not_counted(self) -> None:
        run = self._passing_run(model_id="")
        self.assertFalse(run.counts_as_real_local)


class TestProbeIntegrity(unittest.TestCase):
    """**測定が成立しているか**（020A1）。"""

    def _passing_run(self, **overrides) -> RealLocalModelRun:  # noqa: ANN003
        return TestRealLocalModelRunCounting._passing_run(self, **overrides)  # type: ignore[arg-type]

    def test_a_curated_probe_is_invalid_not_failed(self) -> None:
        """**Local Model の失敗ではない。仕事が回っていない。**

        既定 probe「毎日の支出を記録して合計を見たい」は
        `household_budget` の Curated へ解決される（実測）。
        Curated 経路は AI を1回も呼ばずに文書を作る。
        """
        run = self._passing_run(domain_resolution="curated")
        self.assertFalse(run.counts_as_real_local)
        self.assertTrue(run.probe_was_curated)
        self.assertIs(run.level0_outcome, Level0Outcome.INVALID_PROBE)

    def test_a_generated_probe_is_valid(self) -> None:
        run = self._passing_run(domain_resolution="generated")
        self.assertFalse(run.probe_was_curated)
        self.assertIs(run.level0_outcome, Level0Outcome.PASSED)

    def test_a_claimed_task_that_never_ran_is_not_counted(self) -> None:
        """**手で書いた Task を信じない**（020A1）。

        script は以前 `FORGE_LANGUAGE_UPDATE` を定数で書いていたが、
        `/generate` が通すのは `COGNITIVE_STAGE` である。
        """
        run = self._passing_run(
            task=ForgeTask.FORGE_LANGUAGE_UPDATE,
            observed_tasks=(ForgeTask.COGNITIVE_STAGE,),
        )
        self.assertFalse(run.counts_as_real_local)
        self.assertTrue(
            any("実際に通った Task" in r for r in run.why_not_counted()),
            run.why_not_counted(),
        )

    def test_an_unobserved_task_is_not_counted(self) -> None:
        run = self._passing_run(observed_tasks=())
        self.assertFalse(run.counts_as_real_local)

    def test_a_run_outside_the_production_path_is_not_counted(self) -> None:
        """Provider を横から叩いた実行を Level 0 にしない。"""
        run = self._passing_run(generation_evidence_uid="")
        self.assertFalse(run.counts_as_real_local)
        self.assertIn(
            "Forge の本番経路を通った証拠（Evidence uid）が無い",
            run.why_not_counted(),
        )

    def test_a_curated_document_is_not_counted(self) -> None:
        """**200 OK に騙されない**（実測で踏んだ）。

        Runtime を起動していない状態で `provider="local"` を指定すると
        HTTP 200 が返り、Validator も通る。作ったのは Curated Domain
        Library で、**LLM は1回も呼ばれていない**。

        「Local を指定したら 200 が返った」は Level 0 の証拠にならない。
        """
        run = self._passing_run(generation_source=GenerationSource.CURATED)
        self.assertFalse(run.counts_as_real_local)
        self.assertIn(
            "文書を作ったのが Local Model ではない（curated）",
            run.why_not_counted(),
        )

    def test_a_cloud_generated_document_is_not_counted(self) -> None:
        run = self._passing_run(generation_source=GenerationSource.CLOUD_AI)
        self.assertFalse(run.counts_as_real_local)

    def test_a_test_double_document_is_not_counted(self) -> None:
        run = self._passing_run(generation_source=GenerationSource.TEST_DOUBLE)
        self.assertFalse(run.counts_as_real_local)

    def test_a_run_that_failed_the_validator_is_not_counted(self) -> None:
        self.assertFalse(self._passing_run(validator_passed=False).counts_as_real_local)

    def test_a_cloud_deployment_is_not_counted(self) -> None:
        self.assertFalse(self._passing_run(deployment=Deployment.CLOUD).counts_as_real_local)

    def test_an_unverified_run_is_not_counted(self) -> None:
        run = self._passing_run(verification=Verification.UNVERIFIED)
        self.assertFalse(run.counts_as_real_local)

    def test_every_refusal_is_explained(self) -> None:
        """**「数えない」だけ返さない。**

        020A1 で `model_digest=""` は拒否理由から外した（重みの同一性は
        Level 0.5 の条件）。代わりに `model_id=""` を使う。
        """
        run = self._passing_run(provider="mock", model_id="", latency_ms=0.0)
        self.assertGreaterEqual(len(run.why_not_counted()), 3)

    def test_the_diagnostic_form_shows_why_it_was_not_counted(self) -> None:
        rendered = self._passing_run(provider="mock").to_dict()
        self.assertFalse(rendered["counts_as_real_local"])
        self.assertTrue(rendered["why_not_counted"])


class TestRealLocalModelRunLog(unittest.TestCase):
    def setUp(self) -> None:
        self.log = RealLocalModelRunLog()

    def _run(self, **overrides) -> RealLocalModelRun:  # noqa: ANN003
        return TestRealLocalModelRunCounting._passing_run(self, **overrides)  # type: ignore[arg-type]

    def test_no_runs_means_not_attempted(self) -> None:
        """**「まだ試していない」と「試して失敗した」を混ぜない。**"""
        self.assertIs(self.log.level0(), Level0Outcome.NOT_ATTEMPTED)

    def test_a_rejected_run_makes_level0_failed_not_not_attempted(self) -> None:
        self.log.record(self._run(provider="mock"))
        self.assertIs(self.log.level0(), Level0Outcome.FAILED)

    def test_rejected_runs_are_still_recorded(self) -> None:
        """数えなかった実行も残す。**「なぜ0件か」が分からなくなる。**"""
        self.log.record(self._run(provider="mock"))
        self.assertEqual(self.log.size(), 1)
        self.assertEqual(self.log.count(), 0)
        self.assertEqual(len(self.log.rejected_runs()), 1)

    def test_a_real_run_is_counted_and_passes_level0(self) -> None:
        self.log.record(self._run())
        self.assertEqual(self.log.count(), 1)
        self.assertIs(self.log.level0(), Level0Outcome.PASSED)

    def test_mixing_mock_runs_does_not_inflate_the_count(self) -> None:
        self.log.record(self._run())
        for _ in range(5):
            self.log.record(self._run(provider="mock"))
        self.assertEqual(self.log.count(), 1, "Mock が実測に混ざっている")

    def test_recorded_at_is_filled_in(self) -> None:
        stored = self.log.record(self._run())
        self.assertGreater(stored.recorded_at, 0)


class TestThisContainerHasNotReachedLevel0(unittest.TestCase):
    """**この container では Level 0 に到達していない**（CEO決定、2026-08-26）。

    実測は別実機で行う。ここで「到達した」に変わっていたら、
    Mock を数えたか、偽サーバを数えたかのどちらかである。
    """

    def test_the_default_log_counts_no_real_runs(self) -> None:
        from app.ai.gateway.local_model_evidence import default_real_local_run_log

        self.assertEqual(
            default_real_local_run_log().count(), 0,
            "この container で Real Local Model run が数えられている。"
            "Mock か偽サーバを数えていないか確認すること",
        )


if __name__ == "__main__":  # pragma: no cover
    unittest.main()


class TestLevel0ProbeIsActuallyNonCurated(unittest.TestCase):
    """**probe が Curated へ落ちないことを本番で確かめる**（020A1）。

    `scripts/verify_local_model_level0.py` の定数を、
    **実際に `/generate` へ通して**検証する。定数を目で見ても、
    Curated へ落ちるかどうかは分からない——実際に落ちていた。

    このテストが落ちるのは、probe が Curated 側へ寄ったときである。
    そのとき Level 0 の計測は無言で無効になるので、**気付ける形にする。**
    """

    def setUp(self) -> None:
        import importlib.util
        import pathlib

        root = pathlib.Path(__file__).resolve().parents[2]
        spec = importlib.util.spec_from_file_location(
            "_level0_script", root / "scripts" / "verify_local_model_level0.py",
        )
        assert spec and spec.loader
        self.script = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.script)
        self.client = TestClient(app)

    def _resolution(self, need: str) -> str:
        response = self.client.post(
            "/api/v1/ai/generate",
            json={"input": {"natural_language": need,
                            "generation_options": {"provider": "mock"}}},
        )
        self.assertEqual(response.status_code, 200, response.text)
        diagnostics = (response.json().get("result") or {}).get("diagnostics") or {}
        for entry in diagnostics.get("decision_trace") or ():
            if entry.get("stage") == "domain_resolution":
                return str(entry.get("decision") or "").strip().lower()
        return ""

    def test_the_level0_probe_requires_synthesis(self) -> None:
        self.assertEqual(self._resolution(self.script.LEVEL0_PROBE), "generated")

    def test_the_old_default_probe_really_was_curated(self) -> None:
        """**その罠が実在したことを固定する。**

        消すと「なぜ probe を変えたのか」が分からなくなり、
        「短くて分かりやすいから」と元へ戻される。
        """
        self.assertEqual(self._resolution(self.script.CURATED_TRAP_PROBE), "curated")

    def test_the_script_does_not_default_to_the_trap(self) -> None:
        self.assertNotEqual(self.script.LEVEL0_PROBE, self.script.CURATED_TRAP_PROBE)
