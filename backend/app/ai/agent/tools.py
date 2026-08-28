"""Tool Contract / Tool Broker — **Modelは道具を「呼びたい」としか言えない**
(FORGE-020 §14、2026-08-25)。

---

## 任意の shell 文字列を実行しない

Agent へ道具を渡すやり方は2つある。

```
❌  Model が書いた文字列を shell へ渡す
✅  Model は道具名と引数を選ぶ。実行の仕方は Forge が持つ
```

前者は書きやすいが、**Model の入力（＝Web ページや Provider の出力）が
そのまま実行文字列になる**。境界がどこにも無い。

`ToolCall` は「道具名 + 引数の辞書」しか運ばない。実行の中身は
`ToolSpec.run` が持ち、Forge のコードである。

## 呼び出しは必ず Broker を通る

`ToolBroker.invoke()` の中で

1. 道具が登録されているか（**知らない道具は動かない**）
2. 引数が宣言どおりか（**知らない引数は落とす**）
3. `PermissionBroker` の判定
4. 実行（例外は `ToolResult` へ畳む——Agent Loop を例外で殺さない）
5. 出力の大きさを切る
6. **secret らしき文字列を伏せる**

を順に行う。どれかを飛ばす近道を作らない。
"""

from __future__ import annotations

import re
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from enum import Enum

from app.ai.agent.permission import (
    PermissionBroker,
    PermissionDecision,
    default_permission_broker,
)

__all__ = [
    "ToolBroker",
    "ToolCall",
    "ToolOutcome",
    "ToolResult",
    "ToolSpec",
    "redact_secrets",
]


class ToolOutcome(str, Enum):
    OK = "ok"
    DENIED = "denied"
    """権限で断った。"""

    UNKNOWN_TOOL = "unknown_tool"
    INVALID_ARGUMENTS = "invalid_arguments"
    FAILED = "failed"
    """道具が例外を投げた。**Agent Loop は続けられる。**"""


@dataclass(frozen=True)
class ToolCall:
    """Model が「使いたい」と言った1件。**structured。**"""

    tool: str
    arguments: Mapping[str, object] = field(default_factory=dict)
    call_id: str = ""

    def signature(self) -> str:
        """同じ呼び出しかどうかの照合用。**重複を数えるために使う。**"""
        items = sorted((str(k), repr(v)) for k, v in self.arguments.items())
        return f"{self.tool}({','.join(f'{k}={v}' for k, v in items)})"


#: 出力に混ざった秘密らしき文字列。**長さも先頭も出さない**（`CLAUDE.md` §4）。
_SECRET_PATTERNS: tuple["re.Pattern[str]", ...] = (
    re.compile(r"sk-[A-Za-z0-9_-]{8,}"),
    re.compile(r"gh[pousr]_[A-Za-z0-9]{8,}"),
    re.compile(r"AIza[A-Za-z0-9_-]{8,}"),
    re.compile(r"(?i)\b(api[_-]?key|secret|password|token)\b\s*[:=]\s*\S+"),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
)


def redact_secrets(text: str) -> str:
    """秘密らしき部分を伏せる。**残りは残す。**

    全文を捨てると、道具の出力が読めなくなって Agent が仕事を進め
    られない。伏せるのは一致した部分だけにする。
    """
    for pattern in _SECRET_PATTERNS:
        text = pattern.sub("[REDACTED]", text)
    return text


@dataclass(frozen=True)
class ToolResult:
    """1回の呼び出しの結果。**例外を外へ出さない。**"""

    tool: str
    outcome: ToolOutcome
    call_id: str = ""
    content: str = ""
    error: str = ""
    permission: PermissionDecision | None = None
    duration_ms: float = 0.0
    truncated: bool = False

    @property
    def ok(self) -> bool:
        return self.outcome is ToolOutcome.OK

    def to_dict(self) -> dict[str, object]:
        return {
            "tool": self.tool,
            "outcome": self.outcome.value,
            "call_id": self.call_id,
            "error": self.error,
            "duration_ms": round(self.duration_ms, 2),
            "truncated": self.truncated,
            "content_length": len(self.content),
            "permission": self.permission.to_dict() if self.permission else None,
        }


@dataclass(frozen=True)
class ToolSpec:
    """道具1つ。**実行の中身は Forge のコードである。**"""

    name: str
    description: str
    required: tuple[str, ...] = ()
    optional: tuple[str, ...] = ()
    run: Callable[..., str] = field(default=lambda **_: "", repr=False)

    def validate(self, arguments: Mapping[str, object]) -> str:
        """引数を検査する。**知らない引数は通さない。**

        余分な引数を黙って捨てると、`path` の綴りを間違えた呼び出しが
        「既定値で実行された」ことになる。落とす方が安全である。
        """
        missing = [k for k in self.required if k not in arguments]
        if missing:
            return f"必須の引数が無い: {', '.join(missing)}"
        allowed = set(self.required) | set(self.optional)
        unexpected = [k for k in arguments if k not in allowed]
        if unexpected:
            return f"知らない引数: {', '.join(sorted(unexpected))}"
        return ""


class ToolBroker:
    """道具の登録と、呼び出しの唯一の口。"""

    _MAX_OUTPUT = 40_000

    def __init__(
        self,
        *,
        permissions: PermissionBroker | None = None,
        in_sandbox: bool = False,
        confirmed_tools: frozenset[str] = frozenset(),
    ) -> None:
        self._specs: dict[str, ToolSpec] = {}
        self._permissions = permissions or default_permission_broker()
        self._in_sandbox = in_sandbox
        self._confirmed = confirmed_tools
        self.calls: list[ToolCall] = []

    def register(self, spec: ToolSpec) -> None:
        self._specs[spec.name] = spec

    def available(self) -> tuple[str, ...]:
        return tuple(sorted(self._specs))

    def describe(self) -> tuple[dict[str, object], ...]:
        """Model へ見せる道具一覧。**実行の中身は見せない。**"""
        return tuple(
            {
                "name": spec.name,
                "description": spec.description,
                "required": list(spec.required),
                "optional": list(spec.optional),
                "permission": self._permissions.evaluate(
                    spec.name, in_sandbox=self._in_sandbox,
                    user_confirmed=spec.name in self._confirmed,
                ).tier.value,
            }
            for spec in sorted(self._specs.values(), key=lambda s: s.name)
        )

    def invoke(self, call: ToolCall) -> ToolResult:
        """1件実行する。**ここを通らない実行経路を作らない。**"""
        self.calls.append(call)
        spec = self._specs.get(call.tool)
        if spec is None:
            return ToolResult(
                call.tool, ToolOutcome.UNKNOWN_TOOL, call_id=call.call_id,
                error="登録されていない道具",
            )

        invalid = spec.validate(call.arguments)
        if invalid:
            return ToolResult(
                call.tool, ToolOutcome.INVALID_ARGUMENTS, call_id=call.call_id, error=invalid
            )

        decision = self._permissions.evaluate(
            call.tool, in_sandbox=self._in_sandbox,
            user_confirmed=call.tool in self._confirmed,
        )
        if not decision.allowed:
            return ToolResult(
                call.tool, ToolOutcome.DENIED, call_id=call.call_id,
                error=decision.reason, permission=decision,
            )

        started = time.perf_counter()
        try:
            raw = spec.run(**dict(call.arguments))
        except Exception as error:  # noqa: BLE001 — 道具の失敗で Loop を殺さない
            return ToolResult(
                call.tool, ToolOutcome.FAILED, call_id=call.call_id,
                error=redact_secrets(f"{type(error).__name__}: {error}"),
                permission=decision,
                duration_ms=(time.perf_counter() - started) * 1000,
            )

        content = redact_secrets(str(raw))
        truncated = len(content) > self._MAX_OUTPUT
        if truncated:
            content = content[: self._MAX_OUTPUT]
        return ToolResult(
            call.tool, ToolOutcome.OK, call_id=call.call_id,
            content=content, permission=decision,
            duration_ms=(time.perf_counter() - started) * 1000, truncated=truncated,
        )
