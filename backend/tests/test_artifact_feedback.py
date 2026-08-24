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

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

os.environ.setdefault("FORGE_FEATURE_WORKSPACE", "true")
os.environ.setdefault("FORGE_FEATURE_FOLDER", "true")

from app.ai.gateway.artifact_feedback import (  # noqa: E402
    ArtifactFeedbackService,
    ArtifactRegistry,
    FeedbackRejected,
    document_fingerprint,
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
        self.service = ArtifactFeedbackService(
            registry=self.registry, generations=self.generations, revisions=self.revisions
        )


# ---------------------------------------------------------------------------
# §15 Feedback
# ---------------------------------------------------------------------------


class TestFeedbackRecording(unittest.TestCase):
    def setUp(self) -> None:
        self.h = _Harness()

    def test_accepted_is_written_to_the_generation_record(self) -> None:
        ref = _generation(self.h.generations)
        identity = self.h.registry.register(generation_ref=ref, document=_DOCUMENT)

        result = self.h.service.record(
            signal=AcceptanceSignal.ACCEPTED, artifact_id=identity.artifact_id
        )

        self.assertTrue(result.recorded)
        self.assertIsNone(result.rejected)
        self.assertIs(self.h.generations.get(ref).user_acceptance, AcceptanceSignal.ACCEPTED)

    def test_accepted_generation_becomes_a_training_candidate(self) -> None:
        """**これが効くまで、正例は構造上1件も生まれなかった。**"""
        ref = _generation(self.h.generations, runtime_outcome=RuntimeOutcome.RENDERED)
        self.assertEqual(self.h.generations.training_candidates(), ())

        identity = self.h.registry.register(generation_ref=ref, document=_DOCUMENT)
        self.h.service.record(signal=AcceptanceSignal.ACCEPTED, artifact_id=identity.artifact_id)

        self.assertEqual(len(self.h.generations.training_candidates()), 1)

    def test_corrected_is_recorded_and_is_not_a_training_candidate(self) -> None:
        ref = _generation(self.h.generations, runtime_outcome=RuntimeOutcome.RENDERED)
        identity = self.h.registry.register(generation_ref=ref, document=_DOCUMENT)

        result = self.h.service.record(
            signal=AcceptanceSignal.CORRECTED, artifact_id=identity.artifact_id
        )

        self.assertTrue(result.recorded)
        self.assertIs(self.h.generations.get(ref).user_acceptance, AcceptanceSignal.CORRECTED)
        self.assertEqual(self.h.generations.training_candidates(), ())

    def test_first_signal_wins(self) -> None:
        """後から塗り替えると「その時点でどう扱われたか」が消える。"""
        ref = _generation(self.h.generations)
        identity = self.h.registry.register(generation_ref=ref, document=_DOCUMENT)

        self.h.service.record(signal=AcceptanceSignal.ACCEPTED, artifact_id=identity.artifact_id)
        second = self.h.service.record(
            signal=AcceptanceSignal.CORRECTED, artifact_id=identity.artifact_id
        )

        self.assertFalse(second.recorded)
        self.assertIs(second.rejected, FeedbackRejected.ALREADY_RECORDED)
        self.assertIs(self.h.generations.get(ref).user_acceptance, AcceptanceSignal.ACCEPTED)

    def test_unknown_artifact_is_rejected_with_a_reason(self) -> None:
        result = self.h.service.record(
            signal=AcceptanceSignal.ACCEPTED, artifact_id="そんなIDは発行していない"
        )
        self.assertFalse(result.recorded)
        self.assertIs(result.rejected, FeedbackRejected.UNKNOWN_ARTIFACT)

    def test_stale_artifact_is_rejected(self) -> None:
        """利用者が見ていた世代と、いまの世代が違う（§5）。"""
        ref = _generation(self.h.generations)
        identity = self.h.registry.register(generation_ref=ref, document=_DOCUMENT)

        result = self.h.service.record(
            signal=AcceptanceSignal.ACCEPTED,
            artifact_id=identity.artifact_id,
            seen_fingerprint=document_fingerprint({"version": "1.11", "app": {"title": "別物"}}),
        )

        self.assertFalse(result.recorded)
        self.assertIs(result.rejected, FeedbackRejected.STALE_ARTIFACT)
        self.assertIs(self.h.generations.get(ref).user_acceptance, AcceptanceSignal.UNKNOWN)

    def test_matching_fingerprint_is_accepted(self) -> None:
        ref = _generation(self.h.generations)
        identity = self.h.registry.register(generation_ref=ref, document=_DOCUMENT)

        result = self.h.service.record(
            signal=AcceptanceSignal.ACCEPTED,
            artifact_id=identity.artifact_id,
            seen_fingerprint=document_fingerprint(_DOCUMENT),
        )
        self.assertTrue(result.recorded)

    def test_unknown_signal_is_not_recorded(self) -> None:
        """沈黙は情報ではない（`AcceptanceSignal.UNKNOWN`）。"""
        ref = _generation(self.h.generations)
        identity = self.h.registry.register(generation_ref=ref, document=_DOCUMENT)

        result = self.h.service.record(
            signal=AcceptanceSignal.UNKNOWN, artifact_id=identity.artifact_id
        )
        self.assertFalse(result.recorded)
        self.assertIs(self.h.generations.get(ref).user_acceptance, AcceptanceSignal.UNKNOWN)

    def test_session_id_resolves_to_the_latest_artifact_of_that_session(self) -> None:
        old_ref = _generation(self.h.generations)
        new_ref = _generation(self.h.generations)
        self.h.registry.register(generation_ref=old_ref, document=_DOCUMENT, session_id="s-1")
        self.h.registry.register(
            generation_ref=new_ref, document={"version": "1.11", "app": {"title": "二つ目"}},
            session_id="s-1",
        )

        result = self.h.service.record(signal=AcceptanceSignal.ACCEPTED, session_id="s-1")

        self.assertTrue(result.recorded)
        self.assertIs(self.h.generations.get(new_ref).user_acceptance, AcceptanceSignal.ACCEPTED)
        self.assertIs(self.h.generations.get(old_ref).user_acceptance, AcceptanceSignal.UNKNOWN)

    def test_neither_artifact_id_nor_session_id_is_rejected(self) -> None:
        result = self.h.service.record(signal=AcceptanceSignal.ACCEPTED)
        self.assertFalse(result.recorded)
        self.assertIs(result.rejected, FeedbackRejected.UNKNOWN_ARTIFACT)


class TestArtifactIdentity(unittest.TestCase):
    def test_artifact_id_is_not_guessable(self) -> None:
        """連番だと、他人の生成物へ評価を書けてしまう。"""
        registry = ArtifactRegistry()
        ids = {registry.register(generation_ref=i, document=_DOCUMENT).artifact_id for i in range(20)}
        self.assertEqual(len(ids), 20)
        for artifact_id in ids:
            self.assertGreaterEqual(len(artifact_id), 16)
            self.assertFalse(artifact_id.isdigit())

    def test_fingerprint_is_stable_under_key_order(self) -> None:
        """キーの順序が違うだけで「古い扱い」にしない。"""
        a = {"version": "1.11", "app": {"title": "x"}}
        b = {"app": {"title": "x"}, "version": "1.11"}
        self.assertEqual(document_fingerprint(a), document_fingerprint(b))

    def test_fingerprint_changes_when_the_document_changes(self) -> None:
        a = {"version": "1.11", "app": {"title": "x"}}
        b = {"version": "1.11", "app": {"title": "y"}}
        self.assertNotEqual(document_fingerprint(a), document_fingerprint(b))

    def test_fingerprint_does_not_contain_the_document_text(self) -> None:
        """指紋から本文は復元できない（006 §22のPrivacy境界）。"""
        fingerprint = document_fingerprint({"app": {"title": "医療費の記録"}})
        self.assertNotIn("医療費", fingerprint)
        self.assertTrue(all(c in "0123456789abcdef" for c in fingerprint))

    def test_evidence_ref_points_at_the_revision_when_there_is_one(self) -> None:
        """変更後の評価は、変更へ付く——生成へ付けると意味が変わる。"""
        registry = ArtifactRegistry()
        identity = registry.register(generation_ref=7, document=_DOCUMENT, revision_ref=3)
        self.assertEqual(identity.evidence_ref, ("revision", 3))

    def test_evidence_ref_points_at_the_generation_when_there_is_no_revision(self) -> None:
        registry = ArtifactRegistry()
        identity = registry.register(generation_ref=7, document=_DOCUMENT)
        self.assertEqual(identity.evidence_ref, ("generation", 7))


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

    def test_generate_returns_an_artifact_id(self) -> None:
        """**この配線が無いと、評価を書く先が本番に存在しない。**"""
        result = self._build()
        self.assertIsNotNone(result.get("artifact"), "生成結果にartifactが付いていない")
        self.assertTrue(result["artifact"]["artifact_id"])
        self.assertTrue(result["artifact"]["fingerprint"])

    def test_generate_does_not_expose_internal_refs(self) -> None:
        """内部refを出すと、任意のrefへ「受け入れた」を書けてしまう。"""
        result = self._build()
        self.assertNotIn("generation_ref", result["artifact"])
        self.assertNotIn("generation_ref", result)

    def test_fingerprint_matches_the_returned_document(self) -> None:
        result = self._build()
        self.assertEqual(
            result["artifact"]["fingerprint"], document_fingerprint(result["forge_document"])
        )

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
        self.assertIsNone(body["rejected"])

        identity = default_artifact_registry().resolve(artifact_id)
        self.assertIsNotNone(identity)
        record = default_generation_store().get(identity.generation_ref)
        self.assertIs(record.user_acceptance, AcceptanceSignal.ACCEPTED)

    def test_feedback_for_an_unknown_artifact_returns_a_reason_not_a_crash(self) -> None:
        response = self.client.post(
            "/api/v1/ai/feedback", json={"signal": "accepted", "artifact_id": "存在しない"},
        )
        self.assertEqual(response.status_code, 200, response.text)
        body = response.json()
        self.assertFalse(body["recorded"])
        self.assertEqual(body["rejected"], "unknown_artifact")

    def test_feedback_with_a_stale_fingerprint_is_rejected(self) -> None:
        result = self._build()
        response = self.client.post(
            "/api/v1/ai/feedback",
            json={
                "signal": "accepted",
                "artifact_id": result["artifact"]["artifact_id"],
                "seen_fingerprint": document_fingerprint({"app": {"title": "別の世代"}}),
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

    def test_every_generation_gets_its_own_artifact_id(self) -> None:
        first = self._build()["artifact"]["artifact_id"]
        second = self._build()["artifact"]["artifact_id"]
        self.assertNotEqual(first, second)


if __name__ == "__main__":
    unittest.main()
