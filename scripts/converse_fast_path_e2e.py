"""**本番の入口（`/api/v1/ai/converse`）で速度と LLM 呼び出し回数を測る。**

---

実機（Ollama + `qwen2.5:1.5b-instruct`）で測った Before:

```text
HTTP 200 / simulated=false / **73.54 秒** / しかも記録項目を聞き返した
```

ここで測る After は、**同じ本番の Engine** を通した数字である
（`/converse` が呼ぶのと同じ `ConversationEngine.step()`）。

シナリオ:

| | 入力 | 期待 |
|---|---|---|
| A | いま持っている能力だけで作れる自由文 | **LLM 0 回**・BUILD |
| B | 本当に曖昧な自由文 | **ASK が妥当**（LLM へ渡す） |
| C | 足りない能力が要る自由文 | **missing を名指し**して自己拡張の判断へ |

入力文は毎回ランダムに作る。seed を指定すれば完全に再現できる。

## 秘密情報

実 API を呼ばない。Provider は呼び出し回数を数える Test Double である。
API キー・token の類は一切扱わない。
"""

from __future__ import annotations

import argparse
import json
import pathlib
import random
import sys
import time
from dataclasses import replace

ROOT = pathlib.Path(__file__).resolve().parents[1]
for path in (str(ROOT), str(ROOT / "backend")):
    if path not in sys.path:
        sys.path.insert(0, path)

from app.ai.runtime.conversation_engine import ConversationEngine  # noqa: E402
from app.ai.runtime.conversation_fast_path import deterministic_step  # noqa: E402
from app.ai.runtime.conversation_types import (  # noqa: E402
    ConversationAction,
    ConversationSession,
    ConversationTurn,
)
from forge_ai.core.semantics.capability_plan import plan_capabilities  # noqa: E402
from forge_ai.testing.free_text_requests import (  # noqa: E402
    RequestShape,
    generate_request,
)

LOG_OUT = ROOT / "logs" / "forge-fast-path-e2e-latest.json"

#: 実機で 73.54 秒かかり、しかも誤って聞き返した文そのもの。
REAL_DEVICE_FAILURE = "事務所の鍵を誰が持ち出していて、いつ返す予定か記録したい"
REAL_DEVICE_BEFORE_SECONDS = 73.54

#: 本当に曖昧な文（**答えを教えない**）。
VAGUE_REQUESTS = (
    "なんとかしてほしいんだけど",
    "いい感じのやつ作って",
    "いろいろ記録して一覧で見返したい",
)


class _CountingProvider:
    """**呼ばれたら数える。** 実 API は呼ばない。"""

    def __init__(self, action: str = "ask") -> None:
        self.calls = 0
        self._action = action

    def complete_structured(self, prompt, schema):  # noqa: ANN001, ANN202
        self.calls += 1
        return {
            "problem": "", "known": [],
            "unknowns": [{
                "key": "what_to_track", "impact": "blocking",
                "reason": "何を扱うのか決まっていない",
            }],
            "assumptions": [], "confidence": 0.3,
            "next_action": self._action,
            "question": "何を残しておきたいですか？",
            "question_key": "what_to_track",
            "build_brief": "",
        }


def _session(text: str) -> ConversationSession:
    return replace(
        ConversationSession(session_id="s"),
        turns=(ConversationTurn(role="user", text=text),),
    )


def _run(text: str) -> dict:
    """**本番の Engine を通す。** 別系統を作らない。"""
    provider = _CountingProvider()
    engine = ConversationEngine(provider)
    started = time.perf_counter()
    result = engine.step(_session(text))
    elapsed_ms = round((time.perf_counter() - started) * 1000.0, 2)
    return {
        "text": text,
        "action": result.action.value,
        "llm_calls": provider.calls,
        "elapsed_ms": elapsed_ms,
        "fast_path_reason": engine.last_fast_path_reason,
        "question": result.question,
    }


def _fail(message: str) -> None:
    print(f"FAIL: {message}")
    raise SystemExit(1)


def _understood_existing_only(seed: int):  # noqa: ANN202
    """速い道を通れる自由文を、seed から**決定的に**探す。"""
    misses = []
    for attempt in range(24):
        request = generate_request(seed + attempt * 1009, RequestShape.EXISTING_ONLY)
        if deterministic_step(_session(request.text)).taken:
            return request, misses
        misses.append({
            "text": request.text,
            "reason": deterministic_step(_session(request.text)).reason,
        })
    return None, misses


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", type=int, default=None)
    args = parser.parse_args()
    seed = args.seed if args.seed is not None else random.SystemRandom().randrange(1, 10**9)
    print(f"random seed: {seed}   （再現するには --seed {seed}）")

    deterministic_step(_session(REAL_DEVICE_FAILURE))  # import を温める
    report: dict[str, object] = {"seed": seed}

    print("\n=== 実機で落ちた文（Before: 73.54 秒 + 誤ったASK）===")
    real = _run(REAL_DEVICE_FAILURE)
    print(f"  入力: {real['text']}")
    print(f"  結果: {real['action']}  LLM 呼び出し {real['llm_calls']} 回  {real['elapsed_ms']} ms")
    print(f"  理由: {real['fast_path_reason']}")
    if real["action"] != ConversationAction.BUILD.value:
        _fail(f"実機で落ちた文が、まだ BUILD へ進まない: {real['action']}")
    if real["llm_calls"] != 0:
        _fail("実機で落ちた文が、まだ大きな LLM 判定を通っている")
    speedup = REAL_DEVICE_BEFORE_SECONDS * 1000.0 / max(real["elapsed_ms"], 0.001)
    print(f"  Before 73.54 秒 → After {real['elapsed_ms']} ms（約 {speedup:,.0f} 倍）")
    report["real_device_case"] = {**real, "before_seconds": REAL_DEVICE_BEFORE_SECONDS}

    print("\n=== A. いま持っている能力だけで作れる自由文（ランダム）===")
    request_a, misses_a = _understood_existing_only(seed)
    if request_a is None:
        _fail("速い道を通れる自由文が見つからなかった")
    outcome_a = _run(request_a.text)
    print(f"  入力: {outcome_a['text']}")
    print(f"  結果: {outcome_a['action']}  LLM 呼び出し {outcome_a['llm_calls']} 回  {outcome_a['elapsed_ms']} ms")
    if outcome_a["action"] != ConversationAction.BUILD.value or outcome_a["llm_calls"] != 0:
        _fail("A: 既存能力だけの要求で LLM を呼んでいる")
    report["A"] = {**outcome_a, "domain": request_a.domain}
    report["A_misses"] = misses_a

    print("\n=== B. 本当に曖昧な自由文 → ASK が妥当 ===")
    vague = []
    for text in VAGUE_REQUESTS:
        outcome = _run(text)
        print(f"  {outcome['action']:6} LLM {outcome['llm_calls']} 回  {text}")
        print(f"         理由: {outcome['fast_path_reason']}")
        if outcome["llm_calls"] == 0:
            _fail(f"B: 曖昧な要求を LLM へ渡していない: {text!r}")
        if outcome["action"] != ConversationAction.ASK.value:
            _fail(f"B: 曖昧な要求で ASK にならない: {text!r} -> {outcome['action']}")
        vague.append(outcome)
    report["B"] = vague

    print("\n=== C. 足りない能力が要る自由文（ランダム）===")
    found_c = None
    misses_c = []
    for attempt in range(24):
        request = generate_request(
            seed + 7 + attempt * 1009, RequestShape.NEEDS_MONTHLY_VIEW,
        )
        plan = plan_capabilities(request.text)
        if plan.missing:
            found_c = (request, plan)
            break
        misses_c.append(request.text)
    if found_c is None:
        _fail("足りない能力を要求する自由文が見つからなかった")
    request_c, plan_c = found_c
    outcome_c = _run(request_c.text)
    print(f"  入力: {outcome_c['text']}")
    print(f"  足りない能力: {plan_c.missing}")
    print(f"  結果: {outcome_c['action']}  LLM 呼び出し {outcome_c['llm_calls']} 回")
    print(f"  理由: {outcome_c['fast_path_reason']}")
    if "足りない能力がある" not in (outcome_c["fast_path_reason"] or ""):
        _fail("C: 足りない能力を名指しできていない")
    if outcome_c["llm_calls"] == 0:
        _fail("C: 足りない能力があるのに、判断を LLM へ渡していない")
    report["C"] = {**outcome_c, "missing": list(plan_c.missing)}
    report["C_misses"] = misses_c

    LOG_OUT.parent.mkdir(parents=True, exist_ok=True)
    LOG_OUT.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8", newline="\n",
    )
    print(f"\nログ: {LOG_OUT.relative_to(ROOT)}")
    print("\n=== まだ言えないこと ===")
    print("  BUILD へ進んだあとの生成時間は、ここでは測っていない")
    print("  実機 Chrome での完走は未確認")
    print("  Real Local Model runs = 0 のまま")


if __name__ == "__main__":
    main()
