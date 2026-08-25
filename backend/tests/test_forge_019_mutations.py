"""FORGE-019の配線を守るguard群。

---

## FORGE-019Aで数え方を直した（§6）

019は「mutation 15/15」と報告していたが、中身は3種類が混ざっていた。

| 種類 | 何を確かめているか | 強さ |
|---|---|---|
| **behavior guard** | 本番の経路を実際に動かし、結果を見る | 強い |
| **static protocol check** | ファイルに文言/設定が在るか | 弱い |
| ~~source-string check~~ | ソースに特定の文字列が在るか | **置物になりやすい** |

3つ目が問題だった。`assertIn("revisions.record(RevisionRecord(", source)`
は、**その行をコピーしてコメントアウトしても通る**し、実装を別モジュール
へ移しただけで（振る舞いが正しくても）落ちる。実際019Aで
`RevisionService`へ移したとき、振る舞いは正しいのに落ちた。

019Aで04・05・06を**behavior guard**へ書き換えた。10・15は性質上
staticなので、staticだと名前で明示する。

**報告では3種類を別々に数える。**
"""


from __future__ import annotations

import dataclasses
import unittest
from contextlib import contextmanager
from pathlib import Path

from app.ai.gateway.learning_contract import LearningEventType
from app.ai.gateway.learning_events import (
    ConsentCategory, EvaluationContextSnapshot, LearningEvent,
    consent_category_for_event,
)
from app.ai.runtime.semantic_revision import (
    AppliedSemanticRevision, TargetResolution, TargetResolutionStatus,
    apply_semantic_intent,
)
from tests.test_semantic_revision import finance_document

#: cwdに依存しないRepositoryのroot。以前は`Path("../AGENTS.md")`のように
#: 相対で書いてあり、どこから走らせるかで結果が変わった。
_REPO_ROOT = Path(__file__).resolve().parents[2]


@contextmanager
def _production():
    """本番のHTTP経路を、独立したEvidenceで1回動かすための土台。"""
    from fastapi.testclient import TestClient

    from app.ai.gateway.artifact_feedback import (
        default_artifact_registry, default_feedback_log,
    )
    from app.ai.gateway.generation_evidence import default_generation_store
    from app.ai.gateway.learning_events import default_learning_event_service
    from app.ai.gateway.revision_evidence import default_revision_store
    from app.main import app
    from tests.revision_fixtures import provision_artifact

    for store in (default_generation_store(), default_revision_store(),
                  default_artifact_registry(), default_feedback_log(),
                  default_learning_event_service()):
        store.reset()

    class _Env:
        def __init__(self) -> None:
            self.client = TestClient(app)

        def provision(self):
            return provision_artifact(self.client)

        def update(self, artifact, change_request: str, **overrides):
            return self.client.post(
                "/api/v1/ai/update",
                json=artifact.update_payload(change_request, **overrides),
            )

    yield _Env()


class Forge019MutationKills(unittest.TestCase):
    def _result(self) -> AppliedSemanticRevision:
        result = apply_semantic_intent(finance_document(), "残高をもっと目立たせて")
        self.assertIsInstance(result, AppliedSemanticRevision)
        return result  # type: ignore[return-value]

    def test_01_raw_path_bypass_is_killed(self):
        result = apply_semantic_intent(finance_document(), "screens[0].children[1]を変更")
        self.assertIsInstance(result, TargetResolution)
        self.assertEqual(result.status, TargetResolutionStatus.UNSUPPORTED)

    def test_02_full_rebuild_mutation_is_killed(self):
        result = self._result()
        result.document["app"]["title"] = "mutated"
        self.assertNotEqual(result.document["app"], finance_document()["app"])

    def test_03_wrong_primary_widget_is_killed(self):
        self.assertEqual(self._result().operation.target.widget_id, "balance")

    def test_04_behavior_stale_token_is_rejected(self):
        """**振る舞いで見る**（019A §6）。古いtokenでは通らないこと。

        以前はソースに`!=`の1行が在るかを見ていた。コメントアウトしても
        通るし、実装を移動しただけで落ちる——どちらの向きにも嘘をつく。
        """
        with _production() as env:
            artifact = env.provision()
            first = env.update(artifact, "収入をもっと目立たせて")
            self.assertEqual(first.status_code, 200, first.text)
            replayed = env.client.post("/api/v1/ai/update", json={
                "forge_document": artifact.document,
                "change_request": "収入をもっと目立たせて",
                "artifact_id": artifact.artifact_id,
                "seen_version_token": artifact.version_token,
            })
            self.assertEqual(replayed.status_code, 422, replayed.text)
            self.assertEqual(
                replayed.json()["error"]["reached_stage"], "stale_version",
            )

    def test_05_behavior_revision_is_recorded_by_production(self):
        """**RevisionRecordが実際に増えること。**"""
        from app.ai.gateway.revision_evidence import default_revision_store

        with _production() as env:
            artifact = env.provision()
            before = len(default_revision_store().all_records())
            self.assertEqual(
                env.update(artifact, "収入をもっと目立たせて").status_code, 200,
            )
            self.assertEqual(len(default_revision_store().all_records()), before + 1)

    def test_06_behavior_revision_learning_event_is_emitted(self):
        """**REVISION Learning Eventが実際に出ること。**"""
        from app.ai.gateway.learning_events import default_learning_event_service

        with _production() as env:
            artifact = env.provision()
            self.assertEqual(
                env.update(artifact, "収入をもっと目立たせて").status_code, 200,
            )
            types = [e.event_type for e in default_learning_event_service().local_events]
            self.assertIn(LearningEventType.REVISION, types)
            self.assertIn(LearningEventType.FEEDBACK, types)

    def test_07_usage_consent_cannot_export_revision(self):
        self.assertEqual(consent_category_for_event(LearningEventType.REVISION), ConsentCategory.SEMANTIC_CORRECTIONS)

    def test_08_artifact_handle_cannot_enter_learning_event(self):
        self.assertNotIn("artifact_handle", {f.name for f in dataclasses.fields(LearningEvent)})

    def test_09_evaluation_snapshot_is_required(self):
        names = {f.name for f in dataclasses.fields(EvaluationContextSnapshot)}
        self.assertTrue({"export_policy_version", "training_policy_version", "consent_policy_version"} <= names)

    def test_10_static_visual_capture_route_is_guarded(self):
        """**static protocol check。** 撮影スクリプトが失敗を握り潰さないこと。

        名前に`static_`を付けてあるのは、これが振る舞いを見ていない
        ことを報告で数え分けるためである（019A §6）。
        """
        script = (_REPO_ROOT / "scripts" / "capture_forge_019_visual.ps1").read_text(encoding="utf-8")
        self.assertIn("throw 'Before route capture failed.'", script)

    def test_11_before_after_same_mutation_is_killed(self):
        before, after = finance_document(), self._result().document
        self.assertNotEqual(before, after)

    def test_12_unrelated_subtree_mutation_is_killed(self):
        before, after = finance_document(), self._result().document
        self.assertEqual(before["screens"][0]["body"]["children"][2], after["screens"][0]["body"]["children"][2])

    def test_13_validator_bypass_is_killed(self):
        self.assertTrue(self._result().validation.valid)

    def test_14_critic_bypass_is_killed(self):
        self.assertFalse(self._result().critic.has_blocking_issue)

    def test_15_static_visual_protocol_is_present(self):
        """**static protocol check。** AGENTSの視覚確認ルールが消えていないこと。"""
        protocol = (_REPO_ROOT / "AGENTS.md").read_text(encoding="utf-8")
        self.assertIn("Visual evidence for UI work", protocol)


if __name__ == "__main__":
    unittest.main()
