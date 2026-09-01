"""**どの段が何ミリ秒かを、本番の応答で返すこと**（2026-09-01）。

---

実機で `/converse` が 73.54 秒かかったとき、**内訳が分からなかった。**
合計しか無いと「1つ速くしたから全部速い」と丸めてしまう。

会話の判定を速い道へ逃がして、その判定は 0.09 ミリ秒になった。
**しかしそれは判定だけの数字である。** そのあと `PromptPipeline` が
実際に画面を作る。そこが何秒かは段を分けなければ分からない。

ここが守るのは「段ごとの数字が本番の応答に載ること」である。
載らなくなれば、実機で測ったときに**また内訳が分からなくなる**。
"""

from __future__ import annotations

import pathlib
import sys
import unittest

_ROOT = pathlib.Path(__file__).resolve().parents[2]
for path in (str(_ROOT), str(_ROOT / "backend")):
    if path not in sys.path:
        sys.path.insert(0, path)

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402

#: 実機で 73.54 秒かかり、しかも記録項目を聞き返した文。
REAL_DEVICE_CASE = "事務所の鍵を誰が持ち出していて、いつ返す予定なのか記録できるようにしたい"


class TestTheResponseCarriesStageTimings(unittest.TestCase):
    """**測れないものは直せない。**"""

    def setUp(self) -> None:
        self.client = TestClient(app)

    def _converse(self, message: str) -> dict:
        response = self.client.post(
            "/api/v1/ai/converse", json={"message": message, "provider": "mock"},
        )
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def test_the_real_device_case_builds_without_asking(self) -> None:
        """記録項目を「聞くべき未知」として聞き返さないこと。"""
        body = self._converse(REAL_DEVICE_CASE)
        self.assertEqual(
            body["status"], "build",
            f"聞き返している: {body.get('question')!r}",
        )

    def test_the_stages_are_reported_separately(self) -> None:
        """**合計だけを返さない。** 段が分かれていること。"""
        timings = self._converse(REAL_DEVICE_CASE).get("timings")
        self.assertIsNotNone(timings, "段ごとの実測が応答に載っていない")
        stages = timings["stages_ms"]
        for name in ("fast_path", "conversation_step", "build_pipeline", "validator"):
            with self.subTest(stage=name):
                self.assertIn(name, stages, f"{name} の実測が無い")
                self.assertGreaterEqual(stages[name], 0.0)

    def test_it_reports_that_the_llm_was_not_called(self) -> None:
        """**0 回であることを、0 として読めること。**"""
        timings = self._converse(REAL_DEVICE_CASE)["timings"]
        self.assertEqual(timings["counters"].get("conversation_llm_calls", 0), 0)
        self.assertEqual(timings["notes"].get("fast_path_taken"), "yes")

    def test_a_slow_path_request_reports_the_llm_call(self) -> None:
        """速い道を通らなかったときは、LLM を呼んだことが数字に出ること。"""
        timings = self._converse("なんとかしてほしいんだけど")["timings"]
        self.assertEqual(timings["notes"].get("fast_path_taken"), "no")
        self.assertGreaterEqual(timings["counters"].get("conversation_llm_calls", 0), 1)
        self.assertIn("conversation_llm", timings["stages_ms"])

    def test_the_build_actually_returns_a_document(self) -> None:
        """BUILD と言うなら、Forge Document が返っていること。"""
        body = self._converse(REAL_DEVICE_CASE)
        document = body["result"]["forge_document"]
        self.assertTrue(document.get("screens"), "画面が1つも無い")
        self.assertTrue(body["result"]["validation"]["valid"], "Validator を通っていない")


if __name__ == "__main__":
    unittest.main()
