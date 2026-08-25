"""Artifact Feedback / Revision Evidence（FORGE-016A §3・§4、2026-08-24）。

---

## このテストが守っているもの

`AcceptanceSignal`も`note_user_acceptance()`も011から実装されていた。
**しかしそれを呼ぶ経路が本番に1つも無かった。** その結果
`user_acceptance`は永久に`UNKNOWN`であり、明示的な承認を要求する
`is_positive_example`は**構造上、必ずFalse**だった——「教師データを
貯める」と書いてある仕組みが、貯める口を持っていなかった。

Forgeはこの形の失敗を5回繰り返している（TD59 / 007 §10 / 010 Phase B /
TD64 / TD69）。共通するのは「呼び出し側が忘れずに呼ぶ」設計だったこと。
なので**HTTPの往復で実際に記録が残ることを確かめる**テストを置く。
モジュール単体が正しく動くことは、本番から呼ばれる証拠にならない。

## 配線破壊試験（`CLAUDE.md` §3）

このファイルのテストは、次の配線を1つずつ外すと落ちることを確認して
いる（実際に外して確認した。`docs/reports/FORGE-016A-report.md`参照）:

* `_result_dto()`の`artifact=_artifact_ref(...)` → HTTP往復のテストが落ちる
* `ArtifactFeedbackService`の`existing.user_acceptance`検査 → 最初の信号が勝つテストが落ちる
* `fingerprint`照合 → stale拒否のテストが落ちる
"""

from __future__ import annotations

import json
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

os.environ.setdefault("FORGE_FEATURE_WORKSPACE", "true")
os.environ.setdefault("FORGE_FEATURE_FOLDER", "true")

from app.ai.gateway.artifact_feedback import (  # noqa: E402
    ArtifactEvidenceId,
    ArtifactFeedbackService,
    ArtifactHandle,
    ArtifactRegistry,
    EvidenceKind,
    FeedbackEventLog,
    FeedbackRejected,
    FeedbackSource,
    document_fingerprint,
    new_version_token,
)
from app.ai.gateway.generation_evidence import (  # noqa: E402
    DesignDecisionSource,
    GenerationEvidenceStore,
    GenerationRecord,
    GenerationSource,
    RuntimeOutcome,
)
from app.ai.gateway.learning_foundation import AcceptanceSignal  # noqa: E402
from app.ai.gateway.revision_evidence import (  # noqa: E402
    DesignRevision,
    RevisionEvidenceStore,
    RevisionOperationKind,
    RevisionRecord,
)

try:
    from fastapi.testclient import TestClient

    from app.main import app

    _FASTAPI_AVAILABLE = True
except ImportError:  # pragma: no cover — fastapiが無い環境
    _FASTAPI_AVAILABLE = False


_DOCUMENT = {
    "version": "1.11",
    "app": {"title": "支出メモ"},
    "screens": [{"id": "home", "widgets": [{"type": "text", "value": "今月"}]}],
}


def _generation(store: GenerationEvidenceStore, **kwargs) -> int:
    record = store.record(
        GenerationRecord(
            source=kwargs.pop("source", GenerationSource.CLOUD_AI),
            domain=kwargs.pop("domain", "household_budget"),
            validator_passed=kwargs.pop("validator_passed", True),
            **kwargs,
        )
    )
    return record.ref


class _Harness:
    """本番のSingletonへ触らない、独立した1組。"""

    def __init__(self) -> None:
        self.registry = ArtifactRegistry()
        self.generations = GenerationEvidenceStore()
        self.revisions = RevisionEvidenceStore()
        self.events = FeedbackEventLog()
        self.service = ArtifactFeedbackService(
            registry=self.registry, generations=self.generations,
            revisions=self.revisions, events=self.events,
        )

    def register(self, ref: int, *, session_id: str | None = None) -> ArtifactHandle:
        record = self.generations.get(ref)
        assert record is not None
        return self.registry.register(
            generation_ref=ref, generation_uid=record.uid, session_id=session_id
        )


# ---------------------------------------------------------------------------
# §15 Feedback
# ---------------------------------------------------------------------------


class TestFeedbackRecording(unittest.TestCase):
    def setUp(self) -> None:
        self.h = _Harness()

    def test_accepted_is_written_to_the_generation_record(self) -> None:
        ref = _generation(self.h.generations)
        handle = self.h.register(ref)

        result = self.h.service.record(
            signal=AcceptanceSignal.ACCEPTED, artifact_id=handle.handle
        )

        self.assertTrue(result.recorded)
        self.assertTrue(result.summary_updated)
        self.assertIsNone(result.rejected)
        self.assertIs(self.h.generations.get(ref).user_acceptance, AcceptanceSignal.ACCEPTED)

    def test_accepted_generation_becomes_a_training_candidate(self) -> None:
        """**これが効くまで、正例は構造上1件も生まれなかった。**"""
        ref = _generation(self.h.generations, runtime_outcome=RuntimeOutcome.RENDERED)
        self.assertEqual(self.h.generations.training_candidates(), ())

        self.h.service.record(
            signal=AcceptanceSignal.ACCEPTED, artifact_id=self.h.register(ref).handle
        )

        self.assertEqual(len(self.h.generations.training_candidates()), 1)

    def test_corrected_is_recorded_and_is_not_a_training_candidate(self) -> None:
        ref = _generation(self.h.generations, runtime_outcome=RuntimeOutcome.RENDERED)

        result = self.h.service.record(
            signal=AcceptanceSignal.CORRECTED, artifact_id=self.h.register(ref).handle
        )

        self.assertTrue(result.recorded)
        self.assertIs(self.h.generations.get(ref).user_acceptance, AcceptanceSignal.CORRECTED)
        self.assertEqual(self.h.generations.training_candidates(), ())

    def test_the_summary_keeps_the_first_signal(self) -> None:
        """要約は最初の信号が勝つ——塗り替えると「その時点でどう扱われたか」
        が消える。**ただし2つ目を捨てるわけではない**（下のTestを参照）。"""
        ref = _generation(self.h.generations)
        handle = self.h.register(ref)

        self.h.service.record(signal=AcceptanceSignal.ACCEPTED, artifact_id=handle.handle)
        second = self.h.service.record(
            signal=AcceptanceSignal.CORRECTED, artifact_id=handle.handle
        )

        self.assertTrue(second.recorded, "2つ目の評価が事実として残っていない")
        self.assertFalse(second.summary_updated)
        self.assertIs(self.h.generations.get(ref).user_acceptance, AcceptanceSignal.ACCEPTED)

    def test_unknown_artifact_is_rejected_with_a_reason(self) -> None:
        result = self.h.service.record(
            signal=AcceptanceSignal.ACCEPTED, artifact_id="そんなハンドルは発行していない"
        )
        self.assertFalse(result.recorded)
        self.assertIs(result.rejected, FeedbackRejected.UNKNOWN_ARTIFACT)

    def test_stale_artifact_is_rejected(self) -> None:
        """利用者が見ていた世代と、いまの世代が違う。"""
        ref = _generation(self.h.generations)
        handle = self.h.register(ref)

        result = self.h.service.record(
            signal=AcceptanceSignal.ACCEPTED,
            artifact_id=handle.handle,
            seen_version_token=new_version_token(),
        )

        self.assertFalse(result.recorded)
        self.assertIs(result.rejected, FeedbackRejected.STALE_ARTIFACT)
        self.assertIs(self.h.generations.get(ref).user_acceptance, AcceptanceSignal.UNKNOWN)
        self.assertEqual(self.h.events.size(), 0, "拒否したのにEventが残っている")

    def test_matching_version_token_is_accepted(self) -> None:
        ref = _generation(self.h.generations)
        handle = self.h.register(ref)

        result = self.h.service.record(
            signal=AcceptanceSignal.ACCEPTED,
            artifact_id=handle.handle,
            seen_version_token=handle.version_token,
        )
        self.assertTrue(result.recorded)

    def test_unknown_signal_is_not_recorded(self) -> None:
        """沈黙は情報ではない（`AcceptanceSignal.UNKNOWN`）。"""
        ref = _generation(self.h.generations)

        result = self.h.service.record(
            signal=AcceptanceSignal.UNKNOWN, artifact_id=self.h.register(ref).handle
        )
        self.assertFalse(result.recorded)
        self.assertIs(result.rejected, FeedbackRejected.UNUSABLE_SIGNAL)
        self.assertIs(self.h.generations.get(ref).user_acceptance, AcceptanceSignal.UNKNOWN)
        self.assertEqual(self.h.events.size(), 0)

    def test_session_id_resolves_to_the_latest_artifact_of_that_session(self) -> None:
        old_ref = _generation(self.h.generations)
        new_ref = _generation(self.h.generations)
        self.h.register(old_ref, session_id="s-1")
        self.h.register(new_ref, session_id="s-1")

        result = self.h.service.record(signal=AcceptanceSignal.ACCEPTED, session_id="s-1")

        self.assertTrue(result.recorded)
        self.assertIs(self.h.generations.get(new_ref).user_acceptance, AcceptanceSignal.ACCEPTED)
        self.assertIs(self.h.generations.get(old_ref).user_acceptance, AcceptanceSignal.UNKNOWN)

    def test_neither_artifact_id_nor_session_id_is_rejected(self) -> None:
        result = self.h.service.record(signal=AcceptanceSignal.ACCEPTED)
        self.assertFalse(result.recorded)
        self.assertIs(result.rejected, FeedbackRejected.UNKNOWN_ARTIFACT)


class TestFeedbackIsAppendOnly(unittest.TestCase):
    """**利用者Feedbackの時系列そのものがEvidenceである**（FORGE-017A §2）。

    commit Bは2つ目の信号を捨てていた。「最初は良いと言ったが、使って
    みたら直した」は、最初から`CORRECTED`だったものとまるで意味が違う
    ——前者は「一見よく見えるが実際には外している」という、Local AIに
    とって最も価値のある系列である。1つのfieldに潰すと区別できない。
    """

    def setUp(self) -> None:
        self.h = _Harness()
        self.ref = _generation(self.h.generations)
        self.handle = self.h.register(self.ref)

    def test_both_signals_survive_in_order(self) -> None:
        self.h.service.record(signal=AcceptanceSignal.ACCEPTED, artifact_id=self.handle.handle)
        self.h.service.record(signal=AcceptanceSignal.CORRECTED, artifact_id=self.handle.handle)

        history = self.h.service.history(self.handle.evidence_id)
        self.assertEqual(
            [e.signal for e in history],
            [AcceptanceSignal.ACCEPTED, AcceptanceSignal.CORRECTED],
        )

    def test_sequence_counts_from_one(self) -> None:
        self.h.service.record(signal=AcceptanceSignal.ACCEPTED, artifact_id=self.handle.handle)
        self.h.service.record(signal=AcceptanceSignal.CORRECTED, artifact_id=self.handle.handle)
        self.h.service.record(signal=AcceptanceSignal.ABANDONED, artifact_id=self.handle.handle)

        self.assertEqual([e.sequence for e in self.h.service.history(self.handle.evidence_id)],
                         [1, 2, 3])

    def test_events_of_different_artifacts_do_not_mix(self) -> None:
        other_ref = _generation(self.h.generations)
        other = self.h.register(other_ref)

        self.h.service.record(signal=AcceptanceSignal.ACCEPTED, artifact_id=self.handle.handle)
        self.h.service.record(signal=AcceptanceSignal.CORRECTED, artifact_id=other.handle)

        self.assertEqual(len(self.h.service.history(self.handle.evidence_id)), 1)
        self.assertEqual(len(self.h.service.history(other.evidence_id)), 1)

    def test_event_ids_are_unique(self) -> None:
        for _ in range(5):
            self.h.service.record(
                signal=AcceptanceSignal.ACCEPTED, artifact_id=self.handle.handle
            )
        ids = {e.event_id for e in self.h.service.history(self.handle.evidence_id)}
        self.assertEqual(len(ids), 5)

    def test_an_event_points_at_the_durable_evidence_id_not_the_handle(self) -> None:
        """**ハンドルはEventに現れない**（017A §3）。失効するIDを系譜へ
        使うと、失効した時点で系譜が切れる。"""
        self.h.service.record(signal=AcceptanceSignal.ACCEPTED, artifact_id=self.handle.handle)
        event = self.h.service.history(self.handle.evidence_id)[0]

        self.assertEqual(event.artifact_evidence_ref.uid, self.h.generations.get(self.ref).uid)
        self.assertNotIn(self.handle.handle, repr(event.to_dict()))

    def test_the_event_log_has_no_update_or_delete(self) -> None:
        """**追記専用であること自体を固定する。**"""
        for forbidden in ("update", "delete", "remove", "set_signal", "overwrite"):
            self.assertFalse(
                hasattr(FeedbackEventLog, forbidden),
                f"FeedbackEventLog に {forbidden} が生えている（追記専用が壊れる）",
            )


class TestFeedbackIdempotency(unittest.TestCase):
    """**同じ送信の繰り返しと、本当の再評価を区別する**（FORGE-017A §2）。"""

    def setUp(self) -> None:
        self.h = _Harness()
        self.ref = _generation(self.h.generations)
        self.handle = self.h.register(self.ref)

    def test_the_same_key_twice_is_a_duplicate(self) -> None:
        first = self.h.service.record(
            signal=AcceptanceSignal.ACCEPTED, artifact_id=self.handle.handle,
            idempotency_key="req-1",
        )
        second = self.h.service.record(
            signal=AcceptanceSignal.ACCEPTED, artifact_id=self.handle.handle,
            idempotency_key="req-1",
        )

        self.assertTrue(first.recorded)
        self.assertFalse(second.recorded)
        self.assertIs(second.rejected, FeedbackRejected.DUPLICATE_REQUEST)
        self.assertEqual(len(self.h.service.history(self.handle.evidence_id)), 1)

    def test_a_duplicate_returns_the_original_event(self) -> None:
        first = self.h.service.record(
            signal=AcceptanceSignal.ACCEPTED, artifact_id=self.handle.handle,
            idempotency_key="req-1",
        )
        second = self.h.service.record(
            signal=AcceptanceSignal.ACCEPTED, artifact_id=self.handle.handle,
            idempotency_key="req-1",
        )
        self.assertEqual(second.event.event_id, first.event.event_id)

    def test_different_keys_are_different_evaluations(self) -> None:
        self.h.service.record(
            signal=AcceptanceSignal.ACCEPTED, artifact_id=self.handle.handle,
            idempotency_key="req-1",
        )
        self.h.service.record(
            signal=AcceptanceSignal.CORRECTED, artifact_id=self.handle.handle,
            idempotency_key="req-2",
        )
        self.assertEqual(len(self.h.service.history(self.handle.evidence_id)), 2)

    def test_no_key_means_not_a_retry(self) -> None:
        """**分からないものを「たぶん再送」へ倒さない。**

        倒すと、本物の再評価が静かに消える。
        """
        for _ in range(3):
            self.h.service.record(
                signal=AcceptanceSignal.CORRECTED, artifact_id=self.handle.handle
            )
        self.assertEqual(len(self.h.service.history(self.handle.evidence_id)), 3)


class TestFeedbackSourceIsNotOptimistic(unittest.TestCase):
    def test_inferred_feedback_is_not_supervision(self) -> None:
        """**Forgeの推定を「利用者がそう言った」として学習しない。**

        推定を教師にすると、Forge自身の思い込みを増幅する。
        """
        self.assertFalse(FeedbackSource.INFERRED.is_usable_as_supervision)
        self.assertFalse(FeedbackSource.SYSTEM.is_usable_as_supervision)
        self.assertFalse(FeedbackSource.UNKNOWN.is_usable_as_supervision)
        self.assertTrue(FeedbackSource.USER_EXPLICIT.is_usable_as_supervision)

    def test_the_default_source_is_unknown(self) -> None:
        log = FeedbackEventLog()
        event = log.append(
            evidence_id=ArtifactEvidenceId(EvidenceKind.GENERATION, "uid-1", 1),
            signal=AcceptanceSignal.ACCEPTED,
        )
        self.assertIs(event.source, FeedbackSource.UNKNOWN)


class TestIdentitySeparation(unittest.TestCase):
    """**3つのIDを混ぜない**（FORGE-017A §3・§4）。

    | | 何のためか | 寿命 | Cloudへ |
    |---|---|---|---|
    | `handle` | Clientが評価を送り返す | 失効する | **出さない** |
    | `ArtifactEvidenceId` | Dataset Lineage | 記録に貼り付く | 出す |
    | `version_token` | 世代照合 | ハンドルと同じ | 出さない |
    """

    def setUp(self) -> None:
        self.h = _Harness()

    def test_handle_is_not_guessable(self) -> None:
        """連番だと、他人の生成物へ評価を書けてしまう。"""
        handles = {
            self.h.registry.register(generation_ref=i, generation_uid=f"u{i}").handle
            for i in range(20)
        }
        self.assertEqual(len(handles), 20)
        for handle in handles:
            self.assertGreaterEqual(len(handle), 16)
            self.assertFalse(handle.isdigit())

    def test_the_evidence_id_is_the_record_uid_not_the_store_position(self) -> None:
        """**`ref`は系譜に使えない。** プロセスを跨ぐと別の記録を指す
        （1番は次のプロセスでも1番だが、中身は別物である）。"""
        ref = _generation(self.h.generations)
        record = self.h.generations.get(ref)
        handle = self.h.register(ref)

        self.assertEqual(handle.evidence_id.uid, record.uid)
        self.assertNotEqual(handle.evidence_id.uid, str(ref))
        # 系譜として書き出す形に `ref` は含まれない。
        self.assertNotIn("ref", handle.evidence_id.to_dict())

    def test_the_handle_never_appears_in_the_lineage_id(self) -> None:
        """**失効するIDを系譜へ流用しない**（017A §3・自己監査3/4）。"""
        ref = _generation(self.h.generations)
        handle = self.h.register(ref)
        self.assertNotIn(handle.handle, repr(handle.evidence_id.to_dict()))

    def test_what_goes_to_the_client_carries_no_lineage_id(self) -> None:
        ref = _generation(self.h.generations)
        handle = self.h.register(ref)

        client_view = handle.to_client_dict()
        self.assertEqual(set(client_view), {"artifact_id", "version_token"})
        self.assertNotIn(handle.evidence_id.uid, repr(client_view))

    def test_two_uids_differ_even_for_identical_content(self) -> None:
        """記録が別なら身元も別。内容の同一性とは無関係である。"""
        first = _generation(self.h.generations)
        second = _generation(self.h.generations)
        self.assertNotEqual(
            self.h.generations.get(first).uid, self.h.generations.get(second).uid
        )

    def test_a_revision_handle_points_at_the_revision(self) -> None:
        """変更後の評価は、変更へ付く——生成へ付けると意味が変わる。"""
        handle = self.h.registry.register(
            generation_ref=7, generation_uid="gen-uid",
            revision_ref=3, revision_uid="rev-uid",
        )
        self.assertIs(handle.evidence_id.kind, EvidenceKind.REVISION)
        self.assertEqual(handle.evidence_id.uid, "rev-uid")

    def test_a_handle_without_a_revision_points_at_the_generation(self) -> None:
        handle = self.h.registry.register(generation_ref=7, generation_uid="gen-uid")
        self.assertIs(handle.evidence_id.kind, EvidenceKind.GENERATION)
        self.assertEqual(handle.evidence_id.uid, "gen-uid")


class TestVersionTokenIsNotAContentHash(unittest.TestCase):
    """**世代照合とContent Identityを混ぜない**（FORGE-017A §4）。"""

    def test_the_token_does_not_depend_on_the_document(self) -> None:
        """同じ内容でも毎回違う値になる。**それで正しい**——別々の
        利用者の生成物を突き合わせられない。"""
        self.assertNotEqual(new_version_token(), new_version_token())

    def test_the_registry_never_derives_the_token_from_the_document(self) -> None:
        """**世代tokenは内容から作らない**（017A §4）。

        ---

        ## この制約は FORGE-019A で形を変えた

        017Aでは「見ないなら受け取らない」として`register()`から
        `document`引数そのものを外していた。**019Aで見る必要が出た**
        ——Revisionは「その生成物を直した」という記録なので、直した対象が
        同じものかを確かめないと記録が嘘になる（§1 Document binding）。

        そこで制約を**引数の有無から、値の性質へ**移した。

        * `document`は受け取ってよい
        * ただし**`version_token`はそこから作られない**（内容と無関係）
        * 束縛は`document_binding`（プロセス内鍵のHMAC）へ入り、
          Clientにも Learning Event にも出ない

        引数を禁じるのは手段であって目的ではなかった。目的は
        「内容由来の値を外へ出さない」ことである。
        """
        registry = ArtifactRegistry()
        document = {"version": "1.12", "app": {"title": "同じ内容"}}
        first = registry.register(generation_ref=1, generation_uid="u1", document=document)
        second = registry.register(generation_ref=2, generation_uid="u2", document=document)

        self.assertNotEqual(
            first.version_token, second.version_token,
            "同じ内容から同じtokenが出ている（内容由来になっている）",
        )
        self.assertNotIn(document_fingerprint(document), first.version_token)

    def test_the_document_binding_never_reaches_the_client(self) -> None:
        """**束縛はClientへ出さない**（FORGE-019A §1）。"""
        registry = ArtifactRegistry()
        document = {"version": "1.12", "app": {"title": "x"}}
        handle = registry.register(generation_ref=1, generation_uid="u1", document=document)

        self.assertTrue(handle.document_binding)
        self.assertNotIn(handle.document_binding, repr(handle.to_client_dict()))
        self.assertEqual(set(handle.to_client_dict()), {"artifact_id", "version_token"})

    def test_two_registrations_get_different_tokens(self) -> None:
        registry = ArtifactRegistry()
        first = registry.register(generation_ref=1, generation_uid="u1")
        second = registry.register(generation_ref=1, generation_uid="u1")
        self.assertNotEqual(first.version_token, second.version_token)

    def test_the_internal_fingerprint_still_exists_for_internal_use(self) -> None:
        """内部専用として残してある（消したのではなく、用途を絞った）。"""
        a = {"version": "1.11", "app": {"title": "x"}}
        b = {"app": {"title": "x"}, "version": "1.11"}
        self.assertEqual(document_fingerprint(a), document_fingerprint(b))
        self.assertNotEqual(document_fingerprint(a), document_fingerprint({"app": {}}))


# ---------------------------------------------------------------------------
# §15 Revision
# ---------------------------------------------------------------------------


class TestRevisionEvidence(unittest.TestCase):
    def setUp(self) -> None:
        self.store = RevisionEvidenceStore()

    def test_sequence_counts_per_generation(self) -> None:
        self.assertEqual(self.store.next_sequence(7), 1)
        self.store.record(RevisionRecord(base_generation_ref=7, sequence=1))
        self.assertEqual(self.store.next_sequence(7), 2)
        # **別の生成物の変更は数えない。**
        self.assertEqual(self.store.next_sequence(8), 1)

    def test_revisions_are_linked_to_their_base_generation(self) -> None:
        first = self.store.record(RevisionRecord(base_generation_ref=7, sequence=1))
        second = self.store.record(
            RevisionRecord(
                base_generation_ref=7, sequence=2, previous_revision_ref=first.ref
            )
        )
        self.store.record(RevisionRecord(base_generation_ref=9, sequence=1))

        chain = self.store.for_generation(7)
        self.assertEqual([r.ref for r in chain], [first.ref, second.ref])
        self.assertEqual(second.previous_revision_ref, first.ref)

    def test_revision_acceptance_follows_the_same_first_wins_rule(self) -> None:
        """生成と変更で規則が違うと、突き合わせたときに静かに嘘になる。"""
        stored = self.store.record(RevisionRecord(base_generation_ref=7))
        self.store.note_user_acceptance([stored.ref], AcceptanceSignal.ACCEPTED)
        self.store.note_user_acceptance([stored.ref], AcceptanceSignal.CORRECTED)
        self.assertIs(self.store.get(stored.ref).user_acceptance, AcceptanceSignal.ACCEPTED)

    def test_unknown_does_not_overwrite(self) -> None:
        stored = self.store.record(RevisionRecord(base_generation_ref=7))
        self.store.note_user_acceptance([stored.ref], AcceptanceSignal.ACCEPTED)
        self.assertEqual(self.store.note_user_acceptance([stored.ref], AcceptanceSignal.UNKNOWN), 0)
        self.assertIs(self.store.get(stored.ref).user_acceptance, AcceptanceSignal.ACCEPTED)

    def test_revision_metrics_do_not_mix_into_generation_metrics(self) -> None:
        """§15「生成の集計と変更の集計が混ざらない」。

        変更が10件あっても、生成の集計は生成の件数のままである。
        """
        generations = GenerationEvidenceStore()
        _generation(generations)
        for _ in range(10):
            self.store.record(RevisionRecord(base_generation_ref=1, validator_passed=True))

        summary = generations.summary_by_source()
        self.assertEqual(summary[GenerationSource.CLOUD_AI.value]["samples"], 1)
        self.assertEqual(self.store.size(), 10)

    def test_a_revision_is_a_positive_example_only_when_explicitly_accepted(self) -> None:
        stored = self.store.record(
            RevisionRecord(
                base_generation_ref=7, validator_passed=True,
                source=GenerationSource.CLOUD_AI,
                runtime_outcome=RuntimeOutcome.RENDERED,
            )
        )
        self.assertFalse(stored.is_positive_example)

        self.store.note_user_acceptance([stored.ref], AcceptanceSignal.ACCEPTED)
        self.assertTrue(self.store.get(stored.ref).is_positive_example)

    def test_a_failed_runtime_is_not_a_positive_example(self) -> None:
        stored = self.store.record(
            RevisionRecord(
                base_generation_ref=7, validator_passed=True,
                source=GenerationSource.CLOUD_AI,
                runtime_outcome=RuntimeOutcome.FAILED,
                user_acceptance=AcceptanceSignal.ACCEPTED,
            )
        )
        self.assertFalse(stored.is_positive_example)


class TestRevisionTrainingProvenance(unittest.TestCase):
    """**由来が分からない/本物でない変更を教師データにしない**
    （FORGE-017A §1）。

    commit Bの実装は`source`を見ておらず、既定の`UNKNOWN`のまま
    「利用者が受け入れた」だけでTraining Candidateになっていた。
    生成側(`GenerationRecord`)は013から`is_usable_for_training`を
    要求していたので、**同じ語彙で片方だけ緩い**状態だった。
    """

    def setUp(self) -> None:
        self.store = RevisionEvidenceStore()

    def _revision(self, source: GenerationSource) -> RevisionRecord:
        return self.store.record(
            RevisionRecord(
                base_generation_ref=7,
                source=source,
                validator_passed=True,
                runtime_outcome=RuntimeOutcome.RENDERED,
                user_acceptance=AcceptanceSignal.ACCEPTED,
            )
        )

    def test_unknown_source_is_not_a_positive_example(self) -> None:
        """記録し忘れを「安全」へ倒さない。"""
        self.assertFalse(self._revision(GenerationSource.UNKNOWN).is_positive_example)

    def test_test_double_source_is_not_a_positive_example(self) -> None:
        """**Mockの出力を教師にすると、Mockの癖を学ぶ。**

        テストは`mock` Providerで大量に走るので、これを許すと
        実運用よりテストの方が「正例」を多く生む。
        """
        self.assertFalse(self._revision(GenerationSource.TEST_DOUBLE).is_positive_example)

    def test_cloud_ai_source_is_a_candidate(self) -> None:
        self.assertTrue(self._revision(GenerationSource.CLOUD_AI).is_positive_example)

    def test_local_ai_source_is_a_candidate(self) -> None:
        self.assertTrue(self._revision(GenerationSource.LOCAL_AI).is_positive_example)

    def test_curated_source_is_a_candidate(self) -> None:
        """Curatedは由来が分かっていて本物である（AI呼び出し0回だが、
        それは欠損ではない——013でGenerationRecordを作った理由）。"""
        self.assertTrue(self._revision(GenerationSource.CURATED).is_positive_example)

    def test_the_default_source_is_not_usable(self) -> None:
        """**既定値が楽観側へ倒れていないこと。**"""
        stored = self.store.record(
            RevisionRecord(
                base_generation_ref=7, validator_passed=True,
                runtime_outcome=RuntimeOutcome.RENDERED,
                user_acceptance=AcceptanceSignal.ACCEPTED,
            )
        )
        self.assertIs(stored.source, GenerationSource.UNKNOWN)
        self.assertFalse(stored.is_positive_example)

    def test_training_candidates_matches_generation_side(self) -> None:
        """Storeの候補抽出も生成側と同じ形であること。"""
        self._revision(GenerationSource.UNKNOWN)
        self._revision(GenerationSource.TEST_DOUBLE)
        self._revision(GenerationSource.CLOUD_AI)

        candidates = self.store.training_candidates()
        self.assertEqual(len(candidates), 1)
        self.assertIs(candidates[0].source, GenerationSource.CLOUD_AI)

    def test_revision_and_generation_apply_the_same_rule(self) -> None:
        """**同じ4条件であること自体を固定する。**

        片方だけ条件が増減すると、突き合わせたときに静かに嘘になる。
        """
        generations = GenerationEvidenceStore()
        for source in (GenerationSource.UNKNOWN, GenerationSource.TEST_DOUBLE,
                       GenerationSource.CLOUD_AI, GenerationSource.LOCAL_AI,
                       GenerationSource.CURATED, GenerationSource.COMPOSITION):
            generation = generations.record(
                GenerationRecord(
                    source=source, domain="household_budget", validator_passed=True,
                    runtime_outcome=RuntimeOutcome.RENDERED,
                    user_acceptance=AcceptanceSignal.ACCEPTED,
                )
            )
            revision = self._revision(source)
            self.assertEqual(
                generation.is_positive_example, revision.is_positive_example,
                f"{source.value}: 生成と変更で判定が食い違っている",
            )

    def test_user_corrected_roles_are_separated_from_ai_choices(self) -> None:
        """AIが選んだものと利用者が直させたものを混ぜない（§4）。"""
        stored = self.store.record(
            RevisionRecord(
                base_generation_ref=7,
                design_revisions=(
                    DesignRevision(
                        screen_id="home", target_id="w1", axis="list_surface",
                        before="surface.card", after="surface.elevated",
                        source=DesignDecisionSource.USER_CORRECTION,
                    ),
                    DesignRevision(
                        screen_id="home", target_id="w2", axis="screen_density",
                        before="density.compact", after="density.relaxed",
                        source=DesignDecisionSource.AI,
                    ),
                ),
            )
        )
        corrected = stored.user_corrected_roles
        self.assertEqual(len(corrected), 1)
        self.assertEqual(corrected[0].target_id, "w1")

    def test_user_correction_is_not_counted_as_ai_evidence(self) -> None:
        self.assertFalse(DesignDecisionSource.USER_CORRECTION.is_ai_evidence)
        self.assertTrue(DesignDecisionSource.AI.is_ai_evidence)


# ---------------------------------------------------------------------------
# §15 Privacy（016A §10 / 006 §22）
# ---------------------------------------------------------------------------


class TestRevisionPrivacy(unittest.TestCase):
    def test_a_revision_record_cannot_hold_a_raw_utterance(self) -> None:
        """**型として持てない。** 「入れない運用」では必ず入る。"""
        field_names = set(RevisionRecord.__dataclass_fields__)
        for forbidden in ("utterance", "message", "text", "prompt", "raw", "user_input"):
            self.assertNotIn(forbidden, field_names)

    def test_design_revision_cannot_hold_a_raw_utterance(self) -> None:
        field_names = set(DesignRevision.__dataclass_fields__)
        for forbidden in ("utterance", "message", "text", "prompt", "raw", "user_input"):
            self.assertNotIn(forbidden, field_names)

    def test_serialized_revision_contains_only_identifiers(self) -> None:
        stored = RevisionEvidenceStore().record(
            RevisionRecord(
                base_generation_ref=7,
                operation_kind=RevisionOperationKind.DESIGN,
                design_revisions=(
                    DesignRevision(
                        screen_id="home", target_id="w1", axis="list_surface",
                        before="surface.card", after="surface.elevated",
                        source=DesignDecisionSource.USER_CORRECTION,
                    ),
                ),
            )
        )
        serialized = repr(stored.to_dict())
        # 利用者が言いそうな言い回しが、記録のどこにも現れない。
        for phrase in ("ごちゃごちゃ", "見にくい", "もっと", "してほしい"):
            self.assertNotIn(phrase, serialized)


# ---------------------------------------------------------------------------
# §15 HTTP往復——**本番から呼ばれることの証拠**
# ---------------------------------------------------------------------------


@unittest.skipUnless(_FASTAPI_AVAILABLE, "fastapi/pydanticが無い環境ではスキップする")
class TestFeedbackOverHttp(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(app)

    def _build(self) -> dict:
        response = self.client.post(
            "/api/v1/ai/generate",
            json={
                "input": {
                    "natural_language": "毎日の支出を記録したい",
                    "generation_options": {"provider": "mock"},
                }
            },
        )
        self.assertEqual(response.status_code, 200, response.text)
        body = response.json()
        self.assertEqual(body["status"], "success")
        return body["result"]

    def test_generate_returns_an_artifact_handle(self) -> None:
        """**この配線が無いと、評価を書く先が本番に存在しない。**"""
        result = self._build()
        self.assertIsNotNone(result.get("artifact"), "生成結果にartifactが付いていない")
        self.assertTrue(result["artifact"]["artifact_id"])
        self.assertTrue(result["artifact"]["version_token"])

    def test_generate_does_not_expose_internal_refs(self) -> None:
        """内部refを出すと、任意のrefへ「受け入れた」を書けてしまう。"""
        result = self._build()
        self.assertNotIn("generation_ref", result["artifact"])
        self.assertNotIn("generation_ref", result)

    def test_the_response_never_carries_a_hash_of_the_document(self) -> None:
        """**内容の指紋をClientへ返さない**（FORGE-017A §4）。

        内容が同じなら誰が作っても同じ値になるので、外へ出すと利用者を
        跨いだ突き合わせに使える。内容の候補が少なければ総当たりで中身を
        言い当てられる。世代照合に必要なのは「さっきと同じものか」だけで、
        内容の同一性ではない。
        """
        result = self._build()
        fingerprint = document_fingerprint(result["forge_document"])

        self.assertNotEqual(result["artifact"]["version_token"], fingerprint)
        self.assertNotIn(
            fingerprint, json.dumps(result["artifact"]),
            "Documentの内容ハッシュがHTTPレスポンスに現れている",
        )

    def test_two_generations_of_the_same_input_get_different_tokens(self) -> None:
        """同じ入力でもtokenが違うこと——内容から作っていない証拠。"""
        first = self._build()["artifact"]["version_token"]
        second = self._build()["artifact"]["version_token"]
        self.assertNotEqual(first, second)

    def test_the_response_never_carries_the_lineage_uid(self) -> None:
        """**系譜のIDをClientへ出さない**（FORGE-017A §3）。"""
        from app.ai.gateway.artifact_feedback import default_artifact_registry

        result = self._build()
        handle = default_artifact_registry().resolve(result["artifact"]["artifact_id"])
        self.assertIsNotNone(handle)
        self.assertNotIn(handle.evidence_id.uid, json.dumps(result))

    def test_feedback_round_trip_records_the_signal(self) -> None:
        from app.ai.gateway.artifact_feedback import default_artifact_registry
        from app.ai.gateway.generation_evidence import default_generation_store

        result = self._build()
        artifact_id = result["artifact"]["artifact_id"]

        response = self.client.post(
            "/api/v1/ai/feedback", json={"signal": "accepted", "artifact_id": artifact_id},
        )

        self.assertEqual(response.status_code, 200, response.text)
        body = response.json()
        self.assertTrue(body["recorded"])
        self.assertTrue(body["summary_updated"])
        self.assertIsNone(body["rejected"])

        handle = default_artifact_registry().resolve(artifact_id)
        self.assertIsNotNone(handle)
        record = default_generation_store().get(handle.evidence_id.ref)
        self.assertIs(record.user_acceptance, AcceptanceSignal.ACCEPTED)

    def test_feedback_round_trip_appends_an_event(self) -> None:
        """**時系列がEvidenceとして残ること**（FORGE-017A §2）。"""
        from app.ai.gateway.artifact_feedback import (
            default_artifact_registry,
            default_feedback_service,
        )

        result = self._build()
        artifact_id = result["artifact"]["artifact_id"]

        for signal in ("accepted", "corrected"):
            response = self.client.post(
                "/api/v1/ai/feedback",
                json={"signal": signal, "artifact_id": artifact_id},
            )
            self.assertEqual(response.status_code, 200, response.text)
            self.assertTrue(response.json()["recorded"], f"{signal}が捨てられている")

        handle = default_artifact_registry().resolve(artifact_id)
        history = default_feedback_service().history(handle.evidence_id)
        self.assertEqual(
            [e.signal.value for e in history], ["accepted", "corrected"],
            "2つ目の評価が消えている（時系列がEvidenceである）",
        )

    def test_the_second_signal_does_not_change_the_summary(self) -> None:
        result = self._build()
        artifact_id = result["artifact"]["artifact_id"]

        self.client.post(
            "/api/v1/ai/feedback", json={"signal": "accepted", "artifact_id": artifact_id}
        )
        second = self.client.post(
            "/api/v1/ai/feedback", json={"signal": "corrected", "artifact_id": artifact_id}
        ).json()

        self.assertTrue(second["recorded"])
        self.assertFalse(second["summary_updated"])

    def test_the_same_idempotency_key_is_not_appended_twice(self) -> None:
        result = self._build()
        artifact_id = result["artifact"]["artifact_id"]
        payload = {
            "signal": "accepted", "artifact_id": artifact_id, "idempotency_key": "retry-1",
        }

        first = self.client.post("/api/v1/ai/feedback", json=payload).json()
        second = self.client.post("/api/v1/ai/feedback", json=payload).json()

        self.assertTrue(first["recorded"])
        self.assertFalse(second["recorded"])
        self.assertEqual(second["rejected"], "duplicate_request")

    def test_feedback_for_an_unknown_artifact_returns_a_reason_not_a_crash(self) -> None:
        response = self.client.post(
            "/api/v1/ai/feedback", json={"signal": "accepted", "artifact_id": "存在しない"},
        )
        self.assertEqual(response.status_code, 200, response.text)
        body = response.json()
        self.assertFalse(body["recorded"])
        self.assertEqual(body["rejected"], "unknown_artifact")

    def test_feedback_with_a_stale_version_token_is_rejected(self) -> None:
        result = self._build()
        response = self.client.post(
            "/api/v1/ai/feedback",
            json={
                "signal": "accepted",
                "artifact_id": result["artifact"]["artifact_id"],
                "seen_version_token": new_version_token(),
            },
        )
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["rejected"], "stale_artifact")

    def test_feedback_rejects_unknown_as_a_signal(self) -> None:
        """「沈黙」をHTTPで送れるようにしない。"""
        response = self.client.post(
            "/api/v1/ai/feedback", json={"signal": "unknown", "artifact_id": "x"},
        )
        self.assertEqual(response.status_code, 422, response.text)

    def test_feedback_does_not_accept_raw_refs_from_the_client(self) -> None:
        """`generation_refs`のような内部refを受け付ける口を作らない。"""
        response = self.client.post(
            "/api/v1/ai/feedback", json={"signal": "accepted", "generation_refs": [1, 2, 3]},
        )
        self.assertEqual(response.status_code, 200, response.text)
        body = response.json()
        # 未知のキーは無視され、指す先が無いので拒否される——
        # **決して「1,2,3を受け入れた」にはならない。**
        self.assertFalse(body["recorded"])
        self.assertEqual(body["rejected"], "unknown_artifact")

    def test_every_generation_gets_its_own_handle(self) -> None:
        first = self._build()["artifact"]["artifact_id"]
        second = self._build()["artifact"]["artifact_id"]
        self.assertNotEqual(first, second)


if __name__ == "__main__":
    unittest.main()
