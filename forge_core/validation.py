"""Forge Core validation.

Operationを実行する前の検証結果を表現する。
実行そのものは担当しない。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from forge_core.errors import CoreError
from forge_core.operation import SUPPORTED_OPERATION_IDS, Operation
from forge_core.state import State


@dataclass(frozen=True)
class ValidationResult:
    """Operationの検証結果。"""

    valid: bool
    errors: tuple[CoreError, ...]

    def __post_init__(self) -> None:
        if self.valid and self.errors:
            raise ValueError("valid validation result cannot contain errors")

        if not self.valid and not self.errors:
            raise ValueError("invalid validation result must contain errors")

    @classmethod
    def success(cls) -> ValidationResult:
        """検証成功を生成する。"""
        return cls(valid=True, errors=())

    @classmethod
    def failure(cls, errors: Iterable[CoreError]) -> ValidationResult:
        """検証失敗を生成する。"""
        collected = tuple(errors)

        if not collected:
            raise ValueError("failure requires at least one error")

        return cls(valid=False, errors=collected)


def validate_operation(state: State, operation: Operation) -> ValidationResult:
    """Core v0.1のOperation契約を決定論的に検証する。

    検証は実行を行わない。Operation ID、target、必須引数など、
    実行に必要な条件だけを確認する。
    """

    errors: list[CoreError] = []

    if operation.operation_id not in SUPPORTED_OPERATION_IDS:
        errors.append(
            CoreError(
                code="INVALID_OPERATION",
                message=f"unsupported operation: {operation.operation_id}",
            )
        )
        return ValidationResult.failure(errors)

    if not state.contains(operation.target):
        errors.append(
            CoreError(
                code="NOT_FOUND",
                message=f"target not found: {operation.target}",
            )
        )

    if operation.operation_id == "set_value" and not operation.has_argument("value"):
        errors.append(
            CoreError(
                code="INVALID_VALUE",
                message="set_value requires a value argument",
            )
        )

    return ValidationResult.failure(errors) if errors else ValidationResult.success()
