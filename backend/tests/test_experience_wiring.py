"""Experienceが**本番の経路から実際に記録される**ことの回帰テスト
(FORGE-ROADMAP R0、2026-08-17)。

---

## このファイルが存在する理由

Forgeは同じ失敗を4回している。

    ModelGateway            (TD59)      — 作ったが本番から呼ばれない
    classify_correction     (007 §10)   — 作ったが本番から呼ばれない
    /generate・/update      (010 Phase B) — Routerを迂回していた
    ExperienceStore         (TD64)      — 作ったが本番から呼ばれない

Product Direction §7は、この3つ目の形を名指しで「完成扱いしては
ならない」と書いている。

    ExperienceStore はあるが **Production から記録されない**

Unit Testは、この失敗を1つも捕まえなかった。`ExperienceStore`の
テストは21件あって全部通っていたが、そのすべてがテスト自身で
`store.record(...)`を呼んでいた。**呼べば動く**ことしか確かめて
いなかったのである。

したがってここでは、`ExperienceStore`に一切触れずにHTTP APIを叩き、
**その結果として**記録が増えることだけを見る。Phase Bの
`test_router_anti_bypass.py`と同じ姿勢である。
"""

from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

os.environ.setdefault("FORGE_FEATURE_WORKSPACE", "true")
os.environ.setdefault("FORGE_FEATURE_FOLDER", "true")

from app.ai.gateway.ai_router import default_router  # noqa: E402
from app.ai.gateway.learning_foundation import (  # noqa: E402
    AcceptanceSignal,
    ExperienceRecord,
    default_experience_store,
)
from app.ai.gateway.tasks import ForgeTask  # noqa: E402
from app.ai.runtime.conversation_store import default_conversation_store  # noqa: E402

try:
    from fastapi.testclient import TestClient

    from app.main import app

    from tests.revision_fixtures import provision_artifact

    _FASTAPI_AVAILABLE = True
except ImportError:  # pragma: no cover — 環境依存
    _FASTAPI_AVAILABLE = False


_MINIMAL_DOCUMENT = {
    "forge_version": "1.0",
    "app": {"name": "メモ", "description": "テスト用"},
    "data": [
        {
            "name": "memo",
            "fields": [
                {"name": "title", "type": "text", "required": True},
            ],
        }
    ],
    "views": [
        {
            "name": "一覧",
            "type": "list",
            "data_source": "memo",
            "components": [{"type": "text", "value": "メモ"}],
        }
    ],
}


@unittest.skipUnless(_FASTAPI_AVAILABLE, "fastapi/pydanticが無い環境ではスキップする")
class TestProductionRequestsLeaveEvidence(unittest.TestCase):
    """**HTTP APIを叩くだけ**で記録が増えること。"""

    def setUp(self) -> None:
        self.client = TestClient(app)
        self.store = default_experience_store()
        self.store.reset()

    def test_the_shared_router_actually_has_somewhere_to_record(self) -> None:
        """配線の一番外側。ここが`None`だと、以下のテストは全部
        「記録が0件のまま通る」ようには**ならない**(下のテストが
        落ちる)が、原因がここだと分かりやすくしておく。"""
        self.assertIsNotNone(
            default_router().experience,
            "共有Routerに記録先が無い。ExperienceStoreは再び"
            "「実装はあるが本番から呼ばれない」状態に戻っている。",
        )

    def test_a_conversation_turn_is_recorded(self) -> None:
        before = len(self.store.all_records())
        response = self.client.post(
            "/api/v1/ai/converse",
            json={"message": "買い物で何を買うか忘れる", "provider": "mock"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertGreater(
            len(self.store.all_records()), before,
            "/converse を1往復してもExperienceが1件も増えていない。",
        )
        self.assertTrue(
            any(r.task is ForgeTask.CONVERSATION_STEP for r in self.store.all_records())
        )

    def test_a_generation_is_recorded_with_the_validator_outcome(self) -> None:
        """**Validatorの合否まで届いていること**が要点である。

        呼び出し時点の事実(Provider・latency)だけなら記録は簡単だが、
        それはLocal AIの学習素材としてはほぼ無価値である。
        Product Direction §5が挙げる「正しさの根拠」——Validator・
        Runtime・User ACCEPTED——が付いて初めて教師信号になる。
        """
        response = self.client.post(
            "/api/v1/ai/generate",
            json={
                "input": {
                    "natural_language": "買い物リストを作りたい",
                    "generation_options": {"provider": "mock"},
                }
            },
        )
        self.assertEqual(response.status_code, 200, response.text)
        judged = [r for r in self.store.all_records() if r.validator_passed is not None]
        self.assertTrue(
            judged,
            "生成が成功したのに、Validatorの合否が付いた記録が1件も無い。"
            "呼び出し時点の事実しか残っていない。",
        )
        self.assertTrue(all(r.validator_passed for r in judged))

    def test_an_update_is_recorded(self) -> None:
        """`/update`はCognitive Pipelineを通らない**独立経路**である。
        通らない経路は、放っておくと記録されない。"""
        artifact = provision_artifact(self.client)
        before = len(self.store.all_records())
        response = self.client.post(
            "/api/v1/ai/update",
            # FORGE-019A: 局所的な意味操作へ落とせない要求を選び、
            # 全体再生成fallback(AIを呼ぶ側)を踏ませる。局所patchはAIを
            # 呼ばないので、そちらではExperienceは増えない——それが正しい。
            json=artifact.update_payload("在庫管理の機能も足したい", provider="mock"),
        )
        self.assertIn(response.status_code, (200, 422), response.text)
        after = self.store.all_records()
        self.assertGreater(len(after), before, "/update がExperienceを1件も残していない。")
        updates = [r for r in after if r.task is ForgeTask.FORGE_LANGUAGE_UPDATE]
        self.assertTrue(
            updates,
            "UPDATEが会話ステップと同じTaskとして記録されている"
            "(Taskが混ざると、後でTask別に学習できない)。",
        )
        # **成否まで残っていること。** Routerが自動で残すのは呼び出し
        # 時点の事実だけであり、「その更新がValidatorを通ったか」は
        # `/update`が明示的に書き足さないと永久に`None`のままになる。
        self.assertTrue(
            any(r.validator_passed is not None for r in updates),
            "UPDATEの成否がExperienceへ書き足されていない"
            "(Provider名とlatencyだけでは教師信号にならない)。",
        )

    def test_the_session_keeps_the_refs_so_the_next_turn_can_judge_them(self) -> None:
        """**評価を書き足せる状態で次ターンを迎えていること。**

        記録が増えるだけなら、`AIRouter`の自動記録で満たせてしまう。
        しかし利用者の「それでいい」/「違う」は次ターンにしか来ない
        ので、`/converse`が今ターンの番号をセッションへ預けていないと、
        **一番価値のある信号だけが永久に付かない**。

        これは`/converse`側の1行が消えても他のテストが誰も落ちない
        場所なので、ここで名指しで見る。
        """
        # BUILDまで進むとセッションは破棄されるので、会話が続く
        # (=次ターンがある)応答になる入力を選ぶ。
        response = self.client.post(
            "/api/v1/ai/converse",
            json={"message": "予約を送りたい", "provider": "mock"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn(
            response.json().get("status"), ("ask", "confirm"),
            "この入力が会話継続にならなくなった。テストの前提を見直すこと。",
        )
        session_id = response.json().get("session_id")
        self.assertTrue(session_id)
        session = default_conversation_store.get(session_id)
        self.assertTrue(
            session.pending_experience_refs,
            "/converse が今ターンのExperience番号をセッションへ預けていない。"
            "次ターンで「それでいい」と言われても、書き足す先が分からない。",
        )

    def test_every_implemented_adapter_names_its_model(self) -> None:
        """**実機で見つけた実バグの回帰テスト**(2026-08-17)。

        R0の配線を実Providerで確認したところ、Geminiの記録が
        `{"provider": "gemini", "model": ""}`になっていた。
        `GeminiProvider`だけがModel名をprivate属性(`_model`)にしていて、
        Routerから読めなかったためである。

        Providerだけ分かってModelが分からない記録は、Model入れ替えの
        前後を区別できない。「gemini-flash-latestは構造化出力が
        安定していた」と言えなくなり、後から学習素材として使えない。

        対象は**この環境で実際に呼べるProvider**に限る。未設定の汎用
        Cloud枠(`FORGE_<ID>_MODEL`が空)はModel名を持たないのが正しい
        ——呼べないものが名乗らないのは矛盾ではない。
        """
        from app.ai.gateway.provider_registry import configured_providers  # noqa: PLC0415
        from app.ai.runtime.provider_router import ProviderRouter  # noqa: PLC0415

        router = ProviderRouter()
        callable_ids = [d.provider_id for d in configured_providers()]
        callable_ids.append("mock")  # 常に呼べる
        self.assertTrue(callable_ids)
        for name in callable_ids:
            with self.subTest(provider=name):
                adapter = router.resolve(name)
                self.assertTrue(
                    str(getattr(adapter, "model", "") or "").strip(),
                    f"Provider '{name}' のAdapterがModel名を名乗っていない。"
                    "Experienceに空文字で記録される。",
                )

    def test_nothing_recorded_can_carry_what_the_user_said(self) -> None:
        """本番経路を通した**実物の記録**で確かめる。

        型で塞いであることは`test_learning_foundation.py`が見ている。
        ここで見るのは「実際に流れてきたものに本文が混ざっていない」
        ことである(006 §22)。
        """
        message = "むにゃむにゃ特有の言い回しXYZZY"
        self.client.post("/api/v1/ai/converse", json={"message": message, "provider": "mock"})
        dumped = repr([r.to_dict() for r in self.store.all_records()])
        self.assertNotIn("XYZZY", dumped)
        self.assertNotIn("むにゃむにゃ", dumped)


@unittest.skipUnless(_FASTAPI_AVAILABLE, "fastapi/pydanticが無い環境ではスキップする")
class TestTheUserReactionReachesThePreviousTurn(unittest.TestCase):
    """011 §5の分離が、**本番の会話で実際に付く**こと。

    「明示的な承認」と「ただ訂正されなかった」を型の上で分けても、
    本番から`ACCEPTED`が一度も書かれないなら、記録は永遠に
    `UNKNOWN`だけで埋まる。分けた意味が無い。
    """

    def setUp(self) -> None:
        self.store = default_experience_store()
        self.store.reset()

    def _session_with_a_recorded_turn(self) -> tuple[str, tuple[int, ...]]:
        """AI呼び出し1回分の記録を持つセッションを作る。

        `ConversationEngine`の判定を経由せず、Storeの契約だけで
        組み立てる——ここで見たいのは「Engineがacceptを出せるか」
        ではなく「acceptが出たとき、それが前ターンの記録へ届くか」
        である(前者は`test_conversation_engine.py`の担当)。
        """
        session = default_conversation_store.create()
        record = self.store.record(
            ExperienceRecord(
                task=ForgeTask.CONVERSATION_STEP, provider="mock", model="mock-1",
                structured_output_valid=True,
            )
        )
        default_conversation_store.record_hypothesis_event(
            session.session_id, event=None, hypothesis=None, correction_target=None,
            experience_refs=(record.ref,), experience_store=self.store,
        )
        return session.session_id, (record.ref,)

    def test_an_explicit_accept_marks_the_previous_turn(self) -> None:
        session_id, refs = self._session_with_a_recorded_turn()
        default_conversation_store.record_hypothesis_event(
            session_id, event="accept", hypothesis=None, correction_target=None,
            experience_refs=(), experience_store=self.store,
        )
        marked = [r for r in self.store.all_records() if r.ref in refs]
        self.assertEqual(marked[0].acceptance, AcceptanceSignal.ACCEPTED)
        self.assertTrue(marked[0].acceptance.is_positive)

    def test_a_correction_marks_the_previous_turn_as_a_negative(self) -> None:
        session_id, refs = self._session_with_a_recorded_turn()
        default_conversation_store.record_hypothesis_event(
            session_id, event="clarify", hypothesis=None, correction_target="data",
            experience_refs=(), experience_store=self.store,
        )
        marked = [r for r in self.store.all_records() if r.ref in refs]
        self.assertEqual(marked[0].acceptance, AcceptanceSignal.CORRECTED)
        self.assertFalse(marked[0].acceptance.is_positive)

    def test_an_ordinary_turn_leaves_the_signal_unknown(self) -> None:
        """**沈黙を承認に格上げしない**(011 §5)。

        仮説に触れないターンが挟まっても、前ターンは`UNKNOWN`のまま
        である。
        """
        session_id, refs = self._session_with_a_recorded_turn()
        default_conversation_store.record_hypothesis_event(
            session_id, event=None, hypothesis=None, correction_target=None,
            experience_refs=(), experience_store=self.store,
        )
        marked = [r for r in self.store.all_records() if r.ref in refs]
        self.assertEqual(marked[0].acceptance, AcceptanceSignal.UNKNOWN)
        self.assertFalse(marked[0].acceptance.is_usable_as_supervision)

    def test_the_reaction_does_not_leak_onto_an_older_turn(self) -> None:
        """3ターン前の応答に、今の「それでいい」が付かないこと。

        `pending_experience_refs`を溜めていくと起きる誤りである。
        評価は**直前の1ターンにだけ**付く。
        """
        session_id, first_refs = self._session_with_a_recorded_turn()
        second = self.store.record(
            ExperienceRecord(
                task=ForgeTask.CONVERSATION_STEP, provider="mock", model="mock-1",
                structured_output_valid=True,
            )
        )
        default_conversation_store.record_hypothesis_event(
            session_id, event=None, hypothesis=None, correction_target=None,
            experience_refs=(second.ref,), experience_store=self.store,
        )
        default_conversation_store.record_hypothesis_event(
            session_id, event="accept", hypothesis=None, correction_target=None,
            experience_refs=(), experience_store=self.store,
        )
        by_ref = {r.ref: r for r in self.store.all_records()}
        self.assertEqual(by_ref[second.ref].acceptance, AcceptanceSignal.ACCEPTED)
        self.assertEqual(
            by_ref[first_refs[0]].acceptance, AcceptanceSignal.UNKNOWN,
            "1ターン前ではなく2ターン前の応答にまで評価が付いている。",
        )


if __name__ == "__main__":
    unittest.main()
