from __future__ import annotations

import pytest

from forge_ai.core.logic.ga1_logic import ForgeLogicSpec, LogicSpecError


def test_logic_spec_serializes_derived_and_visibility_without_domain_assumptions() -> None:
    balance = {
        "kind": "binary", "op": "subtract",
        "left": {"kind": "state", "key": "income"},
        "right": {"kind": "state", "key": "expense"},
    }
    negative = {
        "kind": "binary", "op": "lt",
        "left": balance,
        "right": {"kind": "literal", "value": 0},
    }
    spec = ForgeLogicSpec(
        derived={"balance": balance},
        visible_when={"deficit_warning": negative},
    )

    assert spec.to_json_dict() == {
        "derived": {"balance": balance},
        "visible_when": {"deficit_warning": negative},
    }


def test_unknown_expression_operator_fails_closed() -> None:
    spec = ForgeLogicSpec(
        derived={
            "value": {
                "kind": "binary", "op": "execute_python",
                "left": {"kind": "literal", "value": 1},
                "right": {"kind": "literal", "value": 2},
            }
        }
    )
    with pytest.raises(LogicSpecError, match="unsupported binary op"):
        spec.to_json_dict()


def test_aggregate_requires_source_and_field_except_count() -> None:
    with pytest.raises(LogicSpecError, match="requires field"):
        ForgeLogicSpec(derived={
            "sum": {"kind": "aggregate", "op": "sum", "source": "records"}
        }).to_json_dict()

    assert ForgeLogicSpec(derived={
        "count": {"kind": "aggregate", "op": "count", "source": "records"}
    }).to_json_dict()["derived"]
