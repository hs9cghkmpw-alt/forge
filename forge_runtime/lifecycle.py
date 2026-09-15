"""Explicit Runtime invocation lifecycle."""

from enum import Enum


class LifecycleState(str, Enum):
    CREATED = "CREATED"
    ADMITTED = "ADMITTED"
    EXECUTING = "EXECUTING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    REJECTED = "REJECTED"


_ALLOWED_TRANSITIONS: dict[LifecycleState, frozenset[LifecycleState]] = {
    LifecycleState.CREATED: frozenset({LifecycleState.ADMITTED, LifecycleState.REJECTED}),
    LifecycleState.ADMITTED: frozenset({LifecycleState.EXECUTING}),
    LifecycleState.EXECUTING: frozenset({LifecycleState.COMPLETED, LifecycleState.FAILED}),
    LifecycleState.COMPLETED: frozenset(),
    LifecycleState.FAILED: frozenset(),
    LifecycleState.REJECTED: frozenset(),
}


def can_transition(current: LifecycleState, target: LifecycleState) -> bool:
    return target in _ALLOWED_TRANSITIONS[current]
