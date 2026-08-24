"""Local Promotion Gate（FORGE-017A §7）。

---

## 何を解いたテストか

Architectureは「Qualified Local → Local」と書きながら、実装の説明は
「Local優先は Benchmark 順位が同点のときだけ」だった。**同点のときだけ
効く優先は Local First ではない**——Cloudが1点でも高ければ毎回Cloudが
選ばれ、Localは永久に使われない。

かといって「Localだから先」に戻すと、`AIRouter._order()`が実装した上で
退けた「測っていない品質を賭けてQuotaを節約する」へ戻る。

**Best Score Wins をやめ、Quality Gate にした。** 一番良いものではなく
「製品として通用する水準か」で判断する。

このファイルは両方の性質を同時に固定する。

* 満たしたLocalは、Cloudが上でも選ばれる（Local Firstである）
* 満たしていないLocalは、前へ出ない（未測定を優先しない）
"""

from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from app.ai.gateway.benchmark_evidence import (  # noqa: E402
    BenchmarkEvidenceStore,
    BenchmarkRun,
    Verification,
)
from app.ai.gateway.local_promotion import LocalPromotionGate  # noqa: E402
from app.ai.gateway.tasks import ForgeTask  # noqa: E402

_TASK = ForgeTask.ENTITY_SYNTHESIS
_NOW = 1_800_000_000.0


def _run(provider: str, **overrides) -> BenchmarkRun:
    defaults = {
        "task": _TASK,
        "provider": provider,
        "model": f"{provider}-model",
        "dataset_id": "entity-synthesis-v1",
        "dataset_hash": "abc123",
        "dataset_size": 32,
        "verification": Verification.REAL,
        "schema_valid_rate": 0.98,
        "task_accuracy": 0.92,
        "failure_rate": 0.02,
        "latency_p50_ms": 900.0,
        "recorded_at": _NOW - 3600,
    }
    return BenchmarkRun(**{**defaults, **overrides})


class TestTheGateRequiresRealMeasurement(unittest.TestCase):
    """**未測定のLocalを優先しない**（過去に退けた失敗へ戻らない）。"""

    def test_no_measurement_means_not_eligible(self) -> None:
        gate = LocalPromotionGate(BenchmarkEvidenceStore())
        decision = gate.evaluate(
            provider="ollama", task=_TASK, is_local=True, now=_NOW
        )
        self.assertFalse(decision.eligible)
        self.assertTrue(decision.reasons)

    def test_a_gate_without_evidence_promotes_nothing(self) -> None:
        """Evidence Storeが無い＝何も測っていない。"""
        decision = LocalPromotionGate().evaluate(
            provider="ollama", task=_TASK, is_local=True, now=_NOW
        )
        self.assertFalse(decision.eligible)

    def test_a_test_double_measurement_does_not_promote(self) -> None:
        """**Test Doubleで測った数字で本番の経路を決めない。**

        Doubleは成功するAdapterをいくらでも作れる。
        """
        store = BenchmarkEvidenceStore()
        store.record(_run("ollama", verification=Verification.DOUBLE))
        decision = LocalPromotionGate(store).evaluate(
            provider="ollama", task=_TASK, is_local=True, now=_NOW
        )
        self.assertFalse(decision.eligible)
        self.assertTrue(any("実測ではない" in r for r in decision.reasons))

    def test_a_cloud_provider_is_never_promoted_as_local(self) -> None:
        store = BenchmarkEvidenceStore()
        store.record(_run("gemini"))
        decision = LocalPromotionGate(store).evaluate(
            provider="gemini", task=_TASK, is_local=False, now=_NOW
        )
        self.assertFalse(decision.eligible)


class TestTheGateIsAllOrNothing(unittest.TestCase):
    """**1つでも欠けたら通さない。** 「だいたい満たしている」で通すと、
    何が理由で通ったのか後から分からなくなる。"""

    def setUp(self) -> None:
        self.store = BenchmarkEvidenceStore()

    def _decide(self, **overrides):  # noqa: ANN202
        self.store.record(_run("ollama", **overrides))
        return LocalPromotionGate(self.store).evaluate(
            provider="ollama", task=_TASK, is_local=True, now=_NOW
        )

    def test_a_fully_qualified_local_is_eligible(self) -> None:
        decision = self._decide()
        self.assertTrue(decision.eligible, decision.reasons)
        self.assertEqual(decision.reasons, ())

    def test_low_task_accuracy_blocks(self) -> None:
        decision = self._decide(task_accuracy=0.60)
        self.assertFalse(decision.eligible)
        self.assertTrue(any("製品水準" in r for r in decision.reasons))

    def test_low_schema_success_blocks(self) -> None:
        decision = self._decide(schema_valid_rate=0.50)
        self.assertFalse(decision.eligible)

    def test_slow_response_blocks_even_when_quality_is_good(self) -> None:
        """品質が足りていても、遅すぎれば製品として使えない。"""
        decision = self._decide(task_accuracy=0.99, latency_p50_ms=30_000.0)
        self.assertFalse(decision.eligible)
        self.assertTrue(any("遅すぎる" in r for r in decision.reasons))

    def test_an_unrecorded_latency_blocks(self) -> None:
        """**「記録されていない」を「速い」と読まない。**"""
        decision = self._decide(latency_p50_ms=0.0)
        self.assertFalse(decision.eligible)

    def test_too_few_samples_block(self) -> None:
        decision = self._decide(dataset_size=3)
        self.assertFalse(decision.eligible)

    def test_a_missing_dataset_hash_blocks(self) -> None:
        """同一性を照合できないDatasetの数字で昇格しない（011 §3）。"""
        decision = self._decide(dataset_hash="")
        self.assertFalse(decision.eligible)

    def test_a_stale_measurement_blocks(self) -> None:
        decision = self._decide(recorded_at=_NOW - 400 * 24 * 3600)
        self.assertFalse(decision.eligible)

    def test_the_caller_can_tighten_the_latency_budget(self) -> None:
        self.store.record(_run("ollama", latency_p50_ms=900.0))
        gate = LocalPromotionGate(self.store)
        self.assertTrue(
            gate.evaluate(provider="ollama", task=_TASK, is_local=True, now=_NOW).eligible
        )
        self.assertFalse(
            gate.evaluate(
                provider="ollama", task=_TASK, is_local=True, now=_NOW,
                latency_budget_ms=100.0,
            ).eligible
        )


class TestLocalFirstIsActuallyLocalFirst(unittest.TestCase):
    """**Best Score Wins をやめたこと**を固定する（017A §7）。"""

    def test_a_qualified_local_wins_even_when_cloud_scores_higher(self) -> None:
        """Cloudの方が点は上だが、Localは製品水準を満たしている。

        `Best Score Wins`なら毎回Cloudが選ばれ、Localは永久に使われない。
        """
        store = BenchmarkEvidenceStore()
        store.record(_run("ollama", task_accuracy=0.91))
        store.record(_run("gemini", task_accuracy=0.97))

        promoted = LocalPromotionGate(store).promoted_providers(
            _TASK, [("gemini", False), ("ollama", True)], now=_NOW
        )
        self.assertEqual(promoted, ("ollama",))

    def test_an_unqualified_local_is_not_promoted_even_if_it_is_local(self) -> None:
        store = BenchmarkEvidenceStore()
        store.record(_run("ollama", task_accuracy=0.40))
        store.record(_run("gemini", task_accuracy=0.97))

        promoted = LocalPromotionGate(store).promoted_providers(
            _TASK, [("gemini", False), ("ollama", True)], now=_NOW
        )
        self.assertEqual(promoted, ())

    def test_the_gate_does_not_rank_providers(self) -> None:
        """**責務を混ぜない**（017A §8）。ここは「昇格するか」だけを
        答える。順位付けは`AIRouter`の仕事である。"""
        for forbidden in ("rank", "ranking_for", "order", "sort_providers", "best"):
            self.assertFalse(
                hasattr(LocalPromotionGate, forbidden),
                f"LocalPromotionGate に {forbidden} が生えている（順位付けはRouterの仕事）",
            )

    def test_a_decision_always_explains_itself(self) -> None:
        """理由を返さないと、設定した人が何を直せばよいか分からない。"""
        decision = LocalPromotionGate(BenchmarkEvidenceStore()).evaluate(
            provider="ollama", task=_TASK, is_local=True, now=_NOW
        )
        self.assertTrue(decision.reasons)
        self.assertIn("reasons", decision.to_dict())


class TestTheRouterActuallyConsultsTheGate(unittest.TestCase):
    """**本番のRoutingが実際にGateを通ること**（`CLAUDE.md` §3）。

    Gateを作っただけでRouterが見なければ、それは置物である。
    Forgeはこの形で5回失敗している。
    """

    def _router(self, store: BenchmarkEvidenceStore):  # noqa: ANN202
        from app.ai.gateway.ai_router import AIRouter, ModelDescriptor

        catalog = (
            ModelDescriptor(provider="gemini", is_local=False),
            ModelDescriptor(provider="ollama", is_local=True),
        )
        return AIRouter(
            resolve=lambda name: None, catalog=catalog,
            evidence=store, now=lambda: _NOW,
        )

    def test_a_qualified_local_is_ordered_first(self) -> None:
        store = BenchmarkEvidenceStore()
        store.record(_run("ollama", task_accuracy=0.91))
        store.record(_run("gemini", task_accuracy=0.97))

        router = self._router(store)
        ordered = router._order(list(router._catalog), _TASK)

        self.assertEqual(
            ordered[0].provider, "ollama",
            "製品水準を満たしたLocalが先頭に来ていない（Local Firstが効いていない）",
        )

    def test_an_unqualified_local_is_not_ordered_first(self) -> None:
        store = BenchmarkEvidenceStore()
        store.record(_run("ollama", task_accuracy=0.30))
        store.record(_run("gemini", task_accuracy=0.97))

        router = self._router(store)
        ordered = router._order(list(router._catalog), _TASK)

        self.assertEqual(
            ordered[0].provider, "gemini",
            "未達のLocalが優先されている（測っていない品質を賭けている）",
        )

    def test_with_no_measurements_nothing_changes(self) -> None:
        """**いまは何も変わらない**——Localの実測が1件も無いため。

        配線済み・データ待ちの状態にしてある（`_order()`と同じ方針）。
        """
        router = self._router(BenchmarkEvidenceStore())
        ordered = router._order(list(router._catalog), _TASK)
        self.assertEqual([m.provider for m in ordered], ["gemini", "ollama"])


if __name__ == "__main__":
    unittest.main()
