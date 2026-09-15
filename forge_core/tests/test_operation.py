from forge_core.operation import Operation
from forge_core.value import Value


def test_operation_stores_identity_target_and_arguments() -> None:
    value = Value(type_name="text", data="apple")

    operation = Operation(
        operation_id="set_value",
        target="item",
        arguments={"value": value},
    )

    assert operation.operation_id == "set_value"
    assert operation.target == "item"
    assert operation.argument("value") == value
    assert operation.has_argument("value")
    assert not operation.has_argument("missing")


def test_operation_is_immutable() -> None:
    operation = Operation(
        operation_id="set_value",
        target="item",
        arguments={
            "value": Value(type_name="text", data="apple"),
        },
    )

    try:
        operation.operation_id = "other"
    except AttributeError:
        pass
    else:
        raise AssertionError("Operation must be immutable")


def test_empty_operation_id_is_rejected() -> None:
    try:
        Operation(
            operation_id="",
            target="item",
            arguments={},
        )
    except ValueError as exc:
        assert str(exc) == "operation_id must not be empty"
    else:
        raise AssertionError("Operation must reject an empty operation_id")


def test_invalid_argument_value_is_rejected() -> None:
    try:
        Operation(
            operation_id="set_value",
            target="item",
            arguments={"value": "apple"},
        )
    except TypeError as exc:
        assert str(exc) == "operation arguments must be Value instances"
    else:
        raise AssertionError("Operation must reject non-Value arguments")
