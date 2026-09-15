"""Forge Core Operation.

Coreが実行対象として受け取る構造化操作。
自然言語AIUIDBHTTPOSには依存しない。
"""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping

from forge_core.value import Value


@dataclass(frozen=True)
class Operation:
    """Core実行対象となる不変の操作定義。"""

    operation_id: str
    target: str
    arguments: Mapping[str, Value]

    def __post_init__(self) -> None:
        if not self.operation_id:
            raise ValueError("operation_id must not be empty")

        if not self.target:
            raise ValueError("target must not be empty")

        if not isinstance(self.arguments, Mapping):
            raise TypeError("arguments must be a mapping")

        copied = dict(self.arguments)

        for key, value in copied.items():
            if not isinstance(key, str) or not key:
                raise ValueError("argument keys must be non-empty strings")
            if not isinstance(value, Value):
                raise TypeError("operation arguments must be Value instances")

        object.__setattr__(self, "arguments", MappingProxyType(copied))

    def argument(self, name: str) -> Value | None:
        """指定された引数を取得する。"""
        return self.arguments.get(name)

    def has_argument(self, name: str) -> bool:
        """指定された引数が存在するか判定する。"""
        return name in self.arguments
