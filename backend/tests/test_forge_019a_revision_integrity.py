"""FORGE-019A Revision Integrity — 独立レビューが挙げたBlocking項目の回帰。

---

## ここが守るもの

019は「変更を意味的に扱う」ところまで作ったが、**その記録が本物である
保証**が足りていなかった。独立レビューが5つの穴を挙げた。

| § | 穴 | このファイルの担当 |
|---|---|---|
| 1 | handleとtokenが正しければ**別のDocument**でも通った | `TestDocumentBinding` |
| 2 | `/converse`のUPDATEだけ旧経路（記録なし） | `TestBothEntryPointsShareOneService` |
| 3 | 本番のRevisionへ**偽のVisual Evidence**が固定で付いていた | `TestVisualEvidenceIsNotFabricated` |
| 4 | 「直してと言われた」だけで教師データ候補になった | `TestRevisionAcceptanceJoin` |
| 5 | 全体再生成fallbackがlineageを1件も残さなかった | `TestFullRegenKeepsLineage` |

いずれも**本番のHTTP経路を実際に叩いて**確かめる。モジュール単体が
正しいことは、本番から呼ばれる証拠にならない（`CLAUDE.md` §3）。
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
from app.ai.gateway.learning_contract import LearningEventType  # noqa: E402
from app.ai.gateway.learning_contract import (  # noqa: E402
    ContributionTarget,
    DataResidency,
    IntelligenceScope,
)
from app.ai.gateway.learning_events import (  # noqa: E402
    AppIdentity,
    AppTrustTier,
    ConsentCategory,
    ConsentSnapshot,
    ProjectionContext,
    QualityState,
    RevisionAcceptanceState,
    TrainingUse,
    default_learning_event_service,
    resolve_revision_acceptance,
)
from app.ai.gateway.revision_evidence import (  # noqa: E402
    RevisionPatchMode,
    default_revision_store,
)

try:
    from fastapi.testclient import TestClient

    from app.main import app

    from tests.revision_fixtures import provision_artifact

    _FASTAPI_AVAILABLE = True
except ImportError:  # pragma: no cover
    _FASTAPI_AVAILABLE = False


#: 生成直後の家計簿は**残高が既に主KPI**なので、「残高を目立たせて」は
#: 何も変えない（FORGE-019Aで、変えない変更は記録しないようにした）。
#: 実際に階層が動く要求を使う。
_LOCAL_INTENT = "収入をもっと目立たせて"

#: 既に満たされている要求。**記録されないこと**を確かめるために使う。
_ALREADY_SATISFIED_INTENT = "残高をもっと目立たせて"
#: 局所的な意味操作へ落とせない要求。全体再生成fallbackを踏ませる。
_UNSUPPORTED_INTENT = "在庫管理の機能も足したい"


@unittest.skipUnless(_FASTAPI_AVAILABLE, "fastapi/pydanticが無い環境ではスキップする")
class _RevisionCase(unittest.TestCase):
    """Evidenceを毎回まっさらにしてから本番経路を叩く共通土台。"""

    def setUp(self) -> None:
        for store in (
            default_generation_store(), default_revision_store(),
            default_artifact_registry(), default_feedback_log(),
            default_learning_event_service(),
        ):
            store.reset()
        self.client = TestClient(app)

    def provision(self):  # noqa: ANN201
        return provision_artifact(self.client)

    def update(self, artifact, intent: str = _LOCAL_INTENT, **overrides):  # noqa: ANN001, ANN201
        return self.client.post(
            "/api/v1/ai/update", json=artifact.update_payload(intent, **overrides),
        )

    def feedback(self, artifact_id: str, token: str, signal: str, key: str = ""):  # noqa: ANN201
        payload = {"signal": signal, "artifact_id": artifact_id,
                   "seen_version_token": token}
        if key:
            payload["idempotency_key"] = key
        return self.client.post("/api/v1/ai/feedback", json=payload)


# ---------------------------------------------------------------------------
# §1 Document binding
# ---------------------------------------------------------------------------


class TestDocumentBinding(_RevisionCase):
    """**handleとtokenが正しくても、別のDocumentは通さない。**

    017Aで`artifact_id`（capability）と`version_token`（世代）を分けたが、
    **Documentそのものは照合していなかった**。Revisionは「その生成物を
    こう直した」という記録なので、直した対象が別物なら記録は嘘になる
    ——handleを持っている人が、自分で書いた任意のJSONを「Forgeが生成した
    ものを直した」ことにできた。
    """

    def test_a_matching_document_is_accepted(self) -> None:
        artifact = self.provision()
        self.assertEqual(self.update(artifact).status_code, 200)

    def test_a_foreign_document_is_rejected(self) -> None:
        """**これが塞いだ穴そのもの。**"""
        artifact = self.provision()
        foreign = self.client.post("/api/v1/ai/update", json={
            "forge_document": {"version": "1.12", "initial_screen_id": "s",
                               "screens": [{"id": "s", "title": "偽", "state": {},
                                            "body": {"type": "column", "id": "r",
                                                     "children": []}}]},
            "change_request": _LOCAL_INTENT,
            "artifact_id": artifact.artifact_id,
            "seen_version_token": artifact.version_token,
        })
        self.assertEqual(foreign.status_code, 422, foreign.text)
        self.assertEqual(foreign.json()["error"]["reached_stage"], "document_binding")

    def test_a_tampered_document_is_rejected(self) -> None:
        """1文字変えただけでも別物である。"""
        artifact = self.provision()
        tampered = dict(artifact.document)
        tampered["app"] = {**tampered.get("app", {}), "title": "書き換えた"}
        response = self.client.post("/api/v1/ai/update", json={
            "forge_document": tampered, "change_request": _LOCAL_INTENT,
            "artifact_id": artifact.artifact_id,
            "seen_version_token": artifact.version_token,
        })
        self.assertEqual(response.status_code, 422, response.text)
        self.assertEqual(response.json()["error"]["reached_stage"], "document_binding")

    def test_no_revision_evidence_is_written_when_binding_fails(self) -> None:
        """**弾いた要求の記録を残さない。** 残すとlineageが汚れる。"""
        artifact = self.provision()
        self.client.post("/api/v1/ai/update", json={
            "forge_document": {"version": "1.12", "screens": []},
            "change_request": _LOCAL_INTENT,
            "artifact_id": artifact.artifact_id,
            "seen_version_token": artifact.version_token,
        })
        self.assertEqual(default_revision_store().all_records(), ())

    def test_a_revision_that_changes_nothing_is_not_recorded(self) -> None:
        """**直していない変更をlineageへ入れない**（FORGE-019A）。

        生成直後の家計簿では、残高は既にその画面の主KPIである。そこへ
        「残高をもっと目立たせて」と言っても、**変わるものが1つも無い**。

        これを成功として記録すると、「直して受け入れられた」という
        嘘の教師信号を作れてしまう——§4が防ごうとしているものを、
        さらに悪い形で起こす。
        """
        artifact = self.provision()
        response = self.update(artifact, _ALREADY_SATISFIED_INTENT)
        self.assertEqual(response.status_code, 422, response.text)
        self.assertEqual(response.json()["error"]["reached_stage"], "no_change")
        self.assertEqual(default_revision_store().all_records(), ())

    def test_the_binding_never_reaches_the_client(self) -> None:
        artifact = self.provision()
        handle = default_artifact_registry().resolve(artifact.artifact_id)
        response = self.update(artifact)
        self.assertNotIn(handle.document_binding, response.text)

    def test_the_chain_rebinds_to_the_revised_document(self) -> None:
        """**連鎖が切れないこと。** 変更後の文書へ束縛し直している。"""
        artifact = self.provision()
        first = self.update(artifact)
        self.assertEqual(first.status_code, 200, first.text)
        result = first.json()["result"]

        second = self.client.post("/api/v1/ai/update", json={
            "forge_document": result["forge_document"],
            "change_request": "支出をもっと目立たせて",
            "artifact_id": result["artifact"]["artifact_id"],
            "seen_version_token": result["artifact"]["version_token"],
        })
        self.assertEqual(second.status_code, 200, second.text)
        self.assertEqual(len(default_revision_store().all_records()), 2)

    def test_the_previous_document_no_longer_binds_after_a_revision(self) -> None:
        """変更前の文書は、もうその版ではない。"""
        artifact = self.provision()
        result = self.update(artifact).json()["result"]
        replayed = self.client.post("/api/v1/ai/update", json={
            "forge_document": artifact.document, "change_request": _LOCAL_INTENT,
            "artifact_id": result["artifact"]["artifact_id"],
            "seen_version_token": result["artifact"]["version_token"],
        })
        self.assertEqual(replayed.status_code, 422, replayed.text)
        self.assertEqual(replayed.json()["error"]["reached_stage"], "document_binding")


# ---------------------------------------------------------------------------
# §2 /update と /converse が同じServiceを通る
# ---------------------------------------------------------------------------


class _ProposesUpdate:
    """会話ステップで`next_action="update"`を返すTest Double。

    `UPDATE`は**LLMがそう提案し、かつ既存ツールがある**ときにだけ選ばれる
    （`conversation_policy.decide_action`）。`mock`はBUILDを提案するので、
    ここを固定しないと`/converse`のUPDATE経路を確定的に踏めない。

    差し替えているのは**会話の判断だけ**で、Revisionの経路は本番のまま。
    実Cloud APIは呼ばない（Gemini quotaを消費しない）。
    """

    def complete_structured(self, prompt: str, schema: dict) -> dict:  # noqa: ARG002
        return {
            "problem": "家計簿の見た目を直したい",
            "known": ["収入をもっと目立たせたい"],
            "unknowns": [], "assumptions": [], "confidence": 0.95,
            "next_action": "update",
            "external_effect": False, "destructive": False,
        }


class TestBothEntryPointsShareOneService(_RevisionCase):
    """**会話がForgeの本線である。**

    019では`/update`だけがSemantic Revisionを通り、`/converse`のUPDATEは
    旧`ForgeOperationEngine`へ直接流れていた。実機で最もよく使われる
    直し方だけがEvidenceを1件も残していなかった。

    013で`/generate`と`/update`の両方にRouter迂回があったのと同じ形
    ——「片方だけ直して終わりにした」。
    """

    def _converse_update(self, artifact, message: str = _LOCAL_INTENT, **overrides):  # noqa: ANN001, ANN202
        from unittest.mock import patch

        payload = {
            "message": message, "provider": "mock",
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

    def test_converse_update_actually_reaches_the_update_branch(self) -> None:
        """前提の確認。ここが`build`だと以下は何も測っていない。"""
        response = self._converse_update(self.provision())
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["status"], "update")

    def test_converse_update_records_a_revision(self) -> None:
        """**§2の本体。** 会話経由でもRevisionRecordが残ること。"""
        response = self._converse_update(self.provision())
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(
            len(default_revision_store().all_records()), 1,
            "会話経由の変更がRevisionRecordを1件も残していない",
        )

    def test_converse_update_emits_the_same_learning_events(self) -> None:
        self._converse_update(self.provision())
        types = [e.event_type for e in default_learning_event_service().local_events]
        self.assertIn(LearningEventType.REVISION, types)
        self.assertIn(LearningEventType.FEEDBACK, types)

    def test_converse_update_returns_an_advanced_artifact(self) -> None:
        artifact = self.provision()
        result = self._converse_update(artifact).json()["result"]
        self.assertNotEqual(result["artifact"]["version_token"], artifact.version_token)
        self.assertEqual(result["revision_mode"], "local_semantic_patch")

    def test_converse_update_uses_a_local_patch_not_a_rebuild(self) -> None:
        """**会話でも全体書き直しにならないこと。**"""
        artifact = self.provision()
        result = self._converse_update(artifact).json()["result"]
        self.assertEqual(result["semantic_operation"], "select_primary_metric")
        self.assertTrue(result["critic_passed"])

    def test_converse_update_rejects_a_foreign_document(self) -> None:
        """**同じ守りが会話側にも効いていること**（§1 × §2）。"""
        artifact = self.provision()
        response = self._converse_update(
            artifact,
            current_document={"version": "1.12", "initial_screen_id": "s",
                              "screens": [{"id": "s", "title": "偽", "state": {},
                                           "body": {"type": "column", "id": "r",
                                                    "children": []}}]},
        )
        self.assertEqual(response.status_code, 422, response.text)
        self.assertIn(
            response.json()["error"]["reached_stage"],
            ("document_binding", "target_resolution", "no_change"),
        )

    def test_converse_update_rejects_a_stale_version(self) -> None:
        artifact = self.provision()
        self.assertEqual(self._converse_update(artifact).status_code, 200)
        replayed = self._converse_update(artifact)
        self.assertEqual(replayed.status_code, 422, replayed.text)
        self.assertEqual(replayed.json()["error"]["reached_stage"], "stale_version")

    def test_converse_update_without_a_capability_fails_closed(self) -> None:
        artifact = self.provision()
        response = self._converse_update(artifact, artifact_id=None, seen_version_token=None)
        self.assertEqual(response.status_code, 422, response.text)
        self.assertEqual(
            response.json()["error"]["reached_stage"], "artifact_capability",
        )

    def test_the_router_has_no_second_revision_implementation(self) -> None:
        """**二重Architectureにしない**（static protocol check）。

        `/converse`が`ForgeOperationEngine`を直接呼ぶ形へ戻っていない
        ことを見る。fallbackは`_full_regen`という1箇所からのみ呼ぶ。
        """
        import inspect

        from app.routers import ai as router_module

        source = inspect.getsource(router_module)
        self.assertEqual(
            source.count("ForgeOperationEngine("), 1,
            "ForgeOperationEngineの呼び出しが複数ある（変更経路が二重になっている）",
        )


# ---------------------------------------------------------------------------
# §3 Visual Evidence を捏造しない
# ---------------------------------------------------------------------------


class TestVisualEvidenceIsNotFabricated(_RevisionCase):
    """**撮っていないものに、撮った証拠を付けない。**

    019は本番のRevisionRecordへ`docs/visual-evidence/FORGE-019/manifest.md`
    を固定で入れていた。実利用者がどんな変更をしても、Golden Financeの
    スクリーンショットが「その証拠」として紐付いた。
    """

    def test_a_production_revision_has_no_visual_evidence(self) -> None:
        artifact = self.provision()
        self.assertEqual(self.update(artifact).status_code, 200)
        record = default_revision_store().all_records()[0]
        self.assertIsNone(
            record.visual_evidence_reference,
            "実利用者の変更へVisual Evidenceが自動で紐付いている",
        )

    def test_no_production_record_points_at_the_forge_019_manifest(self) -> None:
        artifact = self.provision()
        self.update(artifact)
        for record in default_revision_store().all_records():
            self.assertNotIn("FORGE-019", str(record.visual_evidence_reference or ""))

    def test_evidence_can_be_attached_explicitly(self) -> None:
        """実際にrender/captureしたときだけ、後から明示的に付ける。"""
        artifact = self.provision()
        self.update(artifact)
        store = default_revision_store()
        ref = store.all_records()[0].ref
        updated = store.attach_visual_evidence(ref, "docs/visual-evidence/FORGE-019A/manifest.md")
        self.assertEqual(
            updated.visual_evidence_reference,
            "docs/visual-evidence/FORGE-019A/manifest.md",
        )


# ---------------------------------------------------------------------------
# §4 「直してと言われた」は「うまく直せた」ではない
# ---------------------------------------------------------------------------


class TestRevisionAcceptanceJoin(_RevisionCase):
    """**3つの系列を区別する。**

        Generation → CORRECTED → Revision → ACCEPTED      ✅ 正例
        Generation → CORRECTED → Revision → （無言）       ❌ 分からない
        Generation → CORRECTED → Revision → CORRECTED     ❌ 直しても外した

    区別せずに正例へ入れると、**「利用者が不満を言った回数」を「うまく
    直せた回数」として学習する**ことになる。しかも直せなかったケースほど
    `/update`が多く呼ばれるので、**下手な直し方ほど教師データに多く残る**。
    """

    def _revise(self):  # noqa: ANN202
        artifact = self.provision()
        result = self.update(artifact).json()["result"]
        return result["artifact"], default_revision_store().all_records()[0]

    def test_a_revision_without_feedback_is_not_accepted(self) -> None:
        _, record = self._revise()
        self.assertIs(
            resolve_revision_acceptance(record.uid), RevisionAcceptanceState.NO_FEEDBACK,
        )

    def test_an_accepted_revision_is_accepted(self) -> None:
        handle, record = self._revise()
        response = self.feedback(handle["artifact_id"], handle["version_token"], "accepted")
        self.assertTrue(response.json()["recorded"], response.text)
        self.assertIs(
            resolve_revision_acceptance(record.uid), RevisionAcceptanceState.ACCEPTED,
        )

    def test_a_re_corrected_revision_is_not_accepted(self) -> None:
        """**一度はOKと言ったが、使ってみたら直した。**"""
        handle, record = self._revise()
        self.feedback(handle["artifact_id"], handle["version_token"], "accepted", "k1")
        self.feedback(handle["artifact_id"], handle["version_token"], "corrected", "k2")
        self.assertIs(
            resolve_revision_acceptance(record.uid), RevisionAcceptanceState.RE_CORRECTED,
        )

    def test_only_corrected_is_not_accepted(self) -> None:
        handle, record = self._revise()
        self.feedback(handle["artifact_id"], handle["version_token"], "corrected")
        self.assertIs(
            resolve_revision_acceptance(record.uid), RevisionAcceptanceState.RE_CORRECTED,
        )

    def _eligibility(self, record_uid: str) -> tuple[str, ...]:
        service = default_learning_event_service()
        event = next(
            e for e in service.local_events
            if e.event_type is LearningEventType.REVISION
            and e.artifact_evidence_id == record_uid
        )
        consent = ConsentSnapshot.create({
            ConsentCategory.SEMANTIC_CORRECTIONS: True,
            ConsentCategory.USAGE_STATISTICS: True,
        })
        # **収集の権利がある文脈にする。** 既定は local_only / personal /
        # contribution=none なので、そのままでは`collection_not_permitted`で
        # 止まり、§4が見たい「承認されたか」の判定まで到達しない。
        # （既定が fail closed であること自体は正しい。）
        context = ProjectionContext(
            intelligence_scope=IntelligenceScope.GLOBAL,
            data_residency=DataResidency.CLOUD_ELIGIBLE,
            contribution_target=ContributionTarget.GLOBAL,
            app_identity=AppIdentity("forge", AppTrustTier.FORGE_CORE),
            training_use=TrainingUse.ALLOWED,
            provider_terms_allow_training=True,
        )
        # 寄与者IDが無ければ収集そのものが許可されない（fail closed）。
        # ここでは「発行できた」場合の判定を見たいので、テスト用の
        # 発行者を挿す。**本番の既定は`None`のまま**である。
        class _Issuer:
            def issue(self) -> str:
                return "forge-019a-contributor"

        service.set_contributor_identity_provider(_Issuer())
        try:
            service.evaluate_for_export(event, consent=consent, context=context)
        finally:
            service.set_contributor_identity_provider(None)
        return service.evaluations[-1].training_reasons

    def test_an_unaccepted_revision_is_not_a_dataset_candidate(self) -> None:
        """**これが§4の本体。**"""
        _, record = self._revise()
        reasons = self._eligibility(record.uid)
        self.assertIn("revision_not_accepted", reasons)

    def test_an_accepted_revision_can_qualify(self) -> None:
        handle, record = self._revise()
        self.feedback(handle["artifact_id"], handle["version_token"], "accepted")
        reasons = self._eligibility(record.uid)
        self.assertNotIn("revision_not_accepted", reasons)
        self.assertNotIn("revision_re_corrected", reasons)

    def test_a_re_corrected_revision_is_disqualified(self) -> None:
        handle, record = self._revise()
        self.feedback(handle["artifact_id"], handle["version_token"], "accepted", "k1")
        self.feedback(handle["artifact_id"], handle["version_token"], "corrected", "k2")
        self.assertIn("revision_re_corrected", self._eligibility(record.uid))

    def test_a_later_correction_revokes_an_existing_candidate(self) -> None:
        """**記録は書き換えず、Forgeの判断だけを取り下げる。**"""
        handle, record = self._revise()
        self.feedback(handle["artifact_id"], handle["version_token"], "accepted", "k1")
        self._eligibility(record.uid)
        service = default_learning_event_service()
        created = [c for c in service.dataset_candidates
                   if record.uid in c.source_artifact_ids]
        self.assertTrue(created, "承認済みRevisionの候補が作られていない")

        self.feedback(handle["artifact_id"], handle["version_token"], "corrected", "k2")
        revoked = [c for c in service.dataset_candidates
                   if record.uid in c.source_artifact_ids]
        self.assertTrue(
            all(c.quality_state is QualityState.REVOKED for c in revoked),
            "後から否定されたのに候補が残っている",
        )

    def test_the_feedback_events_are_never_rewritten(self) -> None:
        """**Learning Eventは追記専用のまま。**"""
        handle, record = self._revise()
        self.feedback(handle["artifact_id"], handle["version_token"], "accepted", "k1")
        before = [e.event_id for e in default_feedback_log().all_events()]
        self.feedback(handle["artifact_id"], handle["version_token"], "corrected", "k2")
        after = [e.event_id for e in default_feedback_log().all_events()]
        self.assertEqual(after[: len(before)], before, "過去のEventが書き換えられている")
        self.assertGreater(len(after), len(before))


# ---------------------------------------------------------------------------
# §5 全体再生成fallbackもlineageを残す
# ---------------------------------------------------------------------------


class TestFullRegenKeepsLineage(_RevisionCase):
    """**fallbackもRevisionである。**

    019ではfallbackだけEvidenceを1件も残さず、「Revisionが起きた事実」が
    消えていた。局所patchのふりもしない——`patch_mode`で区別する。

    ---

    ## AIの答えだけをTest Doubleにする

    `mock`が全体再生成で返すJSONはValidatorを通ったり通らなかったりする
    ので、そのままではlineageを確定的に測れない。

    差し替えるのは**AIが返す文書だけ**であり、Router→RevisionService→
    capability照合→Validator→RevisionRecord→Feedback→LearningEvent→
    artifact前進という**経路は本番のまま**である。実Cloud APIは呼ばない。
    """

    def _revised_document(self, base: dict) -> dict:
        """AIが返したことにする文書。**実際に別物になっている。**"""
        from copy import deepcopy

        revised = deepcopy(base)
        revised.setdefault("app", {})["title"] = "在庫も見られる家計簿"
        return revised

    def _fallback(self, artifact):  # noqa: ANN001, ANN202
        from unittest.mock import patch

        from app.ai.runtime.forge_operation import UpdateResult
        from app.ai.validators.schema_validator import validate_forge_document

        revised = self._revised_document(artifact.document)

        def _apply(self_engine, document, change_request):  # noqa: ANN001, ARG001
            return UpdateResult(
                success=True, forge_document=revised,
                validation=validate_forge_document(revised), attempts=1,
            )

        with patch(
            "app.ai.runtime.forge_operation.ForgeOperationEngine.apply_update", _apply,
        ):
            return revised, self.update(artifact, _UNSUPPORTED_INTENT)

    def test_a_fallback_records_a_revision(self) -> None:
        """**§5の本体。** fallbackがlineageを残すこと。"""
        _, response = self._fallback(self.provision())
        self.assertEqual(response.status_code, 200, response.text)
        records = default_revision_store().all_records()
        self.assertEqual(len(records), 1, "fallbackがRevisionRecordを残していない")
        self.assertIs(records[0].patch_mode, RevisionPatchMode.FULL_REGEN_FALLBACK)

    def test_a_fallback_never_claims_to_be_a_local_patch(self) -> None:
        _, response = self._fallback(self.provision())
        result = response.json()["result"]
        self.assertEqual(result["revision_mode"], "full_regen_fallback")
        self.assertIsNone(result["semantic_operation"])
        self.assertFalse(
            result["critic_passed"],
            "Criticを通していないものをPASSと報告している",
        )

    def test_a_fallback_records_why_it_fell_back(self) -> None:
        self._fallback(self.provision())
        self.assertTrue(
            default_revision_store().all_records()[0].fallback_reason,
            "なぜ局所操作へ落とせなかったのかが残っていない",
        )

    def test_a_fallback_emits_the_revision_learning_event(self) -> None:
        self._fallback(self.provision())
        types = [e.event_type for e in default_learning_event_service().local_events]
        self.assertIn(LearningEventType.REVISION, types)
        self.assertIn(LearningEventType.FEEDBACK, types)

    def test_a_fallback_advances_the_artifact_and_rebinds(self) -> None:
        """**次の変更へ繋がること。** 束縛し直していないと連鎖が切れる。"""
        artifact = self.provision()
        revised, response = self._fallback(artifact)
        advanced = response.json()["result"]["artifact"]
        self.assertNotEqual(advanced["version_token"], artifact.version_token)

        handle = default_artifact_registry().resolve(advanced["artifact_id"])
        self.assertTrue(handle.binds(revised), "変更後の文書へ束縛し直していない")

    def test_a_fallback_writes_no_fake_visual_evidence(self) -> None:
        self._fallback(self.provision())
        self.assertIsNone(
            default_revision_store().all_records()[0].visual_evidence_reference,
        )

    def test_a_fallback_is_not_a_training_candidate_without_acceptance(self) -> None:
        """**§4はfallbackにも効く。**"""
        self._fallback(self.provision())
        record = default_revision_store().all_records()[0]
        self.assertIs(
            resolve_revision_acceptance(record.uid), RevisionAcceptanceState.NO_FEEDBACK,
        )

    def test_a_fallback_still_requires_a_capability(self) -> None:
        """**§5: fallbackもcapabilityとbindingを通る。**"""
        response = self.client.post("/api/v1/ai/update", json={
            "forge_document": {"version": "1.12", "screens": []},
            "change_request": _UNSUPPORTED_INTENT,
        })
        self.assertEqual(response.status_code, 422, response.text)
        self.assertEqual(
            response.json()["error"]["reached_stage"], "artifact_capability",
        )

    def test_a_fallback_rejects_a_foreign_document(self) -> None:
        artifact = self.provision()
        response = self.client.post("/api/v1/ai/update", json={
            "forge_document": {"version": "1.12", "initial_screen_id": "s",
                               "screens": [{"id": "s", "title": "偽", "state": {},
                                            "body": {"type": "column", "id": "r",
                                                     "children": []}}]},
            "change_request": _UNSUPPORTED_INTENT,
            "artifact_id": artifact.artifact_id,
            "seen_version_token": artifact.version_token,
        })
        self.assertEqual(response.status_code, 422, response.text)
        self.assertEqual(response.json()["error"]["reached_stage"], "document_binding")


if __name__ == "__main__":
    unittest.main()
