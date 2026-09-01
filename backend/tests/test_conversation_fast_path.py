"""**簡単な要求に、毎回 LLM を待たせない**（実機 2026-08-31 の速度 FAIL）。

---

実機で測った事実:

| | |
|---|---|
| Local Model 接続 | PASS |
| HTTP 200 / `simulated=false` | PASS |
| 応答時間 | **73.54 秒（FAIL）** |
| 意味判断 | **FAIL**（記録項目を「聞くべき未知」と誤判定） |
| Chrome 完走 | **FAIL**（Dio の `receiveTimeout` は 10 秒） |

ここで確かめるのは次の3つである。

1. 既存の能力だけで作れる要求で、**LLM を1回も呼ばない**
2. 本当に曖昧な要求では**ちゃんと LLM へ渡す**（速さのために雑にしない）
3. 記録項目を「聞くべき未知」と混同しない
"""

from __future__ import annotations

import pathlib
import random
import sys
import time
import unittest
from dataclasses import replace

_ROOT = pathlib.Path(__file__).resolve().parents[2]
for path in (str(_ROOT), str(_ROOT / "backend")):
    if path not in sys.path:
        sys.path.insert(0, path)

from app.ai.runtime.conversation_engine import ConversationEngine  # noqa: E402
from app.ai.runtime.conversation_fast_path import (  # noqa: E402
    deterministic_step,
)
from app.ai.runtime.conversation_types import (  # noqa: E402
    ConversationAction,
    ConversationSession,
    ConversationTurn,
)
from forge_ai.testing.free_text_requests import (  # noqa: E402
    RequestShape,
    generate_request,
)

#: 実機で 73.54 秒かかり、しかも誤って聞き返した文そのもの。
REAL_DEVICE_FAILURE = "事務所の鍵を誰が持ち出していて、いつ返す予定か記録したい"


def session_of(*texts: str, asked: tuple[str, ...] = ()) -> ConversationSession:
    turns = tuple(ConversationTurn(role="user", text=t) for t in texts)
    session = ConversationSession(session_id="s")
    return replace(session, turns=turns, asked_question_keys=asked)


class _CountingProvider:
    """**呼ばれたら数える。** 呼ばれないことを証明するために要る。"""

    def __init__(self) -> None:
        self.calls = 0

    def complete_structured(self, prompt, schema):  # noqa: ANN001, ANN202
        self.calls += 1
        return {
            "problem": "", "known": [], "unknowns": [], "assumptions": [],
            "confidence": 0.9, "next_action": "build", "build_brief": "作る",
        }

    def complete(self, prompt):  # noqa: ANN001, ANN202
        self.calls += 1
        raise AssertionError("complete() は使わない")


class TestTheRealDeviceFailureIsFixed(unittest.TestCase):
    """**実機で落ちた文そのもの**で確かめる。"""

    def test_it_no_longer_asks_about_tool_fields(self) -> None:
        """「誰が」「いつ返す」は**作る道具の入力欄**であって未知ではない。"""
        provider = _CountingProvider()
        engine = ConversationEngine(provider)
        result = engine.step(session_of(REAL_DEVICE_FAILURE))

        self.assertIs(result.action, ConversationAction.BUILD,
                      f"聞き返している: {result.question!r}")
        self.assertEqual(
            provider.calls, 0,
            "簡単な要求なのに大きな LLM 判定を通している（実機 73.54 秒の原因）",
        )
        self.assertEqual(engine.last_llm_calls, 0)

    def test_it_records_why_it_did_not_ask(self) -> None:
        """**判断の根拠を残す。** 黙って作らない。"""
        result = deterministic_step(session_of(REAL_DEVICE_FAILURE)).result
        assert result is not None
        keys = {a.key for a in result.need_model.assumptions}
        self.assertIn("tool_fields_are_not_unknowns", keys)

    def test_it_is_fast(self) -> None:
        """実機の 73.54 秒に対して、ここは**ミリ秒**で決まる。"""
        deterministic_step(session_of(REAL_DEVICE_FAILURE))  # import を温める
        started = time.perf_counter()
        deterministic_step(session_of(REAL_DEVICE_FAILURE))
        elapsed_ms = (time.perf_counter() - started) * 1000.0
        self.assertLess(elapsed_ms, 100.0, f"速い道が遅い: {elapsed_ms:.2f} ms")


class TestAmbiguousRequestsStillReachTheLLM(unittest.TestCase):
    """**速さのために雑に分類しない。** 迷ったら LLM へ渡す。"""

    def _falls_through(self, text: str, *, contains: str = "") -> None:
        outcome = deterministic_step(session_of(text))
        self.assertFalse(
            outcome.taken, f"速い道へ倒してはいけない要求を通した: {text!r}",
        )
        if contains:
            self.assertIn(contains, outcome.reason)

    def test_a_vague_request_is_not_rushed(self) -> None:
        self._falls_through("なんとかしてほしいんだけど")
        self._falls_through("いい感じのやつ作って")

    def test_an_unnamed_subject_is_asked_about(self) -> None:
        """**何を**扱うのかが無い。共有の話とは別に、これ単独で落とす。

        「家族で何か管理したい」だと共有の規則でも落ちてしまい、
        こちらの規則を検査したことにならない（配線破壊試験で発覚）。
        """
        self._falls_through("いろいろ記録して一覧で見返したい", contains="名指し")
        self._falls_through("何か記録して残しておきたい", contains="名指し")

    def test_shared_usage_is_asked_about(self) -> None:
        """誰が追加できるかで保存場所と権限が変わる。"""
        self._falls_through("家族で予定を管理したい", contains="複数人")

    def test_an_external_effect_is_not_rushed(self) -> None:
        self._falls_through("お客さんにメールを一斉送信したい", contains="外部作用")

    def test_a_destructive_request_is_not_rushed(self) -> None:
        self._falls_through("古いデータを全部削除したい", contains="外部作用")

    def test_a_modification_without_a_tool_is_not_rushed(self) -> None:
        self._falls_through("期限も追加して", contains="変更")

    def test_a_missing_capability_goes_to_the_slow_path(self) -> None:
        """足りない能力があるなら、自己拡張の判断が要る。"""
        self._falls_through(
            "通院の記録を残して、日付をカレンダーで確認したい",
            contains="足りない能力がある",
        )

    def test_the_second_turn_is_not_rushed(self) -> None:
        """会話が始まっていれば文脈を読む必要がある。"""
        self._falls_through_session(session_of("在庫を記録したい", "うん"))
        self._falls_through_session(
            session_of("在庫を記録したい", asked=("what_to_track",)),
        )

    def _falls_through_session(self, session: ConversationSession) -> None:
        self.assertFalse(deterministic_step(session).taken)

    def test_an_existing_tool_is_not_rushed(self) -> None:
        outcome = deterministic_step(
            session_of("在庫を記録したい"), has_existing_tool=True,
        )
        self.assertFalse(outcome.taken)


class TestRandomFreeTextTakesTheFastPath(unittest.TestCase):
    """**固定文で測らない。** ランダムな自由文で、生成 0 / LLM 0 を確かめる。"""

    def test_existing_only_requests_never_call_the_llm(self) -> None:
        seed = random.SystemRandom().randrange(1, 10**9)
        taken = 0
        checked = 0
        for attempt in range(40):
            request = generate_request(seed + attempt, RequestShape.EXISTING_ONLY)
            provider = _CountingProvider()
            engine = ConversationEngine(provider)
            result = engine.step(session_of(request.text))
            checked += 1
            if engine.last_fast_path_reason and result.action is ConversationAction.BUILD \
                    and provider.calls == 0:
                taken += 1
            else:
                # 速い道を通らなかった場合、**LLM を通ったこと自体は正しい**。
                # ここで測るのは「通ったときに本当に 0 回か」である。
                self.assertGreaterEqual(provider.calls, 0)
        self.assertGreater(
            taken, checked * 0.5,
            f"seed={seed}: 既存能力だけの自由文の過半で速い道を通れていない "
            f"({taken}/{checked})",
        )

    def test_a_fast_path_request_reaches_build_without_the_llm(self) -> None:
        seed = random.SystemRandom().randrange(1, 10**9)
        for attempt in range(40):
            request = generate_request(seed + attempt, RequestShape.EXISTING_ONLY)
            outcome = deterministic_step(session_of(request.text))
            if not outcome.taken:
                continue
            provider = _CountingProvider()
            engine = ConversationEngine(provider)
            result = engine.step(session_of(request.text))
            self.assertIs(result.action, ConversationAction.BUILD, f"seed={seed}")
            self.assertEqual(provider.calls, 0, f"seed={seed} {request.text!r}")
            return
        self.fail(f"seed={seed}: 速い道を通る自由文が40件で1つも出なかった")


class TestTheFastPathCannotBeForgotten(unittest.TestCase):
    """**既定で有効であること。** 渡し忘れたら遅い道、にしない。"""

    def test_it_is_on_by_default(self) -> None:
        provider = _CountingProvider()
        ConversationEngine(provider).step(session_of(REAL_DEVICE_FAILURE))
        self.assertEqual(provider.calls, 0)

    def test_an_engine_built_without_init_still_has_it(self) -> None:
        """`__init__` を差し替えるテストが既にある。それでも有効であること。"""
        engine = ConversationEngine.__new__(ConversationEngine)
        engine._provider = _CountingProvider()  # noqa: SLF001
        result = engine.step(session_of(REAL_DEVICE_FAILURE))
        self.assertIs(result.action, ConversationAction.BUILD)


if __name__ == "__main__":
    unittest.main()
