"""Forge Core errors.

Coreで扱う安定した機械可読エラー。
"""

from __future__ import annotations

from dataclasses import dataclass


ERROR_CODES = frozenset(
    {
        "INVALID_VALUE",
        "INVALID_OPERATION",
        "PRECONDITION_FAILED",
        "STATE_CONFLICT",
        "NOT_FOUND",
        "PERMISSION_DENIED",
        "INTERNAL_INVARIANT_VIOLATION",
    }
)


@dataclass(frozen=True)
class CoreError:
    """Coreで公開する構造化エラー。"""

    code: str
    message: str

    def __post_init__(self) -> None:
        if self.code not in ERROR_CODES:
            raise ValueError(f"unsupported error code: {self.code}")
        if not self.message:
            raise ValueError("error message must not be empty")
