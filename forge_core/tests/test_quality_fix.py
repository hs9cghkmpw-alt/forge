from forge_core.operation import Operation
from forge_core.state import State
from forge_core.validation import validate_operation
from forge_core.value import Value


def test_unknown_operation_is_rejected_before_state_lookup() -> None:
    result = validate_operation(
        State.empty(),
        Operation(
            operation_id="unknown_operation",
            target="missing",
            arguments={},
        ),
    )

    assert not result.valid
    assert [error.code for error in result.errors] == ["INVALID_OPERATION"]


def test_set_value_requires_existing_target() -> None:
    result = validate_operation(
        State.empty(),
        Operation(
            operation_id="set_value",
            target="missing",
            arguments={
                "value": Value(type_name="text", data="apple"),
            },
        ),
    )

    assert not result.valid
    assert [error.code for error in result.errors] == ["NOT_FOUND"]


def test_set_value_requires_value_argument() -> None:
    state = State.empty().with_value(
        "item",
        Value(type_name="text", data="apple"),
    )

    result = validate_operation(
        state,
        Operation(
            operation_id="set_value",
            target="item",
            arguments={},
        ),
    )

    assert not result.valid
    assert [error.code for error in result.errors] == ["INVALID_VALUE"]


def test_set_value_same_value_is_a_valid_successful_execution() -> None:
    from forge_core.execution import execute

    original = State.empty().with_value(
        "item",
        Value(type_name="text", data="apple"),
    )

    result = execute(
        original,
        Operation(
            operation_id="set_value",
            target="item",
            arguments={
                "value": Value(type_name="text", data="apple"),
            },
        ),
    )

    assert result.success
    assert result.state == original
    assert result.evidence.state_before_id == result.evidence.state_after_id
    assert "state_result_observed" in result.evidence.verification_facts
