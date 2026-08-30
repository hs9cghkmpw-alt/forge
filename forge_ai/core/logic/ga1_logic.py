"""Compiler-neutral GA-1 logic model.

This module is the Python-side Source of Truth for serializable derived values
and conditional visibility. It does not know domains, widgets, or Golden apps;
it only emits deterministic Forge Language logic data consumed by the runtime.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping, Any


class LogicSpecError(ValueError):
    pass


_ALLOWED_KINDS = frozenset({"literal", "state", "unary", "binary", "aggregate"})
_ALLOWED_UNARY = frozenset({"not", "negate"})
_ALLOWED_BINARY = frozenset({
    "add", "subtract", "multiply", "divide",
    "eq", "neq", "lt", "lte", "gt", "gte", "and", "or",
})
_ALLOWED_AGGREGATE = frozenset({"sum", "count", "average", "min", "max"})


def validate_expression(node: Mapping[str, Any]) -> None:
    kind = node.get("kind")
    if kind not in _ALLOWED_KINDS:
        raise LogicSpecError(f"unsupported expression kind: {kind!r}")
    if kind == "literal":
        return
    if kind == "state":
        if not isinstance(node.get("key"), str) or not node["key"]:
            raise LogicSpecError("state.key is required")
        return
    if kind == "unary":
        if node.get("op") not in _ALLOWED_UNARY:
            raise LogicSpecError(f"unsupported unary op: {node.get('op')!r}")
        value = node.get("value")
        if not isinstance(value, Mapping):
            raise LogicSpecError("unary.value must be an expression")
        validate_expression(value)
        return
    if kind == "binary":
        if node.get("op") not in _ALLOWED_BINARY:
            raise LogicSpecError(f"unsupported binary op: {node.get('op')!r}")
        for side in ("left", "right"):
            child = node.get(side)
            if not isinstance(child, Mapping):
                raise LogicSpecError(f"binary.{side} must be an expression")
            validate_expression(child)
        return
    if node.get("op") not in _ALLOWED_AGGREGATE:
        raise LogicSpecError(f"unsupported aggregate op: {node.get('op')!r}")
    if not isinstance(node.get("source"), str) or not node["source"]:
        raise LogicSpecError("aggregate.source is required")
    if node.get("op") != "count" and (not isinstance(node.get("field"), str) or not node["field"]):
        raise LogicSpecError(f"aggregate.{node.get('op')} requires field")


@dataclass(frozen=True, slots=True)
class ForgeLogicSpec:
    derived: Mapping[str, Mapping[str, Any]] = field(default_factory=dict)
    visible_when: Mapping[str, Mapping[str, Any]] = field(default_factory=dict)

    def validate(self) -> None:
        for collection_name, collection in (
            ("derived", self.derived),
            ("visible_when", self.visible_when),
        ):
            for name, expression in collection.items():
                if not isinstance(name, str) or not name:
                    raise LogicSpecError(f"{collection_name} requires non-empty names")
                validate_expression(expression)

    def to_json_dict(self) -> dict[str, object]:
        self.validate()
        result: dict[str, object] = {}
        if self.derived:
            result["derived"] = {key: dict(value) for key, value in self.derived.items()}
        if self.visible_when:
            result["visible_when"] = {key: dict(value) for key, value in self.visible_when.items()}
        return result
