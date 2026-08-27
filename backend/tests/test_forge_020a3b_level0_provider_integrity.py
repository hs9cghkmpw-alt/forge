"""Level 0 は **「Local Model が構造を作った」** の証拠である（020A3B §3）。

---

## 「どうやって作ったか」と「誰が作ったか」は別である

020A3 で `structure_source` / `structure_provider` / `structure_task` を
分けた。ところが **Level 0 の判定は `structure_source` しか見ていなかった。**

`AI_ENTITY_SYNTHESIS` が言っているのは「**AI が**構造を設計した」まで
である。Cloud が設計した実行も、Test Double が設計した実行も、同じ値に
なる。それを Level 0 に数えると、**Cloud の成果が Local の実績になる。**

これは 019B §4 / 020A で2回踏んだ「呼んでもいない Provider の手柄」と
同じ形であり、`local_model_evidence.py` の冒頭が「誰が作ったかを
Evidence 層に訊く」と書いている理由そのものである。

## ここで固定すること

Level 0 を通すには、**すべて**が要る。

| 条件 | 意味 |
|---|---|
| `structure_source == AI_ENTITY_SYNTHESIS` | どの段が作ったか |
| `structure_provider == LOCAL` | **誰が**作ったか |
| `structure_task == entity_synthesis` | どの stage が作ったか |
| `entity_synthesis in observed_tasks` | その stage が**実際に通った**か |
| `generation_source == LOCAL_AI` | 文書を作ったのが Local Model か |
| `deployment == LOCAL` | LOCAL で走ったか |
| `validator_passed` | Forge Validator を通ったか |
| `generation_evidence_uid` | 本番経路を通った証拠 |
| `verification == REAL` | 実測として記録されたか |

**1つでも欠けたら数えない。**
"""

from __future__ import annotations

import pathlib
import sys
import unittest

_ROOT = pathlib.Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
_BACKEND = _ROOT / "backend"
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from app.ai.gateway.benchmark_evidence import Verification  # noqa: E402
from app.ai.gateway.capability_evidence import (  # noqa: E402
    GenerationStructureSource,
    StructureProvider,
)
from app.ai.gateway.generation_evidence import GenerationSource  # noqa: E402
from app.ai.gateway.learning_events import Deployment  # noqa: E402
from app.ai.gateway.local_model_evidence import (  # noqa: E402
    Level0Outcome,
    LocalRuntimeBackend,
    RealLocalModelRun,
    RealLocalModelRunLog,
)
from app.ai.gateway.tasks import ForgeTask  # noqa: E402


def _passing_run(**overrides) -> RealLocalModelRun:  # noqa: ANN003
    """**本物の Level 0 実行**（これだけが数えられてよい）。"""
    defaults = {
        "provider": "local",
        "model": "qwen2.5:1.5b-instruct",
        "task": ForgeTask.COGNITIVE_STAGE,
        "observed_tasks": (ForgeTask.COGNITIVE_STAGE, ForgeTask.ENTITY_SYNTHESIS),
        "domain_resolution": "generated",
        "structure_source": GenerationStructureSource.AI_ENTITY_SYNTHESIS,
        "structure_provider": StructureProvider.LOCAL,
        "structure_task": ForgeTask.ENTITY_SYNTHESIS.value,
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


class TestTheBaselineRunIsActuallyValid(unittest.TestCase):
    """**弾きすぎて Local AI が永久に実績を持てない、では意味がない。**"""

    def test_a_complete_local_synthesis_run_counts(self) -> None:
        run = _passing_run()
        self.assertTrue(run.counts_as_real_local, run.why_not_counted())
        self.assertIs(run.level0_outcome, Level0Outcome.PASSED)


class TestStructureProviderIsCheckedIndependently(unittest.TestCase):
    """M1 / M2 / M3 — **「AI が作った」だけでは Local の実績にならない。**"""

    def test_m1_cloud_built_the_structure_is_not_level0(self) -> None:
        run = _passing_run(structure_provider=StructureProvider.CLOUD)
        self.assertFalse(
            run.counts_as_real_local,
            "Cloud が構造を作った実行が Local Model の実績になっている",
        )
        self.assertTrue(
            any("Local Provider ではない" in r for r in run.why_not_counted()),
            run.why_not_counted(),
        )

    def test_m2_a_test_double_built_the_structure_is_not_level0(self) -> None:
        run = _passing_run(structure_provider=StructureProvider.TEST_DOUBLE)
        self.assertFalse(run.counts_as_real_local)

    def test_m3_a_local_generation_source_does_not_rescue_a_cloud_structure(self) -> None:
        """**`generation_source` で上書きさせない。**

        文書を返したのが Local でも、**構造を設計したのが Cloud なら**
        構造生成の実績ではない。2つは別の事実である。
        """
        run = _passing_run(
            generation_source=GenerationSource.LOCAL_AI,
            structure_provider=StructureProvider.CLOUD,
        )
        self.assertFalse(run.counts_as_real_local)

    def test_an_unrecorded_provider_is_not_counted(self) -> None:
        """**記録し損ねたものを楽観側へ倒さない**（`CLAUDE.md` §3）。"""
        run = _passing_run(structure_provider=StructureProvider.NONE)
        self.assertFalse(run.counts_as_real_local)


class TestTheStructureTaskMustBeTheOneThatRan(unittest.TestCase):
    """M5 — **stage 名を書いただけでは通らない。**"""

    def test_m5_a_deterministic_stage_is_not_structure_generation(self) -> None:
        run = _passing_run(structure_task="entity_structure")
        self.assertFalse(run.counts_as_real_local)
        self.assertTrue(
            any("entity_synthesis ではない" in r for r in run.why_not_counted()),
            run.why_not_counted(),
        )

    def test_a_curated_fallback_stage_is_not_structure_generation(self) -> None:
        run = _passing_run(structure_task="entity_synthesis_fallback")
        self.assertFalse(run.counts_as_real_local)

    def test_an_unrecorded_stage_is_not_counted(self) -> None:
        run = _passing_run(structure_task="")
        self.assertFalse(run.counts_as_real_local)

    def test_a_claimed_stage_that_never_reached_the_router_is_not_counted(self) -> None:
        """**記録と実測を突き合わせる。**

        `structure_task` に正しい名前が入っていても、その Task が
        AIRouter を通っていなければ、構造生成は起きていない。
        """
        run = _passing_run(observed_tasks=(ForgeTask.COGNITIVE_STAGE,))
        self.assertFalse(run.counts_as_real_local)
        self.assertTrue(
            any("AIRouter を通っていない" in r for r in run.why_not_counted()),
            run.why_not_counted(),
        )


class TestTheHowAndTheWhoAreNotAliased(unittest.TestCase):
    """**「構造の作り方」と「作った Provider」を同じ型にしない。**

    020A3 の `StructureProvenance` には `LOCAL_AI` / `CLOUD_AI` /
    `TEST_DOUBLE` が `AI_ENTITY_SYNTHESIS` の別名として置かれていた。
    それは Provider を source の中へ畳み込むことであり、**2つを再び
    混ぜる。** merge のときに外したので、戻ったら落ちる形にしておく。
    """

    def test_the_structure_source_enum_names_no_provider(self) -> None:
        forbidden = ("LOCAL_AI", "CLOUD_AI", "TEST_DOUBLE", "LOCAL", "CLOUD")
        for name in forbidden:
            with self.subTest(name=name):
                self.assertFalse(
                    hasattr(GenerationStructureSource, name),
                    f"{name} は Provider の話であって、構造の作り方ではない",
                )

    def test_the_provider_enum_names_no_stage(self) -> None:
        for name in ("AI_ENTITY_SYNTHESIS", "CURATED", "DETERMINISTIC_CAPABILITY_PLAN"):
            with self.subTest(name=name):
                self.assertFalse(hasattr(StructureProvider, name))


class TestTheLogDistinguishesInvalidFromFailed(unittest.TestCase):
    def test_a_cloud_structure_run_is_recorded_but_not_counted(self) -> None:
        log = RealLocalModelRunLog()
        log.record(_passing_run(structure_provider=StructureProvider.CLOUD))
        self.assertEqual(log.count(), 0)
        self.assertEqual(len(log.all_runs()), 1, "数えなかった実行も残すこと")


if __name__ == "__main__":
    unittest.main()


class TestTheEvidenceIsActuallyWired(unittest.TestCase):
    """M4 — **配線が無ければ落ちる。**

    型に欄があっても、本番と script が埋めていなければ Level 0 は
    永久に `NONE` で不成立になる。「作ったが呼ばれない」を4回繰り返した
    リポジトリなので、**呼んでいることをテストで固定する。**
    """

    def test_production_records_the_structure_provider_and_stage(self) -> None:
        from fastapi.testclient import TestClient

        from app.ai.gateway.generation_evidence import default_generation_store
        from app.main import app

        client = TestClient(app)
        response = client.post(
            "/api/v1/ai/generate",
            json={"input": {"natural_language": "旅行の写真を日付ごとに残してメモを付けたい",
                            "generation_options": {"provider": "mock"}}},
        )
        self.assertEqual(response.status_code, 200, response.text)
        record = default_generation_store().all_records()[-1]

        # 決定的な経路なので `NONE` / `entity_structure` が**正しい**。
        # 見たいのは「欄が埋まっていること」である。
        self.assertIsInstance(record.structure_provider, StructureProvider)
        self.assertTrue(
            record.structure_task.strip(),
            "構造を作った stage が本番から記録されていない",
        )

    def test_the_level0_script_carries_both_fields_into_the_run(self) -> None:
        """script が `RealLocalModelRun` へ渡していること。"""
        source = (_ROOT / "scripts" / "verify_local_model_level0.py").read_text(
            encoding="utf-8",
        )
        for wiring in ("structure_provider=", "structure_task="):
            with self.subTest(wiring=wiring):
                self.assertIn(
                    wiring, source,
                    "Level 0 script が構造の Provider / stage を運んでいない",
                )
        self.assertIn(
            "records[-1].structure_provider", source,
            "Evidence Store から読まずに、どこかで作った値を入れている",
        )
