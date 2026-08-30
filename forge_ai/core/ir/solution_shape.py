"""Legacy IR representation chooser for already-resolved entity structures.

This module is **not** Forge's product-level capability planner and must not be
used to decide what the user really asked for.  That responsibility belongs to
the semantic Capability Plan and, when a requirement cannot be represented, the
Capability Gap / Self-Extension path.

Historically this module was described as deciding the application's "solution
shape" from entity fields alone.  That framing was too strong: field shape
cannot tell whether a user wanted a counter, simulation, derived calculation,
map, external effect, or another capability.  Treating the nearest available IR
shape as the answer is exactly the kind of goal substitution Whole Scan forbids.

The only remaining responsibility here is narrower and compatibility-oriented:
for a semantic request that has **already been resolved as an entity/list style
representation**, choose between the two legacy renderable representations
without dropping entity fields:

* ``CHECKLIST`` when the entity can be represented losslessly by checklist state
* ``RECORD_CRUD`` for a multi-attribute record entity

A missing capability must never be converted into RECORD_CRUD merely because
RECORD_CRUD exists.  Counter/increment, transforms, effects, simulations, etc.
must be identified by the semantic planner before this module is reached.
"""

from __future__ import annotations

from enum import Enum

from forge_ai.core.ir.ir_types import Entity, FieldType

__all__ = ["SolutionShape", "select_solution_shape"]


class SolutionShape(str, Enum):
    """Legacy render representation, not a catalog of product capabilities."""

    CHECKLIST = "checklist"
    """並べて、消す。属性を持たない項目の集まり。"""

    RECORD_CRUD = "record_crud"
    """1件が複数の属性を持つ記録。"""


# CHECKLIST形が吸収できるField型。`checklist`Stateの1項目は
# `{id, text, done}`という形であり、「表示する文字列」1つと
# 「済んだか」1つをちょうど表現できる(それ以上の属性は持てない)。
_CHECKLIST_TEXT_TYPES = frozenset({FieldType.STRING})
_CHECKLIST_DONE_TYPES = frozenset({FieldType.BOOLEAN})


def select_solution_shape(entity: Entity) -> SolutionShape:
    """Choose a lossless legacy representation for an already-resolved entity.

    ``CHECKLIST`` is allowed only when checklist state can preserve every field:

    * one string field
    * one string field plus one boolean field

    Otherwise the entity is represented as ``RECORD_CRUD`` so its attributes are
    not discarded.  This fallback is only a representation decision *inside an
    already-resolved record-entity path*.  It is not permission to reinterpret
    an unresolved semantic requirement as CRUD.
    """
    fields = entity.fields
    if not fields:
        # Defensive legacy behavior.  Product-level UNKNOWN structure must have
        # been rejected earlier by the Capability Gate; this branch must not be
        # used as semantic fallback.
        return SolutionShape.RECORD_CRUD

    if len(fields) == 1 and fields[0].type in _CHECKLIST_TEXT_TYPES:
        return SolutionShape.CHECKLIST

    if len(fields) == 2:
        types = {f.type for f in fields}
        if types == _CHECKLIST_TEXT_TYPES | _CHECKLIST_DONE_TYPES:
            return SolutionShape.CHECKLIST

    return SolutionShape.RECORD_CRUD
