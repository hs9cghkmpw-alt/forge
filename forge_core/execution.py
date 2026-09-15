"""Forge Core execution.

Validation済みOperationをStateへ原子的に適用する。
"""

from __future__ import annotations

from dataclasses import dataclass

from forge_core.errors import CoreError
from forge_core.evidence import Evidence
from forge_core.operation import Operation
from forge_core.state import State
from forge_core.validation import validate_operation


@dataclass(frozen=True)
class ExecutionResult:
    """Core実行結果。"""

    success: bool
    state: State
    errors: tuple[CoreError, ...]
    evidence: Evidence

    def __post_init__(self) -> None:
        if self.success and self.errors:
            raise ValueError("successful execution cannot contain errors")

        if not self.success and not self.errors:
            raise ValueError("failed execution must contain errors")

        if self.success != self.evidence.execution_succeeded:
            raise ValueError("execution result and evidence must agree")

    @classmethod
    def failure(
        cls,
        original_state: State,
        operation: Operation,
        errors: tuple[CoreError, ...],
        validation_passed: bool,
    ) -> ExecutionResult:
        """失敗結果を生成する。"""
        evidence = Evidence(
            operation_id=operation.operation_id,
            validation_passed=validation_passed,
            execution_succeeded=False,
            state_before_id=original_state.identity(),
            state_after_id=None,
            verification_facts=("state_unchanged_on_failure",),
        )

        return cls(
            success=False,
            state=original_state,
            errors=errors,
            evidence=evidence,
        )

    @classmethod
    def success_result(
        cls,
        original_state: State,
        new_state: State,
        operation: Operation,
    ) -> ExecutionResult:
        """成功結果を生成する。"""
        evidence = Evidence(
            operation_id=operation.operation_id,
            validation_passed=True,
            execution_succeeded=True,
            state_before_id=original_state.identity(),
            state_after_id=new_state.identity(),
            verification_facts=(
                "validation_passed",
                "candidate_state_created",
                "target_present",
                "state_result_observed",
            ),
        )

        return cls(
            success=True,
            state=new_state,
            errors=(),
            evidence=evidence,
        )


def execute(state: State, operation: Operation) -> ExecutionResult:
    """Operationを検証してから原子的に実行する。"""

    validation = validate_operation(state, operation)

    if not validation.valid:
        return ExecutionResult.failure(
            original_state=state,
            operation=operation,
            errors=validation.errors,
            validation_passed=False,
        )

    value = operation.argument("value")

    if value is None:
        return ExecutionResult.failure(
            original_state=state,
            operation=operation,
            errors=(
                CoreError(
                    code="INTERNAL_INVARIANT_VIOLATION",
                    message="validated set_value is missing its value argument",
                ),
            ),
            validation_passed=True,
        )

    candidate = state.with_value(operation.target, value)

    if not candidate.contains(operation.target):
        return ExecutionResult.failure(
            original_state=state,
            operation=operation,
            errors=(
                CoreError(
                    code="INTERNAL_INVARIANT_VIOLATION",
                    message="candidate state lost the operation target",
                ),
            ),
            validation_passed=True,
        )

    return ExecutionResult.success_result(
        original_state=state,
        new_state=candidate,
        operation=operation,
    )
