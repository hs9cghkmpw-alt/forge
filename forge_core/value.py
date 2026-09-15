"""Forge Core Value primitives.

Core内部で扱う値の最小契約。
値は決定論的かつ不変に扱えるデータだけを受け付ける。
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any


def canonical_data(data: Any) -> Any:
    """Value.dataを決定論的かつ不変な正規化表現へ変換する。"""

    if data is None:
        return None

    if isinstance(data, bool):
        return ("bool", data)

    if isinstance(data, int):
        return ("int", data)

    if isinstance(data, float):
        if not math.isfinite(data):
            raise ValueError("float data must be finite")
        return ("float", data)

    if isinstance(data, str):
        return ("str", data)

    if isinstance(data, list):
        return (
            "list",
            tuple(canonical_data(item) for item in data),
        )

    if isinstance(data, tuple):
        return (
            "tuple",
            tuple(canonical_data(item) for item in data),
        )

    if isinstance(data, dict):
        frozen_items = []

        for key, value in data.items():
            if not isinstance(key, str) or not key:
                raise ValueError(
                    "dictionary keys must be non-empty strings"
                )

            frozen_items.append(
                (key, canonical_data(value))
            )

        frozen_items.sort(key=lambda item: item[0])

        return ("dict", tuple(frozen_items))

    raise TypeError(
        f"unsupported Value.data type: {type(data).__name__}"
    )


@dataclass(frozen=True)
class Value:
    """型情報と値を組み合わせた不変のCore値。"""

    type_name: str
    data: Any

    def __post_init__(self) -> None:
        if not self.type_name:
            raise ValueError("type_name must not be empty")

        object.__setattr__(
            self,
            "data",
            canonical_data(self.data),
        )

    def is_type(self, type_name: str) -> bool:
        """指定された型名と一致するか判定する。"""
        return self.type_name == type_name

    def canonical(self) -> Any:
        """決定論的なデータ表現を返す。"""
        return self.data
