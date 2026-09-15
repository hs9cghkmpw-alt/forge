"""Runtime invocation request boundary.

The request is intentionally small and language-neutral. It carries the
explicit inputs required to invoke one Forge Core operation.
"""

from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any, Mapping

from forge_core.operation import Operation
from forge_core.state import State


@dataclass(frozen=True)
class RuntimeRequest:
    """Immutable request to invoke exactly one Core operation."""

    invocation_id: str
    operation: Operation
    initial_state: State
    declared_capabilities: frozenset[str] = frozenset()
    execution_metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.invocation_id:
            raise ValueError("invocation_id must not be empty")
        object.__setattr__(
            self,
            "execution_metadata",
            MappingProxyType(dict(self.execution_metadata)),
        )
        object.__setattr__(
            self,
            "declared_capabilities",
            frozenset(self.declared_capabilities),
        )
