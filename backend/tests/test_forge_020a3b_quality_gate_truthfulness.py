"""Quality Gate は **Need の種類で見るものを変える**（020A3B §2）。

---

## 1つの物差しで測れない

Quality Gate v2 は「生成物の品質」を測る。ところが

> 「植物を育てながら音を組み合わせるゲームを作りたい」

には、**そもそも Forge が持っていない能力**（`simulate.loop` /
`effect.media_compose`）が要る。この Need に対して
「良い CRUD が出来たか」を測るのは、測る対象を間違えている。

かといって**作れないものを作れた顔で返すのは禁止**である
（`GENERATIVE-SOFTWARE-DIRECTION.md`）。

## だから2つに分ける

| Need | 見るもの |
|---|---|
| build 可能 | 生成された文書の品質 |
| critical missing を含む | **完成品を偽って返していないか** |

後者で見るのは3つ。

1. `release_ready` が **false** である（「仕上がっている」と言わない）
2. 欠けている capability の **id** が出ている
3. 利用者向けの**言葉**で説明が出ている（内部 ID を出さない）

## Need ごとの特別扱いはしない

ゲーム専用の response 型も、Need 名での分岐も作らない。
振り分けは **`capability_gap.blocks_completion`**——
`CapabilityPlan` から機械的に決まる1つの述語だけを見る。
"""

from __future__ import annotations

import pathlib
import sys
import unittest

_ROOT = pathlib.Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
_BACKEND = _ROOT / "backend"
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402

#: Quality Gate v2 の8つ（`scripts/export_quality_gate_fixtures.py` と同じ）。
QUALITY_GATE_NEEDS: tuple[str, ...] = (
    "毎日の収入と支出を記録して残高を見たい",
    "今日やる作業を登録して、終わったものを消していきたい",
    "子どもが朝の支度をひとつずつチェックできるようにしたい",
    "旅行の写真を日付ごとに残してメモを付けたい",
    "釣った場所を地図に残して魚の種類を記録したい",
    "植物を育てながら音を組み合わせるゲームを作りたい",
    "部署ごとの売上を月別に集計してグラフで比べたい",
    "英単語を出題して、正解率の推移を見たい",
)


def _result(need: str) -> dict:
    client = TestClient(app)
    response = client.post(
        "/api/v1/ai/generate",
        json={"input": {"natural_language": need,
                        "generation_options": {"provider": "mock"}}},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body.get("status") == "success", body
    return body["result"]


def _blocks_completion(result: dict) -> bool:
    gap = result.get("capability_gap") or {}
    return bool(gap.get("blocks_completion"))


class TestTheGateSplitsByOutcomeNotByNeed(unittest.TestCase):
    """振り分けが**1つの述語**で決まること。"""

    def test_the_split_comes_from_the_capability_plan(self) -> None:
        blocked = [n for n in QUALITY_GATE_NEEDS if _blocks_completion(_result(n))]
        buildable = [n for n in QUALITY_GATE_NEEDS if n not in blocked]

        # **両方が空でないこと。** 片方が空なら分けた意味がない。
        self.assertTrue(buildable, "build 可能な Need が1つも無い")
        self.assertTrue(blocked, "critical missing の Need が1つも無い")

        # ゲームは critical missing 側である（`simulate.loop` が要る）。
        self.assertIn("植物を育てながら音を組み合わせるゲームを作りたい", blocked)

    def test_no_need_specific_branch_exists_in_production(self) -> None:
        """**Need 名で分岐していない**ことを静的に見る。

        「ゲームならこう返す」を書いた瞬間、有限 Widget Builder へ戻る。
        """
        production = (
            _ROOT / "backend" / "app" / "ai" / "runtime" / "prompt_pipeline.py"
        ).read_text(encoding="utf-8")
        for word in ("植物", "ゲーム", "game_response", "GameResult"):
            with self.subTest(word=word):
                self.assertNotIn(word, production)


class TestBuildableNeedsAreJudgedOnTheDocument(unittest.TestCase):
    def test_they_produce_a_document_and_claim_completion(self) -> None:
        for need in QUALITY_GATE_NEEDS:
            result = _result(need)
            if _blocks_completion(result):
                continue
            with self.subTest(need=need):
                self.assertTrue(result["forge_document"].get("screens"))
                self.assertTrue(result["validation"]["valid"])


class TestCriticalMissingNeedsAreJudgedOnTruthfulness(unittest.TestCase):
    """**完成品を偽って返していないか。**"""

    def setUp(self) -> None:
        self.results = {
            need: result for need in QUALITY_GATE_NEEDS
            if _blocks_completion(result := _result(need))
        }

    def test_none_of_them_is_reported_as_release_ready(self) -> None:
        """**しかも、落ちている理由が capability gap であること。**

        `release_ready` は Design Critic の点数でも落ちる。「false だった」
        だけを見ると、gap → release_ready の配線を外しても通ってしまう
        （実際に配線破壊試験で通ってしまい、書き直した）。
        **理由まで見る。**
        """
        for need, result in self.results.items():
            with self.subTest(need=need):
                self.assertFalse(
                    result["quality"]["release_ready"],
                    "本質が欠けているのに『仕上がっている』と言っている",
                )
                message = result["capability_gap"]["message"]
                self.assertIn(
                    message, result["quality"]["required_fixes"],
                    "『仕上がっていない』理由に、作れなかったことが入っていない",
                )

    def test_each_one_names_the_missing_capability_ids(self) -> None:
        for need, result in self.results.items():
            gap = result["capability_gap"]
            with self.subTest(need=need):
                self.assertTrue(gap["critical"], "critical が空のまま止めている")
                for capability_id in gap["critical"]:
                    self.assertIn(capability_id, gap["missing"])

    def test_each_one_explains_itself_in_words(self) -> None:
        for need, result in self.results.items():
            gap = result["capability_gap"]
            with self.subTest(need=need):
                self.assertTrue(gap["message"].strip())
                # **内部 ID を利用者向けの文へ出さない。**
                for capability_id in gap["missing"]:
                    self.assertNotIn(capability_id, gap["message"])

    def test_the_explanation_also_says_what_can_be_built(self) -> None:
        """作れない話で終わらせない。**出来る範囲を渡す。**"""
        for need, result in self.results.items():
            with self.subTest(need=need):
                self.assertIn("作れます", result["capability_gap"]["message"])
                self.assertTrue(
                    result["forge_document"].get("screens"),
                    "作れる範囲さえ利用者へ渡していない",
                )

    def test_the_required_fixes_carry_the_reason(self) -> None:
        for need, result in self.results.items():
            with self.subTest(need=need):
                self.assertTrue(result["quality"]["required_fixes"])


if __name__ == "__main__":
    unittest.main()
