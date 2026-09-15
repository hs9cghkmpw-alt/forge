"""Forge Core evidence.

Core自身が観測した実行事実を記録する。
AIや外部システムの主張とは区別する。
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Evidence:
    """Core実行について観測された事実。"""

    operation_id: str
    validation_passed: bool
    execution_succeeded: bool
    state_before_id: str
    state_after_id: str | None
    verification_facts: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.operation_id:
            raise ValueError("operation_id must not be empty")

        if not self.state_before_id:
            raise ValueError("state_before_id must not be empty")

        if self.execution_succeeded and self.state_after_id is None:
            raise ValueError(
                "successful execution requires state_after_id"
            )

        if not self.execution_succeeded and self.state_after_id is not None:
            raise ValueError(
                "failed execution must not contain state_after_id"
            )
