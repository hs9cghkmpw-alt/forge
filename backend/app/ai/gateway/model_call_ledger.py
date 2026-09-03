"""**呼んでいない Provider の名前を Evidence へ書かない**（TD104）。

---

## 何が起きていたか

`/api/v1/ai/converse` は、実際に応答を生成した Provider をこう決めていた。

```python
provider_name = provider.last_provider_used or request.provider or "unknown"
```

`last_provider_used` は**実際に呼んで成功した Provider** なので正しい。
問題は次の 2 つである。

1. **`or request.provider`** ——`last_provider_used` が `None`（1回も
   呼んでいない）ときに、**指定されただけの Provider 名**へ落ちる。
   Fast path は LLM を 0 回しか呼ばないので、`provider=gemini` を指定した
   要求は「Gemini が答えた」という Evidence を残す。**呼んでいない。**
2. **`"unknown"`** ——「0 回呼んだ」と「呼んだが名前が取れなかった」を
   同じ語へ潰している。前者は事実が確定していて、後者は記録漏れである。
   混ぜると、後から区別できない。

配線された Provider（configured）と、実際に応答を返した Provider
（actually used）は**別の事実**である。

## この Ledger が答えること

| 問い | フィールド |
|---|---|
| 何回 Model を呼んだか | `model_calls` |
| 実際に答えたのは誰か | `actually_used_provider`（0 回なら `None`） |
| Model を1回も呼んでいないか | `deterministic_path` |
| fallback したか | `fallback_used` |
| 何を試して何が落ちたか | `attempted_providers` / `failed_providers` |

**0 回のときに Provider 名を作らない。** `actually_used_provider` は
`None` のままにし、報告名は `"none"`（呼んでいない）になる。

## 記録する場所

`AIRouter` 経由の `_BoundAdapter.complete_structured()` が唯一の
Model 呼び出し口である。そこで `record_routed_result()` を呼ぶ。
呼び出し側が個別に数える設計にはしない——数え忘れた経路が
「0 回」に見えてしまい、**間違いが安全側でなく楽観側へ倒れる**。

計測していないとき（`recording()` の外）は素通りする。計測のために
本番の形を変えない（`stage_timing` と同じ考え方）。
"""

from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from typing import Any, Iterator

__all__ = [
    "ModelCall",
    "ModelCallLedger",
    "ProviderAttribution",
    "NO_MODEL_CALL",
    "UNRECORDED_PROVIDER",
    "current_ledger",
    "record_model_call",
    "record_routed_result",
    "recording",
]

#: Model を 1 回も呼んでいないときの報告名。**Provider 名ではない。**
NO_MODEL_CALL = "none"

#: 呼んだが名前を記録できなかったときの報告名。`NO_MODEL_CALL` と混ぜない。
UNRECORDED_PROVIDER = "unrecorded"


@dataclass(frozen=True, slots=True)
class ModelCall:
    """Model を 1 回呼んだ事実。**試行単位**であり、成功だけではない。"""

    provider: str
    model: str
    ok: bool
    latency_ms: float = 0.0
    detail: str = ""


@dataclass(slots=True)
class ModelCallLedger:
    """1 リクエスト分の Model 呼び出し記録。"""

    calls: list[ModelCall] = field(default_factory=list)

    def record(self, call: ModelCall) -> None:
        self.calls.append(call)

    @property
    def model_calls(self) -> int:
        """**試行の総数。** 失敗した試行も 1 回である（呼んだのだから）。"""
        return len(self.calls)

    @property
    def successful_calls(self) -> int:
        return sum(1 for call in self.calls if call.ok)

    @property
    def attempted_providers(self) -> tuple[str, ...]:
        seen: list[str] = []
        for call in self.calls:
            if call.provider and call.provider not in seen:
                seen.append(call.provider)
        return tuple(seen)

    @property
    def failed_providers(self) -> tuple[str, ...]:
        seen: list[str] = []
        for call in self.calls:
            if not call.ok and call.provider and call.provider not in seen:
                seen.append(call.provider)
        return tuple(seen)

    @property
    def last_successful(self) -> ModelCall | None:
        for call in reversed(self.calls):
            if call.ok:
                return call
        return None

    def attribution(self, *, configured_provider: str | None) -> "ProviderAttribution":
        success = self.last_successful
        return ProviderAttribution(
            configured_provider=configured_provider,
            actually_used_provider=(
                (success.provider or UNRECORDED_PROVIDER) if success else None
            ),
            actually_used_model=(success.model if success else ""),
            model_calls=self.model_calls,
            successful_model_calls=self.successful_calls,
            attempted_providers=self.attempted_providers,
            failed_providers=self.failed_providers,
        )


@dataclass(frozen=True, slots=True)
class ProviderAttribution:
    """**設定された Provider と、実際に答えた Provider を分けて持つ。**"""

    configured_provider: str | None
    """要求や Router に**指定された**名前。指定が無ければ `None`（auto）。
    **これを「使われた」と読んではならない。**"""

    actually_used_provider: str | None
    """**実際に応答を返した** Provider。1 回も成功していなければ `None`。"""

    actually_used_model: str = ""
    model_calls: int = 0
    successful_model_calls: int = 0
    attempted_providers: tuple[str, ...] = ()
    failed_providers: tuple[str, ...] = ()

    @property
    def deterministic_path(self) -> bool:
        """Model を 1 回も呼ばずに答えたか（Fast path / Reuse）。"""
        return self.model_calls == 0

    @property
    def fallback_used(self) -> bool:
        """最初の候補が失敗して別の Provider へ移ったか。"""
        return len(self.attempted_providers) > 1

    @property
    def reported_provider(self) -> str:
        """Evidence とレスポンスへ書く名前。

        **呼んでいなければ Provider 名を作らない。**
        """
        if self.actually_used_provider:
            return self.actually_used_provider
        if self.model_calls == 0:
            return NO_MODEL_CALL
        return UNRECORDED_PROVIDER

    def to_dict(self) -> dict[str, Any]:
        return {
            "configured_provider": self.configured_provider,
            "actually_used_provider": self.actually_used_provider,
            "actually_used_model": self.actually_used_model,
            "reported_provider": self.reported_provider,
            "model_calls": self.model_calls,
            "successful_model_calls": self.successful_model_calls,
            "deterministic_path": self.deterministic_path,
            "fallback_used": self.fallback_used,
            "attempted_providers": list(self.attempted_providers),
            "failed_providers": list(self.failed_providers),
        }


_ledger: ContextVar[ModelCallLedger | None] = ContextVar(
    "forge_model_call_ledger", default=None,
)


@contextmanager
def recording() -> Iterator[ModelCallLedger]:
    """このブロックの Model 呼び出しを数える。"""
    ledger = ModelCallLedger()
    token = _ledger.set(ledger)
    try:
        yield ledger
    finally:
        _ledger.reset(token)


def current_ledger() -> ModelCallLedger | None:
    return _ledger.get()


def record_model_call(call: ModelCall) -> None:
    """記録先が無ければ素通りする（本番の形を計測で変えない）。"""
    ledger = _ledger.get()
    if ledger is not None:
        ledger.record(call)


def record_routed_result(result: Any) -> None:
    """`AIRouter` の `RoutedResult` を、試行単位で Ledger へ写す。

    `attempts` を持たない結果（Test の Fake 等）は、成功 1 回として
    最小限を残す。**「無かったこと」にはしない**——呼ばれた事実を
    落とすと、0 回だったのか記録漏れなのか分からなくなる。
    """
    if _ledger.get() is None:
        return
    attempts = getattr(result, "attempts", ()) or ()
    if attempts:
        for attempt in attempts:
            record_model_call(ModelCall(
                provider=getattr(attempt, "provider", "") or "",
                model=getattr(attempt, "model", "") or "",
                ok=bool(getattr(attempt, "ok", False)),
                latency_ms=float(getattr(attempt, "latency_ms", 0.0) or 0.0),
                detail=str(getattr(attempt, "detail", "") or ""),
            ))
        return
    record_model_call(ModelCall(
        provider=str(getattr(result, "provider_used", "") or ""),
        model="",
        ok=True,
    ))
