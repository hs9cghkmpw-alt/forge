"""Explicit Runtime context and capability boundary."""

from dataclasses import dataclass


@dataclass(frozen=True)
class RuntimeContext:
    """Immutable context admitted for one Runtime invocation."""

    capabilities: frozenset[str] = frozenset()

    def has_capability(self, capability: str) -> bool:
        return capability in self.capabilities
