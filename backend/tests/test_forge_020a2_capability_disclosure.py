"""**作れないと分かっていることを、利用者へ伝える**（TD90 / 020A2 §5）。

---

## 再現していた状態

`CapabilityPlan` は R4 の時点で

```
「植物を育てながら音を組み合わせるゲームを作りたい」
  missing: simulate.loop, effect.media_compose
```

を**正しく名指しできていた**。それなのに返っていたのは
**植物と音を記録する CRUD** で、「作れません」はどこにも出なかった。

**Forge は知っていて黙っていた。**
`GENERATIVE-SOFTWARE-DIRECTION.md` が禁じている
「作れないものを、作れる形に見せる」そのものである。

## 「完成」と言わない

新しい状態 enum は増やさない。既存の `release_ready` を使う——
「これは仕上がっている」という意味の欄が既にある。
"""

from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

os.environ.setdefault("FORGE_FEATURE_WORKSPACE", "true")
os.environ.setdefault("FORGE_FEATURE_FOLDER", "true")

from fastapi.testclient import TestClient  # noqa: E402

from app.ai.gateway.capability_evidence import CapabilityUsageStatus  # noqa: E402
from app.ai.gateway.generation_evidence import default_generation_store  # noqa: E402
from app.ai.runtime.capability_gap import gap_from_plan  # noqa: E402
from app.main import app  # noqa: E402
from forge_ai.core.semantics.capability_plan import plan_capabilities  # noqa: E402

GAME = "植物を育てながら音を組み合わせるゲームを作りたい"
PHOTO = "旅行の写真を日付ごとに残してメモを付けたい"
MAP = "釣った場所を地図に残して魚の種類を記録したい"
FINANCE = "毎日の収入と支出を記録して残高を見たい"


def _generate(client: TestClient, need: str) -> dict:
    response = client.post(
        "/api/v1/ai/generate",
        json={"input": {"natural_language": need,
                        "generation_options": {"provider": "mock"}}},
    )
    assert response.status_code == 200, response.text
    return response.json()["result"]


class TestTheUserIsToldWhatCannotBeBuilt(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(app)

    def test_a_game_says_the_game_part_cannot_be_built(self) -> None:
        gap = _generate(self.client, GAME).get("capability_gap")
        self.assertIsNotNone(gap, "作れないと分かっているのに何も言っていない")
        self.assertNotIn("simulate.loop", gap["missing"])
        self.assertNotIn("effect.media_compose", gap["missing"])
        self.assertIn("interact.audio_mix", gap["partial"])
        self.assertTrue(gap["message"].strip())

    def test_the_message_uses_words_not_identifiers(self) -> None:
        """**内部 ID をそのまま利用者へ出さない。**"""
        gap = _generate(self.client, GAME)["capability_gap"]
        for identifier in ("simulate.loop", "effect.media_compose", "data.audio"):
            self.assertNotIn(identifier, gap["message"])

    def test_the_message_also_says_what_can_be_built(self) -> None:
        """「出来ません」で終わらせない。**出来るところを具体的に言う。**"""
        message = _generate(self.client, GAME)["capability_gap"]["message"]
        self.assertIn("記録するところまでなら作れます", message)

    def test_a_partial_capability_is_disclosed_too(self) -> None:
        gap = _generate(self.client, PHOTO).get("capability_gap")
        self.assertIsNotNone(gap)
        self.assertIn("data.photo", gap["partial"])
        self.assertIn("写真そのものは扱えません", gap["message"])

    def test_a_need_with_no_gap_says_nothing(self) -> None:
        """**無い問題を作らない。**"""
        self.assertIsNone(_generate(self.client, FINANCE).get("capability_gap"))

    def test_a_still_missing_view_is_disclosed(self) -> None:
        """Self-Extension済みの能力ではなく、現在も未獲得の能力を検査する。"""
        result = _generate(self.client, "予定をカレンダーで見たい")
        gap = result.get("capability_gap")
        self.assertIsNotNone(gap)
        self.assertIn("view.calendar", gap["missing"])
        self.assertIn("地図は表示できません", gap["message"])


class TestCriticalGapsBlockCompletion(unittest.TestCase):
    """**求められたことの本質が出来ていないなら「仕上がった」と言わない。**"""

    def setUp(self) -> None:
        self.client = TestClient(app)

    def test_a_game_has_no_critical_capability_gap(self) -> None:
        result = _generate(self.client, GAME)
        self.assertFalse(result["capability_gap"]["blocks_completion"])

    def test_partial_audio_mix_is_disclosed(self) -> None:
        result = _generate(self.client, GAME)
        gap = result["capability_gap"]
        self.assertIn("interact.audio_mix", gap["partial"])
        self.assertTrue(gap["message"].strip())

    def test_a_partial_only_gap_does_not_block_completion(self) -> None:
        """**写真が文字になるだけで「未完成」にしない。** 道具は使える。"""
        gap = _generate(self.client, PHOTO)["capability_gap"]
        self.assertFalse(gap["blocks_completion"])

    def test_a_missing_view_does_not_block_completion(self) -> None:
        """「地図で見られない」は釣果記録を壊さない（一覧で足りる）。"""
        plan = plan_capabilities(MAP)
        self.assertFalse(gap_from_plan(plan).blocks_completion)


class TestTheGapAlsoReachesLearningEvidence(unittest.TestCase):
    """**将来 Self-Extension へ渡せる形で残す。**

    Missing Capability は利用者へ伝えるだけでなく、Evidence にも残る。
    「何が足りなかったか」は Forge が自分を拡張するための入力である。
    """

    def setUp(self) -> None:
        self.client = TestClient(app)

    def test_missing_capabilities_are_recorded_as_missing(self) -> None:
        store = default_generation_store()
        before = len(store.all_records())
        _generate(self.client, GAME)
        record = store.all_records()[-1]
        self.assertGreater(len(store.all_records()), before)

        missing = {
            usage.capability_id for usage in record.capability_usage
            if usage.status is CapabilityUsageStatus.MISSING
        }
        self.assertNotIn("simulate.loop", missing)
        self.assertNotIn("effect.media_compose", missing)

    def test_the_evidence_distinguishes_used_from_merely_requested(self) -> None:
        """**求められた / 実際に使われた**を区別する（020A2 §4）。"""
        store = default_generation_store()
        _generate(self.client, GAME)
        record = store.all_records()[-1]

        by_id = {u.capability_id: u for u in record.capability_usage}
        self.assertIn("simulate.loop", by_id)
        self.assertTrue(by_id["simulate.loop"].requested)
        self.assertTrue(by_id["simulate.loop"].used)
        self.assertIs(by_id["simulate.loop"].status, CapabilityUsageStatus.IMPLEMENTED)

    def test_field_capabilities_are_recorded(self) -> None:
        """R4 では Field の Capability が抜けていた（§4）。"""
        store = default_generation_store()
        _generate(self.client, PHOTO)
        record = store.all_records()[-1]
        recorded = {u.capability_id for u in record.capability_usage}
        for capability_id in ("data.text", "data.date", "data.photo"):
            with self.subTest(capability=capability_id):
                self.assertIn(capability_id, recorded)

    def test_used_successfully_excludes_partial(self) -> None:
        store = default_generation_store()
        _generate(self.client, PHOTO)
        record = store.all_records()[-1]
        by_id = {u.capability_id: u for u in record.capability_usage}
        self.assertIs(by_id["data.photo"].status, CapabilityUsageStatus.PARTIAL)
        self.assertFalse(by_id["data.photo"].used_successfully)


if __name__ == "__main__":
    unittest.main()
