"""Forge Core State.

Core実行に必要な状態を、不変な値の集合として扱う。
状態識別子は決定論的な正規化表現から生成する。
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping

from forge_core.value import Value


@dataclass(frozen=True)
class State:
    """Core実行時の不変状態。"""

    values: Mapping[str, Value]

    def __post_init__(self) -> None:
        if not isinstance(self.values, Mapping):
            raise TypeError("values must be a mapping")

        copied = dict(self.values)

        for key, value in copied.items():
            if not isinstance(key, str) or not key:
                raise ValueError("state keys must be non-empty strings")
            if not isinstance(value, Value):
                raise TypeError("state values must be Value instances")

        object.__setattr__(self, "values", MappingProxyType(copied))

    @classmethod
    def empty(cls) -> State:
        """空の状態を作る。"""
        return cls(values={})

    def get(self, key: str) -> Value | None:
        """状態から値を取得する。"""
        return self.values.get(key)

    def contains(self, key: str) -> bool:
        """指定されたキーが存在するか判定する。"""
        return key in self.values

    def with_value(self, key: str, value: Value) -> State:
        """値を追加置換した新しいStateを返す。"""
        if not key:
            raise ValueError("state key must not be empty")
        if not isinstance(value, Value):
            raise TypeError("value must be a Value instance")

        updated = dict(self.values)
        updated[key] = value
        return State(values=updated)

    def without(self, key: str) -> State:
        """値を削除した新しいStateを返す。"""
        updated = dict(self.values)
        updated.pop(key, None)
        return State(values=updated)

    def identity(self) -> str:
        """状態内容から決定論的な識別子を生成する。"""
        canonical = tuple(
            sorted(
                (
                    key,
                    value.type_name,
                    value.canonical(),
                )
                for key, value in self.values.items()
            )
        )

        encoded = repr(canonical).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()
