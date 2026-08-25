"""FORGE-019B — Revision の transaction / retry / provider 帰属の回帰。

---

## このファイルは「先に落とす」ために書いた

独立レビューが挙げた4点は、いずれも**現在のコードで再現できる**。
直す前にここへ再現を書き、FAIL することを確かめてから実装を変えた。

| § | 何が起きるか |
|---|---|
| 1 | Feedback が失敗しても RevisionRecord と LearningEvent が残る（孤児） |
| 2 | 応答が届かなかった Client の再送が `stale_version` で必ず失敗する |
| 3 | 別の生成物で同じ idempotency key を使うと重複扱いになる |
| 4 | 実際に文書を変えた Provider ではなく、会話の Provider が返る |
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
    ArtifactEvidenceId,
    EvidenceKind,
    default_artifact_registry,
    default_feedback_log,
)
from app.ai.gateway.generation_evidence import default_generation_store  # noqa: E402
from app.ai.gateway.learning_contract import LearningEventType  # noqa: E402
from app.ai.gateway.learning_events import default_learning_event_service  # noqa: E402
from app.ai.gateway.learning_foundation import AcceptanceSignal  # noqa: E402
from app.ai.gateway.revision_evidence import default_revision_store  # noqa: E402
from app.ai.runtime.revision_service import default_replay_log  # noqa: E402

try:
    from fastapi.testclient import TestClient

    from app.main import app

    from tests.revision_fixtures import provision_artifact

    _FASTAPI_AVAILABLE = True
except ImportError:  # pragma: no cover
    _FASTAPI_AVAILABLE = False


_LOCAL_INTENT = "収入をもっと目立たせて"
_SECOND_INTENT = "支出をもっと目立たせて"
_UNSUPPORTED_INTENT = "在庫管理の機能も足したい"


@unittest.skipUnless(_FASTAPI_AVAILABLE, "fastapi/pydanticが無い環境ではスキップする")
class _RevisionCase(unittest.TestCase):
    def setUp(self) -> None:
        for store in (
            default_generation_store(), default_revision_store(),
            default_artifact_registry(), default_feedback_log(),
            default_learning_event_service(),
            # 再送のreplay記録もプロセス内グローバルなので、ここで消さないと
            # 前のテストの成功結果が次のテストへ漏れる（FORGE-019B §2）。
            default_replay_log(),
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
        """Evidence の件数。**partial が残っていないかを1つの目で見る。**"""
        service = default_learning_event_service()
        return {
            "revisions": len(default_revision_store().all_records()),
            "feedback": default_feedback_log().size(),
            "learning": len(service.local_events),
        }


# ---------------------------------------------------------------------------
# §1 Revision は atomic でなければならない
# ---------------------------------------------------------------------------


class TestRevisionIsAtomic(_RevisionCase):
    """**途中で失敗したら、何も残さない。**

    現在の `_record()` は

        RevisionRecord.record()   ← ここで LearningEvent も出る
        → Feedback.record()       ← ここで失敗しうる
        → artifact advance

    の順なので、Feedback が失敗すると API は 422 を返すのに
    **RevisionRecord と REVISION LearningEvent は Store に残る**。

    残った記録は、対応する CORRECTED Feedback を持たない孤児である。
    §4（019A）で入れた「Feedback列をjoinして Dataset 適格性を決める」は、
    孤児を `NO_FEEDBACK` として扱う——つまり**永久に評価されない記録**が
    Evidence を汚し続ける。
    """

    def test_a_failing_feedback_leaves_no_revision_record(self) -> None:
        artifact = self.provision()
        first = self.update(artifact, _LOCAL_INTENT, idempotency_key="K")
        self.assertEqual(first.status_code, 200, first.text)
        result = first.json()["result"]
        before = self.counts()

        # 2回目は artifact / token / document すべて正しいが、
        # **同じ idempotency key** なので Feedback が重複として弾かれる。
        second = self.client.post("/api/v1/ai/update", json={
            "forge_document": result["forge_document"],
            "change_request": _SECOND_INTENT,
            "artifact_id": result["artifact"]["artifact_id"],
            "seen_version_token": result["artifact"]["version_token"],
            "idempotency_key": "K",
        })

        self.assertNotEqual(
            second.status_code, 200,
            "この再現は「Feedbackが失敗する」ことが前提。成功したら前提が崩れている",
        )
        self.assertEqual(
            self.counts(), before,
            "失敗したのに Evidence が増えている（partial Evidence が残った）",
        )

    def test_a_failed_revision_does_not_advance_the_artifact(self) -> None:
        artifact = self.provision()
        first = self.update(artifact, _LOCAL_INTENT, idempotency_key="K").json()["result"]
        token_before = first["artifact"]["version_token"]

        self.client.post("/api/v1/ai/update", json={
            "forge_document": first["forge_document"],
            "change_request": _SECOND_INTENT,
            "artifact_id": first["artifact"]["artifact_id"],
            "seen_version_token": token_before,
            "idempotency_key": "K",
        })

        handle = default_artifact_registry().resolve(first["artifact"]["artifact_id"])
        self.assertEqual(
            handle.version_token, token_before,
            "失敗したのに artifact が進んでいる",
        )

    def test_a_failed_revision_emits_no_learning_event(self) -> None:
        artifact = self.provision()
        first = self.update(artifact, _LOCAL_INTENT, idempotency_key="K").json()["result"]
        before = len(default_learning_event_service().local_events)

        self.client.post("/api/v1/ai/update", json={
            "forge_document": first["forge_document"],
            "change_request": _SECOND_INTENT,
            "artifact_id": first["artifact"]["artifact_id"],
            "seen_version_token": first["artifact"]["version_token"],
            "idempotency_key": "K",
        })

        self.assertEqual(
            len(default_learning_event_service().local_events), before,
            "失敗したのに LearningEvent が出ている（孤児の REVISION が残る）",
        )

    def test_every_revision_has_the_correction_that_caused_it(self) -> None:
        """**不変条件。** すべての RevisionRecord に、それを生んだ
        CORRECTED が対応している。

        CORRECTED は**直された側**（元の生成物 / 直前の変更）へ付く
        ——「これは外していた」という評価だからである。Revision 自身は
        評価が付いていない状態で生まれ、あとで ACCEPTED / CORRECTED を
        受ける（019A §4）。

        したがって孤児かどうかは「その Revision の**base**に CORRECTED が
        あるか」で見る。transaction が壊れると、base に CORRECTED が無い
        まま Revision だけが残る。
        """
        artifact = self.provision()
        first = self.update(artifact, _LOCAL_INTENT, idempotency_key="K").json()["result"]
        self.client.post("/api/v1/ai/update", json={
            "forge_document": first["forge_document"],
            "change_request": _SECOND_INTENT,
            "artifact_id": first["artifact"]["artifact_id"],
            "seen_version_token": first["artifact"]["version_token"],
            "idempotency_key": "K",
        })

        log = default_feedback_log()
        generations = default_generation_store()
        revisions = default_revision_store()
        self.assertTrue(revisions.all_records(), "1件目すら記録されていない")

        for record in revisions.all_records():
            if record.previous_revision_ref is not None:
                previous = revisions.get(record.previous_revision_ref)
                base = ArtifactEvidenceId(
                    EvidenceKind.REVISION, previous.uid, previous.ref,
                )
            else:
                generation = generations.get(record.base_generation_ref)
                base = ArtifactEvidenceId(
                    EvidenceKind.GENERATION, generation.uid, generation.ref,
                )
            with self.subTest(revision=record.ref):
                self.assertTrue(
                    any(
                        e.signal is AcceptanceSignal.CORRECTED
                        for e in log.for_evidence(base)
                    ),
                    f"Revision {record.ref} を生んだ CORRECTED が無い（孤児の記録）",
                )


class TestCommitFailureRollsBack(_RevisionCase):
    """**commit の途中で落ちたら、staged を巻き戻す。**

    ---

    ## なぜ失敗を注入するのか

    §2 で再送を replay するようにしたので、「同じキーで2回目」という
    元の再現手順は **`idempotency_conflict` で先に止まる**——transaction
    の中まで届かなくなった。

    そのままだと、`TestRevisionIsAtomic` は「transaction を壊しても
    落ちないテスト」＝置物になる（実際、mutation B1 で確認した）。

    そこで commit 相当の段で**確実に失敗させて**、
    partial Evidence が残らないことを直接見る。
    """

    def _counts_and_token(self, artifact):  # noqa: ANN001, ANN202
        handle = default_artifact_registry().resolve(artifact.artifact_id)
        return self.counts(), handle.version_token

    def test_a_failure_while_recording_the_correction_leaves_nothing(self) -> None:
        """**FORGE-019C で注入先が変わった。**

        019B は `ArtifactFeedbackService.record` を差し替えていたが、
        019C の本番経路は `prepare()` → `commit_prepared()` を通る。
        `record()` を差し替えても**本番はもうそこを通らない**ので、
        このテストは置物になっていた（実際 019C の実装後に PASS した）。

        いま落とすのは、本番が実際に通る `commit_prepared()` である。
        """
        from unittest.mock import patch

        from app.ai.gateway.artifact_feedback import FeedbackRejected, FeedbackResult

        artifact = self.provision()
        before, token_before = self._counts_and_token(artifact)

        def _rejects(self_service, staged):  # noqa: ANN001, ARG001
            return FeedbackResult(
                False, AcceptanceSignal.CORRECTED,
                rejected=FeedbackRejected.UNKNOWN_ARTIFACT,
            )

        with patch(
            "app.ai.gateway.artifact_feedback.ArtifactFeedbackService.commit_prepared",
            _rejects,
        ):
            response = self.update(artifact)

        self.assertEqual(response.status_code, 422, response.text)
        self.assertEqual(
            self.counts(), before,
            "commit が失敗したのに Evidence が残っている（巻き戻していない）",
        )
        self.assertEqual(
            default_artifact_registry().resolve(artifact.artifact_id).version_token,
            token_before, "失敗したのに版が進んでいる",
        )

    def test_an_exception_while_advancing_leaves_no_revision_record(self) -> None:
        from unittest.mock import patch

        artifact = self.provision()
        revisions_before = len(default_revision_store().all_records())
        learning_before = len(default_learning_event_service().local_events)

        def _boom(self_registry, **kwargs):  # noqa: ANN001, ARG001
            msg = "advance failed"
            raise RuntimeError(msg)

        with patch(
            "app.ai.gateway.artifact_feedback.ArtifactRegistry.advance_to_revision", _boom,
        ), self.assertRaises(RuntimeError):
            self.update(artifact)

        self.assertEqual(
            len(default_revision_store().all_records()), revisions_before,
            "例外で落ちたのに RevisionRecord が残っている",
        )
        # **FORGE-019C で仕様が変わった。**
        #
        # 019B はここを `learning_before + 1`（CORRECTED だけ残る）と
        # 書いていた。追記専用の Feedback log は巻き戻せない、という
        # 理由だった。
        #
        # しかし**追記していなければ巻き戻す必要も無い**。019C で
        # 「CAS で版を進めてから追記する」順序にしたので、advance が
        # 落ちた時点で追記はまだ起きていない。したがって
        # **partial Evidence は1件も残らない**。
        self.assertEqual(
            len(default_learning_event_service().local_events), learning_before,
            "論理的に失敗した Revision の Evidence が残っている（019C §3.1）",
        )
        self.assertNotIn(
            LearningEventType.REVISION,
            [e.event_type for e in default_learning_event_service().local_events],
            "巻き戻したのに REVISION の Learning Event が出ている（孤児）",
        )
        self.assertEqual(
            default_feedback_log().size(), 0,
            "巻き戻したのに CORRECTED の Feedback が残っている（019C §3.1）",
        )

    def test_the_staged_record_never_becomes_visible(self) -> None:
        """**巻き戻した record は誰にも見えない。**"""
        from unittest.mock import patch

        from app.ai.gateway.artifact_feedback import FeedbackRejected, FeedbackResult

        artifact = self.provision()

        def _rejects(self_service, staged):  # noqa: ANN001, ARG001
            return FeedbackResult(
                False, AcceptanceSignal.CORRECTED,
                rejected=FeedbackRejected.UNKNOWN_ARTIFACT,
            )

        with patch(
            "app.ai.gateway.artifact_feedback.ArtifactFeedbackService.commit_prepared",
            _rejects,
        ):
            self.update(artifact)

        self.assertEqual(default_revision_store().all_records(), ())
        self.assertEqual(default_revision_store().size(), 0)

    def test_a_rejected_admission_writes_nothing_at_all(self) -> None:
        """**書く前に断る**（`admit()`）。

        巻き戻しがあるので外から見た結果は同じだが、**そもそも書かない**
        方が安い。ここは深さの違う2枚目の守りである。
        """
        from unittest.mock import patch

        from app.ai.gateway.artifact_feedback import FeedbackRejected

        artifact = self.provision()
        before = self.counts()

        with patch(
            "app.ai.gateway.artifact_feedback.ArtifactFeedbackService.prepare",
            lambda self_service, **kwargs: FeedbackRejected.DUPLICATE_REQUEST,
        ):
            response = self.update(artifact)

        self.assertEqual(response.status_code, 422, response.text)
        self.assertEqual(response.json()["error"]["reached_stage"], "revision_evidence")
        self.assertEqual(self.counts(), before)


# ---------------------------------------------------------------------------
# §2 Revision そのものの冪等性
# ---------------------------------------------------------------------------


class TestRevisionRetryReplays(_RevisionCase):
    """**応答が届かなかった再送を、成功として返す。**

    019A で Flutter は「同じ操作の再送は同じキー」にした。しかし
    **Backend の Revision 自体は冪等でない**ので、

        1. V1 で Revision 成功（サーバは V2 へ進む）
        2. 応答が Client へ届かない
        3. Client は V1・古い文書・同じキーで再送
        4. サーバは `stale_version` で拒否

    となる。利用者から見ると「直したのに直っていない」うえ、もう一度
    押しても永久に通らない。**通信が切れただけで詰む。**
    """

    def _first(self):  # noqa: ANN202
        artifact = self.provision()
        response = self.update(artifact, _LOCAL_INTENT, idempotency_key="retry-1")
        self.assertEqual(response.status_code, 200, response.text)
        return artifact, response.json()["result"]

    def test_the_same_request_replays_instead_of_failing(self) -> None:
        artifact, first = self._first()
        replay = self.update(artifact, _LOCAL_INTENT, idempotency_key="retry-1")
        self.assertEqual(
            replay.status_code, 200,
            "届かなかった応答の再送が通らない（通信が切れただけで詰む）",
        )

    def test_a_replay_returns_the_same_document(self) -> None:
        artifact, first = self._first()
        replay = self.update(artifact, _LOCAL_INTENT, idempotency_key="retry-1")
        self.assertEqual(replay.json()["result"]["forge_document"], first["forge_document"])

    def test_a_replay_returns_the_same_artifact_version(self) -> None:
        artifact, first = self._first()
        replay = self.update(artifact, _LOCAL_INTENT, idempotency_key="retry-1")
        self.assertEqual(replay.json()["result"]["artifact"], first["artifact"])

    def test_a_replay_creates_no_second_revision(self) -> None:
        artifact, _ = self._first()
        before = self.counts()
        self.update(artifact, _LOCAL_INTENT, idempotency_key="retry-1")
        self.assertEqual(self.counts(), before, "再送で Evidence が二重に増えている")

    def test_a_replay_does_not_advance_the_artifact_again(self) -> None:
        artifact, first = self._first()
        self.update(artifact, _LOCAL_INTENT, idempotency_key="retry-1")
        handle = default_artifact_registry().resolve(first["artifact"]["artifact_id"])
        self.assertEqual(handle.version_token, first["artifact"]["version_token"])

    def test_the_same_key_with_a_different_request_is_refused(self) -> None:
        """**キーだけで検査を迂回させない。** 内容が違えば replay しない。"""
        artifact, _ = self._first()
        different = self.update(artifact, _SECOND_INTENT, idempotency_key="retry-1")
        self.assertNotEqual(
            different.status_code, 200,
            "同じキーで別の要求が通っている（fail closed になっていない）",
        )

    def test_the_same_key_with_a_different_document_is_refused(self) -> None:
        artifact, _ = self._first()
        response = self.client.post("/api/v1/ai/update", json={
            "forge_document": {"version": "1.12", "initial_screen_id": "s",
                               "screens": [{"id": "s", "title": "偽", "state": {},
                                            "body": {"type": "column", "id": "r",
                                                     "children": []}}]},
            "change_request": _LOCAL_INTENT,
            "artifact_id": artifact.artifact_id,
            "seen_version_token": artifact.version_token,
            "idempotency_key": "retry-1",
        })
        self.assertNotEqual(response.status_code, 200)

    def test_the_same_key_on_a_different_artifact_is_refused(self) -> None:
        artifact, _ = self._first()
        other = self.provision()
        response = self.update(other, _LOCAL_INTENT, idempotency_key="retry-1")
        self.assertNotEqual(
            response.status_code, 200,
            "別の生成物へ、他の生成物のreplayが返っている",
        )

    def test_without_a_key_a_repeat_is_not_a_replay(self) -> None:
        """**キーが無ければ再送とみなさない**（017A §2 と同じ姿勢）。"""
        artifact = self.provision()
        self.assertEqual(self.update(artifact, _LOCAL_INTENT).status_code, 200)
        # 1回目で版が進んでいるので、キー無しの再送は stale で弾かれる。
        self.assertNotEqual(self.update(artifact, _LOCAL_INTENT).status_code, 200)


# ---------------------------------------------------------------------------
# §3 Feedback の idempotency scope
# ---------------------------------------------------------------------------


class TestFeedbackIdempotencyIsScoped(_RevisionCase):
    """**別の生成物で同じキーを使っても、重複ではない。**

    `FeedbackEventLog._by_idempotency` は raw key だけの global dict
    なので、Client が単純な連番キーを使うと、無関係な生成物への評価が
    「重複」として捨てられる。**評価が黙って消える。**
    """

    def _artifact_with_feedback_target(self):  # noqa: ANN202
        artifact = self.provision()
        return artifact

    def test_the_same_key_on_two_artifacts_records_both(self) -> None:
        first = self._artifact_with_feedback_target()
        second = self._artifact_with_feedback_target()

        a = self.client.post("/api/v1/ai/feedback", json={
            "signal": "accepted", "artifact_id": first.artifact_id,
            "seen_version_token": first.version_token, "idempotency_key": "k1",
        })
        b = self.client.post("/api/v1/ai/feedback", json={
            "signal": "accepted", "artifact_id": second.artifact_id,
            "seen_version_token": second.version_token, "idempotency_key": "k1",
        })

        self.assertTrue(a.json()["recorded"], a.text)
        self.assertTrue(
            b.json()["recorded"],
            "別の生成物への評価が、キーが同じというだけで捨てられている",
        )

    def test_the_same_key_on_the_same_artifact_is_still_a_duplicate(self) -> None:
        """**緩めすぎていないこと。**"""
        artifact = self.provision()
        payload = {
            "signal": "accepted", "artifact_id": artifact.artifact_id,
            "seen_version_token": artifact.version_token, "idempotency_key": "k1",
        }
        self.assertTrue(self.client.post("/api/v1/ai/feedback", json=payload).json()["recorded"])
        second = self.client.post("/api/v1/ai/feedback", json=payload).json()
        self.assertFalse(second["recorded"])
        self.assertEqual(second["rejected"], "duplicate_request")


# ---------------------------------------------------------------------------
# §4 Provider の帰属
# ---------------------------------------------------------------------------


class _ProposesUpdate:
    """会話ステップで `next_action="update"` を返す Test Double。"""

    def complete_structured(self, prompt: str, schema: dict) -> dict:  # noqa: ARG002
        return {
            "problem": "家計簿の見た目を直したい",
            "known": ["収入をもっと目立たせたい"],
            "unknowns": [], "assumptions": [], "confidence": 0.95,
            "next_action": "update",
            "external_effect": False, "destructive": False,
        }


class TestProviderAttribution(_RevisionCase):
    """**実際に文書を変えたのが誰かを、失わない。**

    局所 patch は Forge の決定的な操作であって LLM を1回も呼ばない。
    それを「gemini が直しました」と報告するのは嘘である。

    全体再生成へ落ちた場合は、会話の Provider ではなく
    **実際に生成した Provider** を返さなければならない。
    """

    def _converse_update(self, artifact, **overrides):  # noqa: ANN001, ANN202
        from unittest.mock import patch

        payload = {
            "message": _LOCAL_INTENT, "provider": "mock",
            "current_document": artifact.document,
            "artifact_id": artifact.artifact_id,
            "seen_version_token": artifact.version_token,
        }
        payload.update(overrides)
        with patch(
            "app.ai.runtime.conversation_engine.ConversationEngine.__init__",
            lambda self, provider=None: setattr(self, "_provider", _ProposesUpdate()),
        ):
            return self.client.post("/api/v1/ai/converse", json=payload)

    def test_a_local_patch_does_not_claim_an_llm_provider(self) -> None:
        """**LLMを使っていないのに、使ったように言わない。**"""
        artifact = self.provision()
        result = self.update(artifact).json()["result"]
        self.assertEqual(
            result.get("revision_provider"), "forge_deterministic",
            "局所patchなのに LLM Provider を名乗っている",
        )

    def _fallback_with_real_router(self, artifact):  # noqa: ANN001, ANN202
        """全体再生成を、**Routerを本当に通して**踏ませる。

        差し替えるのは Provider が返す JSON だけ。`AIRouter` も
        `_BoundAdapter` も本番のまま通るので、`last_provider_used` は
        実際に使われた Provider として記録される。

        `mock` の素の出力は Validator を通ったり通らなかったりする
        （スイート順序に依存する。TECH_DEBT 参照）ので、そこだけ固定する。
        """
        from unittest.mock import patch

        revised = {**artifact.document, "app": {"title": "在庫も見られる家計簿"}}

        def _complete_structured(self_adapter, prompt, response_schema):  # noqa: ANN001, ARG001
            return revised

        with patch(
            "app.ai.foundation.providers.MockLLMAdapter.complete_structured",
            _complete_structured,
        ):
            return revised, self.update(artifact, _UNSUPPORTED_INTENT)

    def test_a_fallback_reports_the_provider_that_actually_generated(self) -> None:
        """**会話のProviderではなく、実際に生成したProviderを返す。**"""
        artifact = self.provision()
        _, response = self._fallback_with_real_router(artifact)

        self.assertEqual(response.status_code, 200, response.text)
        result = response.json()["result"]
        self.assertEqual(result["revision_mode"], "full_regen_fallback")
        self.assertEqual(
            result.get("revision_provider"), "mock",
            "全体再生成なのに、実際に生成したProviderが返っていない",
        )
        self.assertNotEqual(result.get("revision_provider"), "forge_deterministic")

    def test_a_fallback_records_the_real_provider_in_evidence(self) -> None:
        """Evidence 側にも実際のProviderが残ること。"""
        artifact = self.provision()
        _, response = self._fallback_with_real_router(artifact)
        self.assertEqual(response.status_code, 200, response.text)

        record = default_revision_store().all_records()[-1]
        self.assertEqual(record.provider_id, "mock")

    def test_converse_separates_conversation_and_revision_provider(self) -> None:
        """会話の Provider と、実際に直した Provider を混ぜない。"""
        artifact = self.provision()
        body = self._converse_update(artifact).json()
        self.assertEqual(body["status"], "update", body)
        self.assertEqual(
            body["result"].get("revision_provider"), "forge_deterministic",
            "会話経由の局所patchが LLM Provider を名乗っている",
        )

    def test_the_revision_learning_event_carries_the_real_provider(self) -> None:
        """**Evidence 側でも嘘にならないこと。**"""
        artifact = self.provision()
        self.assertEqual(self.update(artifact).status_code, 200)
        events = [
            e for e in default_learning_event_service().local_events
            if e.event_type is LearningEventType.REVISION
        ]
        self.assertTrue(events)
        self.assertNotEqual(
            events[-1].provider_id, "gemini",
            "局所patchの Evidence が LLM Provider を名乗っている",
        )


if __name__ == "__main__":
    unittest.main()
