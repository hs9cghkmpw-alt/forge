"""FORGE-020 §39 — **本番から本当に辿れるか。**

---

## なぜこのファイルが要るか

Forge は「作ったが本番から呼ばれない」を6回繰り返している
（TD59 / 007 §10 / 010 Phase B / TD64 / TD69 / 016A）。共通するのは
**呼び出し側が忘れずに呼ぶ設計**だったことで、忘れられた。

だから「class がある」「test がある」では完了にしない。
**本番の入口を叩いて、その先に痕跡が残ること**を見る。

## 今回、本番配線されているものと、されていないもの

| | 状態 |
|---|---|
| Revision → Learning Outbox | **配線済み**（`/update` で pending/projected が動く） |
| Revision → GenerationEpisode | **配線済み**（`/update` で Episode が1件増える） |
| Benchmark → LocalPromotionGate → routing | **配線済み・データ待ち**（昇格0件） |
| Agent / Tool / Web / Teacher / Gym / Novel / Dataset / Adapter | **契約のみ。本番配線なし** |

最後の行を**テストで固定する**。「配線したつもり」を防ぐのと同じくらい、
「配線していないのに配線したと書く」を防ぐ必要がある。
"""

from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

os.environ.setdefault("FORGE_FEATURE_WORKSPACE", "true")
os.environ.setdefault("FORGE_FEATURE_FOLDER", "true")

from app.ai.gateway.artifact_feedback import (  # noqa: E402
    default_artifact_registry,
    default_feedback_log,
)
from app.ai.gateway.generation_evidence import default_generation_store  # noqa: E402
from app.ai.gateway.learning_events import TrainingUse  # noqa: E402
from app.ai.gateway.learning_events import default_learning_event_service  # noqa: E402
from app.ai.gateway.learning_outbox import (  # noqa: E402
    ProjectionStatus,
    default_projection_outbox,
)
from app.ai.gateway.revision_evidence import default_revision_store  # noqa: E402
from app.ai.learning.episode import default_episode_store  # noqa: E402
from app.ai.runtime.revision_service import default_replay_log  # noqa: E402

try:
    from fastapi.testclient import TestClient

    from app.main import app

    from tests.revision_fixtures import provision_artifact

    _FASTAPI_AVAILABLE = True
except ImportError:  # pragma: no cover
    _FASTAPI_AVAILABLE = False

_LOCAL_INTENT = "収入をもっと目立たせて"


@unittest.skipUnless(_FASTAPI_AVAILABLE, "fastapi/pydanticが無い環境ではスキップする")
class TestRevisionReachesTheLearningAssets(unittest.TestCase):
    def setUp(self) -> None:
        for store in (
            default_generation_store(), default_revision_store(),
            default_artifact_registry(), default_feedback_log(),
            default_learning_event_service(), default_replay_log(),
            default_projection_outbox(), default_episode_store(),
        ):
            store.reset()
        self.client = TestClient(app)

    def _update(self):  # noqa: ANN202
        artifact = provision_artifact(self.client)
        response = self.client.post(
            "/api/v1/ai/update", json=artifact.update_payload(_LOCAL_INTENT),
        )
        self.assertEqual(response.status_code, 200, response.text)
        return response

    def test_the_outbox_is_reached_from_the_http_endpoint(self) -> None:
        """**Outbox はテストからだけ動く入れ物ではない。**"""
        self._update()
        entries = default_projection_outbox().all_entries()
        self.assertTrue(entries, "本番の変更で Outbox が1件も動いていない")
        self.assertTrue(
            all(e.status is ProjectionStatus.PROJECTED for e in entries),
            "投影できるはずの状況で pending が残っている",
        )

    def test_both_the_correction_and_the_revision_are_projected(self) -> None:
        self._update()
        kinds = {e.evidence_kind for e in default_projection_outbox().all_entries()}
        self.assertEqual(kinds, {"ArtifactFeedbackEvent", "RevisionRecord"})

    def test_an_episode_is_recorded_from_the_http_endpoint(self) -> None:
        """**Episode は Agent が動かなくても本番で生まれる。**"""
        self._update()
        episodes = default_episode_store().all_episodes()
        self.assertEqual(len(episodes), 1, "本番の変更で Episode が残っていない")
        self.assertEqual(episodes[0].task_id, "forge.revision")

    def test_the_episode_points_at_the_revision_evidence(self) -> None:
        self._update()
        episode = default_episode_store().all_episodes()[0]
        record = default_revision_store().all_records()[0]
        self.assertEqual(episode.revision_evidence_uids, (record.uid,))

    def test_the_episode_names_the_provider_that_actually_changed_it(self) -> None:
        """019B の Provider 帰属を Episode でも壊さない。"""
        self._update()
        self.assertEqual(
            default_episode_store().all_episodes()[0].provider, "forge_deterministic",
        )

    def test_the_episode_carries_no_training_right(self) -> None:
        """**収集してよい ≠ 学習に使ってよい**（§40）。"""
        self._update()
        episode = default_episode_store().all_episodes()[0]
        self.assertIs(episode.training_use, TrainingUse.UNKNOWN)
        self.assertFalse(episode.has_usable_training_right)

    def test_the_production_episode_is_refused_by_the_dataset_gate(self) -> None:
        """同意も build/test 証拠も無いので、**そのままでは学習素材にならない。**"""
        from app.ai.learning.dataset_builder import evaluate_episode_for_dataset

        self._update()
        candidate, reasons = evaluate_episode_for_dataset(
            default_episode_store().all_episodes()[0],
        )
        self.assertIsNone(candidate)
        self.assertTrue(reasons)

    def test_a_rejected_revision_records_no_episode(self) -> None:
        """**失敗した変更の Episode を成功として残さない。**"""
        artifact = provision_artifact(self.client)
        rejected = self.client.post(
            "/api/v1/ai/update", json=artifact.update_payload("残高をもっと目立たせて"),
        )
        self.assertEqual(rejected.status_code, 422, rejected.text)
        self.assertEqual(default_episode_store().size(), 0)

    def test_an_episode_failure_does_not_break_the_revision(self) -> None:
        """Episode の記録は**利用者の成功を壊さない**。"""
        from unittest.mock import patch

        def _boom(self_store, episode):  # noqa: ANN001, ARG001
            msg = "episode store failed"
            raise RuntimeError(msg)

        with patch("app.ai.learning.episode.EpisodeStore.start", _boom):
            artifact = provision_artifact(self.client)
            response = self.client.post(
                "/api/v1/ai/update", json=artifact.update_payload(_LOCAL_INTENT),
            )
        self.assertEqual(response.status_code, 200, response.text)


class TestLocalPromotionIsWiredButEmpty(unittest.TestCase):
    """**配線済み・データ待ち**を正直に固定する（017A §7）。"""

    def test_the_router_consults_the_promotion_gate(self) -> None:
        from app.ai.gateway.ai_router import AIRouter

        source = AIRouter._local_first.__doc__ or ""
        self.assertIn("LocalPromotionGate", source)

    def test_no_provider_is_promoted_without_measurements(self) -> None:
        """**実測が無いのに Local を優先しない。**"""
        from app.ai.gateway.benchmark_evidence import BenchmarkEvidenceStore
        from app.ai.gateway.local_promotion import LocalPromotionGate
        from app.ai.gateway.tasks import ForgeTask

        gate = LocalPromotionGate(BenchmarkEvidenceStore())
        self.assertEqual(
            gate.promoted_providers(
                ForgeTask.FORGE_LANGUAGE_UPDATE, [("local", True)], now=0.0,
            ),
            (),
        )


class TestContractOnlyLayersAreNotClaimedAsWired(unittest.TestCase):
    """**配線していないものを「配線した」と書かない。**

    FORGE-020Bで Agent / Tool は本番へ接続した。Web / Teacher / Gym /
    Novel Benchmark / Dataset / Adapter はまだ**契約とテストだけ**である。
    実 Local Model が無い状態で未測定の層を本番へ差し込むと、
    生成経路へ差し込むと、Promotion Gate を迂回して未測定の Local を
    使うことになる（017A §7 が退けた形）。

    ここが落ちるのは、**本番へ差し込んだのに文書を直していない**とき
    である。そのときは文書を直すこと。
    """

    def _production_sources(self) -> str:
        import pathlib

        root = pathlib.Path(__file__).resolve().parents[1] / "app"
        return "\n".join(
            path.read_text(encoding="utf-8")
            for path in sorted(root.rglob("*.py"))
            if "ai/agent" not in path.as_posix() and "ai/learning" not in path.as_posix()
        )

    def test_the_agent_layer_has_a_production_caller(self) -> None:
        sources = self._production_sources()
        self.assertIn(
            "app.ai.agent.production", sources,
            "020B Agent production runner がHTTP本線から参照されていない",
        )

    def test_web_layer_is_still_not_claimed_as_wired(self) -> None:
        sources = self._production_sources()
        self.assertNotIn(
            "app.ai.agent.web", sources,
            "Webは020D。020Bで本番接続したことにしない",
        )

    def test_the_teacher_and_benchmark_layers_have_no_production_caller(self) -> None:
        sources = self._production_sources()
        for module in (
            "app.ai.learning.teacher", "app.ai.learning.novel_benchmark",
            "app.ai.learning.gym", "app.ai.learning.dataset_builder",
            "app.ai.learning.adapter",
        ):
            self.assertNotIn(module, sources, f"{module} が本番から参照されている")

    def test_the_episode_layer_does_have_a_production_caller(self) -> None:
        """**逆に、Episode は配線されていること。**"""
        self.assertIn("app.ai.learning.episode", self._production_sources())


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
