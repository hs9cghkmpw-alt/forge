"""FORGE-019C — Revision を**本当に閉じる**ための回帰。

---

## このファイルも「先に落とす」ために書いた

独立レビューが 019B に対して挙げた A/B/C は、いずれも**現在のコードで
再現できる**。直す前にここへ再現を置き、FAIL を確かめてから実装を変えた。

| 指摘 | いま起きること |
|---|---|
| A | `advance_to_revision()` が落ちると、**CORRECTED の Feedback と Learning だけ残る** |
| B | Learning への投影が落ちると、**確定済みの Revision が API 失敗になる** |
| C | 「単一プロセスだから割り込まない」は**成り立たない**（FastAPI の sync def は thread pool） |

## A が「部分的に残る」となぜ困るのか

`RevisionRecord` が無いのに `CORRECTED` だけが残ると、019A §4 の join は
**「利用者が直せと言ったが、Forge は何も直していない」**という事実を
記録したことになる。だが実際には Forge は直そうとして落ちただけである。

この差は Dataset の質へ効く。`RE_CORRECTED` / `NO_FEEDBACK` の判定は
Feedback の並びを読むので、**起きていない訂正が並びへ入る**。
"""

from __future__ import annotations

import os
import sys
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

os.environ.setdefault("FORGE_FEATURE_WORKSPACE", "true")
os.environ.setdefault("FORGE_FEATURE_FOLDER", "true")

from app.ai.gateway.artifact_feedback import (  # noqa: E402
    default_artifact_registry,
    default_feedback_log,
)
from app.ai.gateway.generation_evidence import default_generation_store  # noqa: E402
from app.ai.gateway.learning_events import default_learning_event_service  # noqa: E402
from app.ai.gateway.revision_evidence import default_revision_store  # noqa: E402
from app.ai.runtime.revision_service import (  # noqa: E402
    default_replay_log,
    default_revision_service,
)

try:
    from fastapi.testclient import TestClient

    from app.main import app

    from tests.revision_fixtures import provision_artifact

    _FASTAPI_AVAILABLE = True
except ImportError:  # pragma: no cover
    _FASTAPI_AVAILABLE = False


_LOCAL_INTENT = "収入をもっと目立たせて"
_OTHER_INTENT = "支出をもっと目立たせて"


def _forced_race_window(participants: int, *, timeout: float = 1.0):
    """**競合を偶然に任せない。**

    ---

    ## 「同時に開始する」だけでは競合しなかった

    最初に書いた版は barrier で開始を揃えるだけだった。それでも
    1件しか commit されず、**壊れているのに PASS した**。理由は偶然で
    ある——`admit()` も `record()` も現在の版を読み直すので、片方が
    先に版を進め終えていれば、もう片方はそこで落ちる。

    しかしそれは**順序が良かっただけ**で、保証ではない。独立レビュー C
    はまさにここを指している。検査と更新の間はどれも隙間である。

        A.admit → A.record → A.feedback → | A.advance
        B.admit → B.record → B.feedback → | B.advance
                                          ↑ ここまで両方来られる

    そこで**版を進める直前**で落ち合わせる。両方が「書いてよい」と
    言われ、評価も書き終えた状態から同時に進めば、blind overwrite が
    必ず起きる。

    ## 直したあとも成立させる

    直列化したあとは、2本目は lock の手前で待つのでここへ来ない
    ——barrier は永久に揃わない。だから**待ち時間を区切る**。
    時間切れなら barrier は壊れ、以後の `wait()` は素通りする。

    「競合できるなら必ず競合させる。できないなら止めない」という形。
    """
    from app.ai.gateway.artifact_feedback import ArtifactRegistry

    barrier = threading.Barrier(participants)
    original = ArtifactRegistry.advance_to_revision

    def rendezvous(self, **kwargs):  # noqa: ANN001, ANN003, ANN202
        try:
            barrier.wait(timeout=timeout)
        except threading.BrokenBarrierError:
            pass
        return original(self, **kwargs)

    return patch.object(ArtifactRegistry, "advance_to_revision", rendezvous)


@unittest.skipUnless(_FASTAPI_AVAILABLE, "fastapi/pydanticが無い環境ではスキップする")
class _RevisionCase(unittest.TestCase):
    def setUp(self) -> None:
        for store in (
            default_generation_store(), default_revision_store(),
            default_artifact_registry(), default_feedback_log(),
            default_learning_event_service(), default_replay_log(),
        ):
            store.reset()
        self.client = TestClient(app)

    def provision(self):  # noqa: ANN201
        return provision_artifact(self.client)

    def update(self, artifact, intent: str = _LOCAL_INTENT, **overrides):  # noqa: ANN001, ANN201
        return self.client.post(
            "/api/v1/ai/update", json=artifact.update_payload(intent, **overrides),
        )

    def counts(self) -> dict[str, int]:
        service = default_learning_event_service()
        return {
            "revisions": len(default_revision_store().all_records()),
            "feedback": default_feedback_log().size(),
            "learning": len(service.local_events),
        }

    def token(self, artifact) -> str:  # noqa: ANN001
        return default_artifact_registry().resolve(artifact.artifact_id).version_token


# ---------------------------------------------------------------------------
# A. advance が落ちたら「何も残らない」
# ---------------------------------------------------------------------------


class TestAdvanceFailureLeavesNothing(_RevisionCase):
    """**論理的に失敗した Revision は、部分的な Evidence も残さない。**

    019B は「CORRECTED だけ残る」を仕様として書いていた。追記専用の log は
    巻き戻せない、という理由だった。

    しかし**追記していなければ巻き戻す必要も無い。** 順序を変えれば済む
    ——先に版を進め、確定してから追記する。
    """

    def _inject_advance_failure(self):  # noqa: ANN202
        def _boom(self_registry, **kwargs):  # noqa: ANN001, ARG001
            msg = "advance failed"
            raise RuntimeError(msg)

        return patch(
            "app.ai.gateway.artifact_feedback.ArtifactRegistry.advance_to_revision", _boom,
        )

    def test_nothing_at_all_is_recorded(self) -> None:
        artifact = self.provision()
        before = self.counts()

        with self._inject_advance_failure(), self.assertRaises(RuntimeError):
            self.update(artifact)

        self.assertEqual(
            self.counts(), before,
            "advance が落ちたのに部分的な Evidence が残っている",
        )

    def test_the_artifact_version_does_not_advance(self) -> None:
        artifact = self.provision()
        before = self.token(artifact)

        with self._inject_advance_failure(), self.assertRaises(RuntimeError):
            self.update(artifact)

        self.assertEqual(self.token(artifact), before)

    def test_no_replay_record_is_left_behind(self) -> None:
        """**失敗を「成功として再送に返す」ことがあってはならない。**"""
        artifact = self.provision()

        with self._inject_advance_failure(), self.assertRaises(RuntimeError):
            self.update(artifact, idempotency_key="k-advance-fail")

        self.assertEqual(default_replay_log().size(), 0)

    def test_the_next_attempt_still_works(self) -> None:
        """巻き戻したなら、**やり直せる**はずである。"""
        artifact = self.provision()

        with self._inject_advance_failure(), self.assertRaises(RuntimeError):
            self.update(artifact)

        retry = self.update(artifact)
        self.assertEqual(retry.status_code, 200, retry.text)


# ---------------------------------------------------------------------------
# B. 投影が落ちても、確定した Revision は成功のまま
# ---------------------------------------------------------------------------


class TestProjectionFailureDoesNotFailTheRevision(_RevisionCase):
    """**Learning への投影は、利用者の成功を取り消す理由にならない。**

    投影はネットワークの向こう（将来）にある処理であり、事実の確定とは
    別の寿命を持つ。ここを同じ transaction に入れると、
    「サーバでは成功したが利用者には失敗」が復活する。
    """

    def _inject_projection_failure(self):  # noqa: ANN202
        def _boom(self_service, evidence):  # noqa: ANN001, ARG001
            msg = "projection failed"
            raise RuntimeError(msg)

        return patch(
            "app.ai.gateway.learning_events.LearningEventService.observe", _boom,
        )

    def _inject_publish_failure(self):  # noqa: ANN202
        """**確定後の投影段**で落とす（レビュー指摘 B そのもの）。

        `observe_evidence()` は例外を飲むが、その手前の `publish()` は
        飲まない。事実を全部書き終えてからここが落ちると、
        **サーバでは成功しているのに利用者には失敗**が返る。
        """
        def _boom(self_store, record):  # noqa: ANN001, ARG001
            msg = "publish failed"
            raise RuntimeError(msg)

        return patch(
            "app.ai.gateway.revision_evidence.RevisionEvidenceStore.publish", _boom,
        )

    def test_the_api_still_succeeds(self) -> None:
        artifact = self.provision()
        with self._inject_projection_failure():
            response = self.update(artifact)
        self.assertEqual(response.status_code, 200, response.text)

    def test_a_failing_publish_does_not_fail_the_committed_revision(self) -> None:
        artifact = self.provision()
        with self._inject_publish_failure():
            response = self.update(artifact)
        self.assertEqual(
            response.status_code, 200,
            "確定済みの Revision が投影の失敗で API 失敗になっている",
        )

    def test_a_failing_publish_still_advances_the_artifact_once(self) -> None:
        artifact = self.provision()
        before = self.token(artifact)
        with self._inject_publish_failure():
            self.update(artifact)
        self.assertNotEqual(self.token(artifact), before)
        self.assertEqual(len(default_revision_store().all_records()), 1)

    def test_a_failing_publish_still_remembers_the_replay(self) -> None:
        """**投影が落ちても、再送は replay で返せる**（§4 の切り分け）。"""
        artifact = self.provision()
        with self._inject_publish_failure():
            self.update(artifact, idempotency_key="k-publish-fail")
        self.assertEqual(default_replay_log().size(), 1)

    def test_the_facts_are_committed(self) -> None:
        artifact = self.provision()
        with self._inject_projection_failure():
            self.update(artifact)
        self.assertEqual(len(default_revision_store().all_records()), 1)
        self.assertEqual(default_feedback_log().size(), 1)

    def test_the_projection_is_pending_not_lost(self) -> None:
        """**落ちた投影は「無かったこと」にしない。** 保留として残す。"""
        from app.ai.gateway.learning_outbox import default_projection_outbox

        artifact = self.provision()
        with self._inject_projection_failure():
            self.update(artifact)

        pending = default_projection_outbox().pending()
        self.assertTrue(pending, "投影が落ちたのに outbox が空（黙って捨てている）")
        self.assertTrue(all(entry.attempts >= 1 for entry in pending))

    def test_a_retry_projects_exactly_once(self) -> None:
        from app.ai.gateway.learning_outbox import default_projection_outbox

        artifact = self.provision()
        with self._inject_projection_failure():
            self.update(artifact)

        outbox = default_projection_outbox()
        pending_before = len(outbox.pending())
        self.assertGreater(pending_before, 0)

        projected = outbox.drain()
        self.assertEqual(projected, pending_before)
        self.assertEqual(outbox.pending(), ())

        # **2回目の drain は1件も出さない。** exactly-once 相当。
        events_after_first = len(default_learning_event_service().local_events)
        self.assertEqual(outbox.drain(), 0)
        self.assertEqual(
            len(default_learning_event_service().local_events), events_after_first,
            "retry で Learning Event が二重に出ている",
        )

    def test_the_outbox_never_holds_a_client_handle(self) -> None:
        """Outbox は**capability を持たない**（§6）。"""
        from app.ai.gateway.learning_outbox import default_projection_outbox

        artifact = self.provision()
        self.update(artifact)
        for entry in default_projection_outbox().all_entries():
            rendered = repr(entry.to_dict())
            self.assertNotIn(artifact.artifact_id, rendered)
            self.assertNotIn(artifact.version_token, rendered)


# ---------------------------------------------------------------------------
# C. 並行 Revision
# ---------------------------------------------------------------------------


class TestConcurrentRevisions(_RevisionCase):
    """**同じ版へ同時に2つ**（§7.1）。

    FastAPI の `def`（async でない）endpoint は thread pool で並行に走る。
    「単一プロセスなので割り込まない」は成り立たない。
    """

    def _race(self, artifact, intents):  # noqa: ANN001, ANN202
        start = threading.Barrier(len(intents))
        service = default_revision_service()

        def run(intent: str):  # noqa: ANN202
            start.wait(timeout=10)
            try:
                return service.revise(
                    artifact_id=artifact.artifact_id,
                    seen_version_token=artifact.version_token,
                    document=artifact.document,
                    change_request=intent,
                    idempotency_key="",
                )
            except Exception as error:  # noqa: BLE001 — 拒否も結果である
                return error

        with _forced_race_window(len(intents)), ThreadPoolExecutor(
            max_workers=len(intents)
        ) as pool:
            return list(pool.map(run, intents))

    def test_exactly_one_of_two_concurrent_revisions_commits(self) -> None:
        from app.ai.runtime.revision_service import RevisionOutcome

        artifact = self.provision()
        results = self._race(artifact, [_LOCAL_INTENT, _OTHER_INTENT])
        succeeded = [r for r in results if isinstance(r, RevisionOutcome)]
        self.assertEqual(
            len(succeeded), 1,
            f"同じ版から2つ commit された（lost update / branch lineage）: {results}",
        )

    def test_only_one_revision_record_exists(self) -> None:
        artifact = self.provision()
        self._race(artifact, [_LOCAL_INTENT, _OTHER_INTENT])
        self.assertEqual(len(default_revision_store().all_records()), 1)

    def test_only_one_correction_is_recorded(self) -> None:
        artifact = self.provision()
        self._race(artifact, [_LOCAL_INTENT, _OTHER_INTENT])
        self.assertEqual(default_feedback_log().size(), 1)

    def test_the_artifact_advances_exactly_once(self) -> None:
        artifact = self.provision()
        self._race(artifact, [_LOCAL_INTENT, _OTHER_INTENT])
        handle = default_artifact_registry().resolve(artifact.artifact_id)
        record = default_revision_store().all_records()[0]
        self.assertEqual(handle.evidence_id.uid, record.uid)

    def test_the_lineage_does_not_branch(self) -> None:
        artifact = self.provision()
        self._race(artifact, [_LOCAL_INTENT, _OTHER_INTENT])
        records = default_revision_store().all_records()
        sequences = [r.sequence for r in records]
        self.assertEqual(len(sequences), len(set(sequences)), f"系譜が分岐した: {records}")


class TestConcurrentRetryOfTheSameRequest(_RevisionCase):
    """**同じ論理要求の同時再送**（§7.2）。

    どちらも本処理へ入ってはならない。片方は replay か、
    処理の完了を待って同じ結果を返す。
    """

    def _race_same(self, artifact, workers: int = 2):  # noqa: ANN001, ANN202
        barrier = threading.Barrier(workers)
        service = default_revision_service()

        def run(_: int):  # noqa: ANN202
            barrier.wait(timeout=10)
            try:
                return service.revise(
                    artifact_id=artifact.artifact_id,
                    seen_version_token=artifact.version_token,
                    document=artifact.document,
                    change_request=_LOCAL_INTENT,
                    idempotency_key="same-logical-request",
                )
            except Exception as error:  # noqa: BLE001
                return error

        with _forced_race_window(workers), ThreadPoolExecutor(
            max_workers=workers
        ) as pool:
            return list(pool.map(run, range(workers)))

    def test_both_callers_see_the_same_outcome(self) -> None:
        from app.ai.runtime.revision_service import RevisionOutcome

        artifact = self.provision()
        results = self._race_same(artifact)
        self.assertTrue(
            all(isinstance(r, RevisionOutcome) for r in results),
            f"同時再送の片方が失敗した: {results}",
        )
        self.assertEqual(results[0].record.uid, results[1].record.uid)

    def test_only_one_revision_is_recorded(self) -> None:
        artifact = self.provision()
        self._race_same(artifact)
        self.assertEqual(len(default_revision_store().all_records()), 1)

    def test_only_one_correction_is_recorded(self) -> None:
        artifact = self.provision()
        self._race_same(artifact)
        self.assertEqual(default_feedback_log().size(), 1)

    def test_only_one_revision_learning_event(self) -> None:
        from app.ai.gateway.learning_contract import LearningEventType

        artifact = self.provision()
        self._race_same(artifact)
        revisions = [
            e for e in default_learning_event_service().local_events
            if e.event_type is LearningEventType.REVISION
        ]
        self.assertEqual(len(revisions), 1)


# ---------------------------------------------------------------------------
# §7.3 Artifact CAS
# ---------------------------------------------------------------------------


class TestArtifactCompareAndSwap(_RevisionCase):
    """**blind overwrite にしない。**"""

    def test_advancing_with_a_stale_expectation_is_refused(self) -> None:
        from app.ai.gateway.artifact_feedback import ArtifactCasConflict

        artifact = self.provision()
        registry = default_artifact_registry()
        stale = registry.resolve(artifact.artifact_id)

        self.assertEqual(self.update(artifact).status_code, 200)

        with self.assertRaises(ArtifactCasConflict):
            registry.advance_to_revision(
                handle=artifact.artifact_id, revision_ref=999, revision_uid="forged",
                document=artifact.document, expected=stale,
            )

    def test_advancing_without_an_expectation_is_refused(self) -> None:
        """**期待値を渡さない呼び出しは通さない**（fail closed）。"""
        from app.ai.gateway.artifact_feedback import ArtifactCasConflict

        artifact = self.provision()
        with self.assertRaises(ArtifactCasConflict):
            default_artifact_registry().advance_to_revision(
                handle=artifact.artifact_id, revision_ref=999, revision_uid="forged",
                document=artifact.document, expected=None,
            )


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
