"""FORGE-019C §6・§7.3・§8 — Outbox / CAS / lock / 予約 の単体回帰。

エンドツーエンドの回帰は `test_forge_019c_revision_closure.py` にある。
ここは**部品そのものの契約**を固定する。
"""

from __future__ import annotations

import os
import sys
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from app.ai.gateway.artifact_feedback import (  # noqa: E402
    ArtifactCasConflict,
    ArtifactEvidenceId,
    ArtifactRegistry,
    EvidenceKind,
)
from app.ai.gateway.generation_evidence import (  # noqa: E402
    GenerationRecord,
    GenerationSource,
)
from app.ai.gateway.learning_outbox import (  # noqa: E402
    LearningProjectionOutbox,
    ProjectionStatus,
)
from app.ai.gateway.revision_evidence import RevisionRecord  # noqa: E402


class _CountingService:
    """`LearningEventService` の代わり。**何回投影されたか**だけ数える。"""

    def __init__(self, *, fail_times: int = 0) -> None:
        self.calls = 0
        self._fail_times = fail_times

        class _Diag:
            failure_count = 0

            def record_failure(self, error: Exception) -> None:  # noqa: ANN001, ARG002
                self.failure_count += 1

        self.diagnostics = _Diag()

    def observe(self, evidence: object) -> object:  # noqa: ANN401
        self.calls += 1
        if self._fail_times > 0:
            self._fail_times -= 1
            msg = "projection failed"
            raise RuntimeError(msg)
        return evidence


class _OutboxCase(unittest.TestCase):
    def setUp(self) -> None:
        self.outbox = LearningProjectionOutbox()
        self.service = _CountingService()
        self._install(self.service)

    def _install(self, service: object) -> None:
        from app.ai.gateway import learning_events

        self._original = learning_events.default_learning_event_service
        learning_events.default_learning_event_service = lambda: service  # type: ignore[assignment]
        self.addCleanup(self._restore)

    def _restore(self) -> None:
        from app.ai.gateway import learning_events

        learning_events.default_learning_event_service = self._original  # type: ignore[assignment]

    @staticmethod
    def _revision(uid: str = "rev-1") -> RevisionRecord:
        return RevisionRecord(base_generation_ref=1, uid=uid, ref=1)


class TestOutboxProjectsExactlyOnce(_OutboxCase):
    def test_a_successful_submit_is_projected(self) -> None:
        entry = self.outbox.submit(self._revision())
        assert entry is not None
        self.assertIs(entry.status, ProjectionStatus.PROJECTED)
        self.assertEqual(self.service.calls, 1)

    def test_submitting_the_same_evidence_twice_projects_once(self) -> None:
        record = self._revision()
        self.outbox.submit(record)
        self.outbox.submit(record)
        self.assertEqual(self.service.calls, 1, "同じEvidenceが二重に投影された")
        self.assertEqual(self.outbox.size(), 1)

    def test_draining_a_projected_entry_does_nothing(self) -> None:
        self.outbox.submit(self._revision())
        self.assertEqual(self.outbox.drain(), 0)
        self.assertEqual(self.service.calls, 1)

    def test_different_evidence_gets_its_own_entry(self) -> None:
        self.outbox.submit(self._revision("a"))
        self.outbox.submit(self._revision("b"))
        self.assertEqual(self.outbox.size(), 2)


class TestOutboxRetriesFailures(_OutboxCase):
    def setUp(self) -> None:
        self.outbox = LearningProjectionOutbox()
        self.service = _CountingService(fail_times=1)
        self._install(self.service)

    def test_a_failed_projection_stays_pending(self) -> None:
        entry = self.outbox.submit(self._revision())
        assert entry is not None
        self.assertIs(entry.status, ProjectionStatus.PENDING)
        self.assertEqual(entry.attempts, 1)

    def test_a_retry_succeeds_and_marks_projected(self) -> None:
        self.outbox.submit(self._revision())
        self.assertEqual(self.outbox.drain(), 1)
        self.assertEqual(self.outbox.pending(), ())

    def test_a_retry_does_not_double_project(self) -> None:
        self.outbox.submit(self._revision())
        self.outbox.drain()
        before = self.service.calls
        self.outbox.drain()
        self.assertEqual(self.service.calls, before)

    def test_the_failure_category_is_recorded(self) -> None:
        entry = self.outbox.submit(self._revision())
        assert entry is not None
        self.assertNotEqual(entry.last_error.value, "none")

    def test_enqueue_does_not_attempt(self) -> None:
        """投影の段そのものが落ちた場合、**二度目を走らせない**。"""
        entry = self.outbox.enqueue(self._revision(), error=RuntimeError("boom"))
        assert entry is not None
        self.assertEqual(self.service.calls, 0)
        self.assertIs(entry.status, ProjectionStatus.PENDING)


class TestOutboxHoldsNothingSensitive(_OutboxCase):
    def test_unknown_evidence_types_are_refused(self) -> None:
        """**whitelist に無いものを溜め込まない。**"""

        class _Rogue:
            uid = "x"

        self.assertIsNone(self.outbox.submit(_Rogue()))
        self.assertEqual(self.outbox.size(), 0)

    def test_a_plain_string_is_refused(self) -> None:
        self.assertIsNone(self.outbox.submit("secret-looking-string"))

    def test_the_diagnostic_form_omits_the_payload(self) -> None:
        self.outbox.submit(self._revision())
        for entry in self.outbox.all_entries():
            self.assertNotIn("payload", entry.to_dict())

    def test_generation_records_are_retainable(self) -> None:
        record = GenerationRecord(
            source=GenerationSource.COMPOSITION, domain="finance",
            validator_passed=True, uid="gen-1", ref=1,
        )
        self.assertIsNotNone(self.outbox.submit(record))

    def test_the_payload_is_released_after_projection(self) -> None:
        """投影が終われば retry 用の本体は要らない。**持ち続けない。**"""
        entry = self.outbox.submit(self._revision())
        assert entry is not None
        self.assertIsNone(entry.payload)


class TestArtifactCas(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = ArtifactRegistry()
        self.document = {"version": "1.0", "screens": []}
        self.handle = self.registry.register(
            generation_ref=1, generation_uid="gen-1", document=self.document,
        )

    def test_a_matching_expectation_advances(self) -> None:
        advanced = self.registry.advance_to_revision(
            handle=self.handle.handle, revision_ref=1, revision_uid="rev-1",
            document={"version": "1.1"}, expected=self.handle,
        )
        self.assertNotEqual(advanced.version_token, self.handle.version_token)

    def test_a_missing_expectation_is_refused(self) -> None:
        with self.assertRaises(ArtifactCasConflict):
            self.registry.advance_to_revision(
                handle=self.handle.handle, revision_ref=1, revision_uid="rev-1",
                document={"version": "1.1"}, expected=None,
            )

    def test_a_stale_version_token_is_refused(self) -> None:
        self.registry.advance_to_revision(
            handle=self.handle.handle, revision_ref=1, revision_uid="rev-1",
            document={"version": "1.1"}, expected=self.handle,
        )
        with self.assertRaises(ArtifactCasConflict):
            self.registry.advance_to_revision(
                handle=self.handle.handle, revision_ref=2, revision_uid="rev-2",
                document={"version": "1.2"}, expected=self.handle,
            )

    def test_a_forged_lineage_is_refused(self) -> None:
        """`version_token` だけ合わせても通さない（3値すべて見る）。"""
        from dataclasses import replace

        forged = replace(
            self.handle,
            evidence_id=ArtifactEvidenceId(EvidenceKind.REVISION, "someone-elses", 99),
        )
        with self.assertRaises(ArtifactCasConflict):
            self.registry.advance_to_revision(
                handle=self.handle.handle, revision_ref=1, revision_uid="rev-1",
                document={"version": "1.1"}, expected=forged,
            )

    def test_a_forged_document_binding_is_refused(self) -> None:
        from dataclasses import replace

        forged = replace(self.handle, document_binding="0" * 64)
        with self.assertRaises(ArtifactCasConflict):
            self.registry.advance_to_revision(
                handle=self.handle.handle, revision_ref=1, revision_uid="rev-1",
                document={"version": "1.1"}, expected=forged,
            )

    def test_restore_puts_the_previous_version_back(self) -> None:
        self.registry.advance_to_revision(
            handle=self.handle.handle, revision_ref=1, revision_uid="rev-1",
            document={"version": "1.1"}, expected=self.handle,
        )
        self.registry.restore(self.handle)
        self.assertEqual(
            self.registry.resolve(self.handle.handle).version_token,
            self.handle.version_token,
        )


class TestPerArtifactLock(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = ArtifactRegistry()

    def _register(self, uid: str):  # noqa: ANN202
        return self.registry.register(
            generation_ref=1, generation_uid=uid, document={"uid": uid},
        )

    def test_the_lock_table_does_not_grow(self) -> None:
        """**無限増殖しない。** 使い終わったら消える。"""
        handle = self._register("a")
        for _ in range(50):
            with self.registry.lock_for(handle.handle):
                pass
        self.assertEqual(self.registry.lock_table_size(), 0)

    def test_the_lock_is_released_on_exception(self) -> None:
        handle = self._register("a")
        with self.assertRaises(ValueError), self.registry.lock_for(handle.handle):
            raise ValueError
        self.assertEqual(self.registry.lock_table_size(), 0)
        # もう一度取れる＝解放されている
        with self.registry.lock_for(handle.handle):
            pass

    def test_the_same_artifact_is_serialized(self) -> None:
        handle = self._register("a")
        order: list[str] = []
        gate = threading.Event()

        def first() -> None:
            with self.registry.lock_for(handle.handle):
                order.append("first-in")
                gate.set()
                threading.Event().wait(0.05)
                order.append("first-out")

        def second() -> None:
            gate.wait(timeout=2)
            with self.registry.lock_for(handle.handle):
                order.append("second-in")

        with ThreadPoolExecutor(max_workers=2) as pool:
            pool.submit(first)
            pool.submit(second)
        self.assertEqual(order, ["first-in", "first-out", "second-in"])

    def test_different_artifacts_are_not_serialized(self) -> None:
        """**global lock にしない。** 無関係な生成物を待たせない。"""
        a = self._register("a")
        b = self._register("b")
        both_inside = threading.Barrier(2)

        def hold(handle_id: str) -> bool:
            with self.registry.lock_for(handle_id):
                try:
                    both_inside.wait(timeout=1.0)
                except threading.BrokenBarrierError:
                    return False
                return True

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(hold, [a.handle, b.handle]))
        self.assertTrue(all(results), "別々の生成物が直列化されている")


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
