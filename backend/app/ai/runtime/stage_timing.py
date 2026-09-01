"""**どの段が遅いのかを、本番経路そのもので測る**（2026-09-01）。

---

## なぜ要るのか

実機で `/api/v1/ai/converse` が 73.54 秒かかった。会話の判定を速い道へ
逃がして、その判定は 0.09 ミリ秒になった。

**しかしそれは「ASK / BUILD を決めるところ」だけの数字である。**
そのあと `PromptPipeline` が実際に画面を作る。そこが何秒かかるのかは
**まだ誰も測っていない。**

「速くなった」と言うためには、**どの段が何秒か**が分かれていなければ
ならない。合計だけ見て「1つ速くしたから全部速い」と丸めない。

## 測り方

計測器を context variable に置く。段を測りたい場所は

```python
with stage("validator"):
    ...
```

と書くだけでよい。呼び出し側へ引数を通して回らないので、深いところ
（Validator など）も、そこだけ見て測れる。

**計測していないときは何もしない。** `measuring()` の外で `stage()` を
呼んでも、記録先が無いので素通りする——計測のために本番の形を変えない。

## 数えるもの

時間だけでなく回数も持つ。「速いが 10 回呼んでいる」と
「遅いが 1 回」は別の問題であり、混ぜると直せない。
"""

from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
import time
from typing import Iterator

__all__ = [
    "StageTimings",
    "count",
    "current_timings",
    "measuring",
    "note",
    "stage",
]


@dataclass(slots=True)
class StageTimings:
    """1回の要求の中で、どの段に何ミリ秒かかったか。"""

    stages_ms: dict[str, float] = field(default_factory=dict)
    """段の名前 → 合計ミリ秒。**同じ段を複数回通ったら足す**
    （Validator は repair のたびに走る）。"""

    stage_calls: dict[str, int] = field(default_factory=dict)
    """段の名前 → 通った回数。"""

    counters: dict[str, int] = field(default_factory=dict)
    """LLM 呼び出し回数・生成回数など。"""

    notes: dict[str, str] = field(default_factory=dict)
    """速い道を通ったか、などの短い事実。"""

    def record(self, name: str, elapsed_ms: float) -> None:
        self.stages_ms[name] = round(self.stages_ms.get(name, 0.0) + elapsed_ms, 3)
        self.stage_calls[name] = self.stage_calls.get(name, 0) + 1

    def to_dict(self) -> dict[str, object]:
        return {
            "stages_ms": dict(self.stages_ms),
            "stage_calls": dict(self.stage_calls),
            "counters": dict(self.counters),
            "notes": dict(self.notes),
        }


_CURRENT: ContextVar[StageTimings | None] = ContextVar(
    "forge_stage_timings", default=None,
)


def current_timings() -> StageTimings | None:
    """いま計測中なら計測器。していなければ `None`。"""
    return _CURRENT.get()


@contextmanager
def measuring() -> Iterator[StageTimings]:
    """計測を始める。**入口で1回だけ呼ぶ。**"""
    timings = StageTimings()
    token = _CURRENT.set(timings)
    try:
        yield timings
    finally:
        _CURRENT.reset(token)


@contextmanager
def stage(name: str) -> Iterator[None]:
    """1つの段を測る。計測していなければ**何もしない**。"""
    timings = _CURRENT.get()
    if timings is None:
        yield
        return
    started = time.perf_counter()
    try:
        yield
    finally:
        timings.record(name, (time.perf_counter() - started) * 1000.0)


def count(name: str, amount: int = 1) -> None:
    """回数を数える。計測していなければ何もしない。"""
    timings = _CURRENT.get()
    if timings is not None:
        timings.counters[name] = timings.counters.get(name, 0) + amount


def note(name: str, value: str) -> None:
    """短い事実を残す。計測していなければ何もしない。"""
    timings = _CURRENT.get()
    if timings is not None:
        timings.notes[name] = value
