"""Quality Gate truthfulness regression tests (020A3B §2).

Golden examples are allowed to become buildable as Forge gains real capabilities.
Truthfulness is tested against an explicit request that still requires a genuinely
missing capability, rather than preserving historical failures as permanent fixtures.
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

UNSUPPORTED_AUTHORING_NEED = "植物を育てながら新しい音を合成して書き出すゲームを作りたい"


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
    def test_golden_examples_may_advance_without_freezing_old_gaps(self) -> None:
        results = {need: _result(need) for need in QUALITY_GATE_NEEDS}
        self.assertTrue(results)
        # The interactive game fixture is now supported by real simulation + audio
        # mixing. It must not be forced back to FAIL just to keep this regression red.
        game = results["植物を育てながら音を組み合わせるゲームを作りたい"]
        self.assertFalse(_blocks_completion(game))

    def test_a_real_missing_authoring_capability_still_blocks_completion(self) -> None:
        result = _result(UNSUPPORTED_AUTHORING_NEED)
        self.assertTrue(_blocks_completion(result))
        gap = result["capability_gap"]
        self.assertIn("effect.media_compose", gap["missing"])
        self.assertIn("effect.media_compose", gap["critical"])

    def test_no_need_specific_branch_exists_in_production(self) -> None:
        production = (
            _ROOT / "backend" / "app" / "ai" / "runtime" / "prompt_pipeline.py"
        ).read_text(encoding="utf-8")
        for word in ("植物", "ゲーム", "game_response", "GameResult"):
            with self.subTest(word=word):
                self.assertNotIn(word, production)


class TestBuildableNeedsAreJudgedOnTheDocument(unittest.TestCase):
    def test_they_produce_a_valid_document(self) -> None:
        for need in QUALITY_GATE_NEEDS:
            result = _result(need)
            if _blocks_completion(result):
                continue
            with self.subTest(need=need):
                self.assertTrue(result["forge_document"].get("screens"))
                self.assertTrue(result["validation"]["valid"])


class TestCriticalMissingNeedsAreJudgedOnTruthfulness(unittest.TestCase):
    def setUp(self) -> None:
        result = _result(UNSUPPORTED_AUTHORING_NEED)
        self.assertTrue(_blocks_completion(result))
        self.result = result

    def test_not_reported_as_release_ready(self) -> None:
        self.assertFalse(self.result["quality"]["release_ready"])
        message = self.result["capability_gap"]["message"]
        self.assertIn(message, self.result["quality"]["required_fixes"])

    def test_names_the_missing_capability_ids(self) -> None:
        gap = self.result["capability_gap"]
        self.assertTrue(gap["critical"])
        for capability_id in gap["critical"]:
            self.assertIn(capability_id, gap["missing"])

    def test_explains_itself_in_words_not_internal_ids(self) -> None:
        gap = self.result["capability_gap"]
        self.assertTrue(gap["message"].strip())
        for capability_id in gap["missing"]:
            self.assertNotIn(capability_id, gap["message"])

    def test_explanation_also_says_what_can_be_built(self) -> None:
        self.assertIn("作れます", self.result["capability_gap"]["message"])
        self.assertTrue(self.result["forge_document"].get("screens"))

    def test_required_fixes_carry_the_reason(self) -> None:
        self.assertTrue(self.result["quality"]["required_fixes"])


if __name__ == "__main__":
    unittest.main()
