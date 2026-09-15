from forge_core.errors import CoreError
from forge_core.operation import Operation
from forge_core.state import State
from forge_core.validation import ValidationResult, validate_operation
from forge_core.value import Value


def test_validation_success_has_no_errors() -> None:
    state = State.empty().with_value(
        "item",
        Value(type_name="text", data="apple"),
    )
    operation = Operation(
        operation_id="set_value",
        target="item",
        arguments={
            "value": Value(type_name="text", data="orange"),
        },
    )

    result = validate_operation(state, operation)

    assert result.valid
    assert result.errors == ()


def test_validation_failure_contains_stable_error() -> None:
    state = State.empty()
    operation = Operation(
        operation_id="set_value",
        target="missing",
        arguments={
            "value": Value(type_name="text", data="apple"),
        },
    )

    result = validate_operation(state, operation)

    assert not result.valid
    assert len(result.errors) == 1
    assert result.errors[0].code == "NOT_FOUND"


def test_validation_result_rejects_invalid_success_shape() -> None:
    error = CoreError(
        code="NOT_FOUND",
        message="target not found",
    )

    try:
        ValidationResult(valid=True, errors=(error,))
    except ValueError as exc:
        assert str(exc) == "valid validation result cannot contain errors"
    else:
        raise AssertionError("Invalid ValidationResult shape was accepted")


def test_validation_result_rejects_empty_failure() -> None:
    try:
        ValidationResult.failure([])
    except ValueError as exc:
        assert str(exc) == "failure requires at least one error"
    else:
        raise AssertionError("Empty validation failure was accepted")


def test_unknown_error_code_is_rejected() -> None:
    try:
        CoreError(
            code="UNKNOWN",
            message="invalid",
        )
    except ValueError as exc:
        assert str(exc) == "unsupported error code: UNKNOWN"
    else:
        raise AssertionError("Unknown error code was accepted")
