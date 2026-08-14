"""Benchmark Evidence と 品質による並べ替え
(FORGE-AI-FOUNDATION-010 Phase J、2026-08-13)。

守っているのは1つのことである:

    **測っていないものでProduction Routingを決めない。**

Test Doubleは「常に正解するAdapter」をいくらでも作れる。それを
Benchmarkに通せば`task_accuracy = 1.0`が出る。その数字が本番の
Provider選択へ流れ込むと、**測っていないものを測ったことにして**
経路が決まる。`Verification`はそれを型で塞ぐためにある。
"""

from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from app.ai.gateway.ai_router import AIRouter, ModelDescriptor  # noqa: E402
from app.ai.gateway.benchmark_evidence import (  # noqa: E402
    BenchmarkEvidenceStore,
    BenchmarkRun,
    Verification,
)
from app.ai.gateway.tasks import ForgeTask  # noqa: E402

_TASK = ForgeTask.CONVERSATION_STEP
# 実際のepoch秒に近い値にしておく。小さい値だと「30日前」が負になり、
# `record()`が「時刻未設定」と見なして今の時刻を入れてしまうため、
# 鮮度のテストが**通ってしまう**(最初この形で書いて気付いた)。
_NOW = 1_800_000_000.0


def _run(provider: str, *, accuracy: float = 0.9, **overrides) -> BenchmarkRun:
    defaults = {
        "task": _TASK,
        "provider": provider,
        "model": f"{provider}-model-1",
        "dataset_id": "impact-v1",
        "dataset_size": 16,
        "verification": Verification.REAL,
        "task_accuracy": accuracy,
        "schema_valid_rate": 1.0,
        "latency_p50_ms": 100.0,
        "recorded_at": _NOW,
    }
    return BenchmarkRun(**{**defaults, **overrides})


def _store() -> BenchmarkEvidenceStore:
    return BenchmarkEvidenceStore(now=lambda: _NOW)


class TestOnlyRealMeasurementsCanDecideRouting(unittest.TestCase):
    """`Verification`が本番経路への関門である。"""

    def test_two_real_measurements_produce_a_ranking(self) -> None:
        store = _store()
        store.record(_run("slow_but_right", accuracy=0.95))
        store.record(_run("fast_but_wrong", accuracy=0.40))
        self.assertEqual(store.ranking_for(_TASK), ("slow_but_right", "fast_but_wrong"))

    def test_test_double_measurements_never_produce_a_ranking(self) -> None:
        """**このテストが一番重要である。**

        Doubleは`task_accuracy=1.0`をいくらでも作れる。それが
        Routingへ効いてしまうと、本番の経路が「テストの都合」で決まる。
        """
        store = _store()
        store.record(_run("a", accuracy=1.0, verification=Verification.DOUBLE))
        store.record(_run("b", accuracy=1.0, verification=Verification.DOUBLE))
        self.assertIsNone(store.ranking_for(_TASK))

    def test_unverified_is_the_default(self) -> None:
        """出所が分からないものを「実測」へ格上げしない。"""
        run = BenchmarkRun(
            task=_TASK, provider="x", model="m", dataset_id="d", dataset_size=100
        )
        self.assertIs(run.verification, Verification.UNVERIFIED)
        self.assertFalse(run.is_usable_for_routing(now=_NOW))

    def test_a_fixture_replay_is_not_a_current_measurement(self) -> None:
        """記録済み応答の再生は回帰検出には使えるが、**今の**Providerの
        実力ではない(モデルは黙って差し替わる)。"""
        store = _store()
        store.record(_run("a", verification=Verification.FIXTURE))
        store.record(_run("b", verification=Verification.FIXTURE))
        self.assertIsNone(store.ranking_for(_TASK))

    def test_a_small_dataset_is_not_enough(self) -> None:
        store = _store()
        store.record(_run("a", dataset_size=3, accuracy=1.0))
        store.record(_run("b", dataset_size=3, accuracy=0.0))
        self.assertIsNone(store.ranking_for(_TASK))

    def test_a_stale_measurement_is_not_used(self) -> None:
        """Providerはモデルを黙って差し替える。古い記録で今日を決めない。"""
        store = _store()
        store.record(_run("a", recorded_at=_NOW - 60 * 24 * 3600))
        store.record(_run("b", recorded_at=_NOW - 60 * 24 * 3600))
        self.assertIsNone(store.ranking_for(_TASK))

    def test_one_provider_alone_is_not_a_ranking(self) -> None:
        """「唯一測ったものが最良」は、測っていないものについての主張。"""
        store = _store()
        store.record(_run("only_one"))
        self.assertIsNone(store.ranking_for(_TASK))

    def test_it_says_why_a_ranking_is_missing(self) -> None:
        """理由を言えないと運用者は直せない。"""
        store = _store()
        store.record(_run("a", verification=Verification.DOUBLE))
        store.record(_run("b", dataset_size=2))
        reasons = " / ".join(store.exclusion_reasons(_TASK))
        self.assertIn("実測ではない", reasons)
        self.assertIn("件数不足", reasons)

    def test_an_empty_store_says_there_is_nothing_yet(self) -> None:
        self.assertTrue(_store().exclusion_reasons(_TASK))

    def test_rankings_are_per_task(self) -> None:
        """§3「GeminiとLocalのどちらが優秀か」という粗い比較を禁じている。
        記録もRoutingもTask単位でしか成立しない。"""
        store = _store()
        store.record(_run("a"))
        store.record(_run("b"))
        self.assertIsNotNone(store.ranking_for(_TASK))
        self.assertIsNone(store.ranking_for(ForgeTask.FORGE_LANGUAGE_UPDATE))

    def test_a_later_measurement_replaces_the_earlier_one(self) -> None:
        store = _store()
        store.record(_run("a", accuracy=0.2))
        store.record(_run("b", accuracy=0.5))
        self.assertEqual(store.ranking_for(_TASK), ("b", "a"))
        store.record(_run("a", accuracy=0.9))
        self.assertEqual(store.ranking_for(_TASK), ("a", "b"))


class TestTheRouterUsesTheRankingWhenItExists(unittest.TestCase):
    """配線の確認。**「基盤はあるが本番では使っていない」を作らない。**"""

    _CATALOG = (
        ModelDescriptor(provider="declared_first", is_local=False),
        ModelDescriptor(provider="declared_second", is_local=False),
    )

    def _router(self, store: BenchmarkEvidenceStore | None) -> AIRouter:
        return AIRouter(
            resolve=lambda name: None, catalog=self._CATALOG,
            evidence=store, now=lambda: _NOW,
        )

    def test_without_measurements_the_declaration_order_holds(self) -> None:
        candidates, _ = self._router(_store()).candidates_for(_TASK)
        self.assertEqual(
            [m.provider for m in candidates], ["declared_first", "declared_second"]
        )

    def test_real_measurements_actually_reorder_the_candidates(self) -> None:
        """**データを入れれば本当に順序が変わる**こと。

        これを確かめずに「配線済み」と書くと、それこそが
        3度繰り返した失敗になる。
        """
        store = _store()
        store.record(_run("declared_second", accuracy=0.95))
        store.record(_run("declared_first", accuracy=0.30))
        candidates, _ = self._router(store).candidates_for(_TASK)
        self.assertEqual(
            [m.provider for m in candidates], ["declared_second", "declared_first"]
        )

    def test_double_measurements_do_not_reorder_production_routing(self) -> None:
        """Doubleで作った「完璧なProvider」が本番の順序を動かさない。"""
        store = _store()
        store.record(_run("declared_second", accuracy=1.0, verification=Verification.DOUBLE))
        store.record(_run("declared_first", accuracy=0.0, verification=Verification.DOUBLE))
        candidates, _ = self._router(store).candidates_for(_TASK)
        self.assertEqual(
            [m.provider for m in candidates], ["declared_first", "declared_second"]
        )

    def test_an_unmeasured_provider_is_moved_back_not_dropped(self) -> None:
        """測っていないことは、悪いことの証拠ではない。

        候補から**落とす**のは健全性の仕事(除外)であり、
        品質は**順序**にしか使わない。混ぜると、片方がもう片方を
        無効化する(Phase Bで健全性の並べ替えを外したのと同じ理由)。
        """
        catalog = (*self._CATALOG, ModelDescriptor(provider="never_measured", is_local=False))
        store = _store()
        store.record(_run("declared_second", accuracy=0.95))
        store.record(_run("declared_first", accuracy=0.30))
        router = AIRouter(
            resolve=lambda name: None, catalog=catalog, evidence=store, now=lambda: _NOW
        )
        candidates, _ = router.candidates_for(_TASK)
        self.assertEqual(
            [m.provider for m in candidates],
            ["declared_second", "declared_first", "never_measured"],
        )

    def test_a_router_without_an_evidence_store_still_works(self) -> None:
        """Benchmarkを渡さない構成(既存テスト・単体検証)も壊さない。"""
        candidates, _ = self._router(None).candidates_for(_TASK)
        self.assertEqual(
            [m.provider for m in candidates], ["declared_first", "declared_second"]
        )

    def test_the_production_router_is_actually_wired_to_the_store(self) -> None:
        """`default_router()`がBenchmark記録を持っていること。

        持っていなければ、実測を入れても永久に効かない
        ——それが「基盤はあるのに使っていない」の正体である。
        """
        from app.ai.gateway.ai_router import default_router, reset_default_router  # noqa: PLC0415

        reset_default_router()
        try:
            router = default_router()
            self.assertIsNotNone(
                router._evidence,  # noqa: SLF001 — 配線そのものを検査する
                "default_router()がBenchmark記録に繋がっていない",
            )
        finally:
            reset_default_router()


if __name__ == "__main__":
    unittest.main()
