from forge_core.execution import ExecutionResult, execute
from forge_core.operation import Operation
from forge_core.state import State
from forge_core.value import Value


def test_set_value_execution_produces_evidence() -> None:
    original = State.empty().with_value(
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

    result = execute(original, operation)

    assert result.success
    assert result.evidence.operation_id == "set_value"
    assert result.evidence.validation_passed
    assert result.evidence.execution_succeeded
    assert result.evidence.state_before_id == original.identity()
    assert result.evidence.state_after_id == result.state.identity()
    assert result.evidence.state_before_id != result.evidence.state_after_id


def test_failed_execution_records_unchanged_state_evidence() -> None:
    original = State.empty()

    operation = Operation(
        operation_id="set_value",
        target="missing",
        arguments={
            "value": Value(type_name="text", data="apple"),
        },
    )

    result = execute(original, operation)

    assert not result.success
    assert result.state == original
    assert result.evidence.operation_id == "set_value"
    assert not result.evidence.validation_passed
    assert not result.evidence.execution_succeeded
    assert result.evidence.state_before_id == original.identity()
    assert result.evidence.state_after_id is None
    assert "state_unchanged_on_failure" in result.evidence.verification_facts


def test_same_state_has_same_identity() -> None:
    first = State.empty().with_value(
        "item",
        Value(type_name="text", data="apple"),
    )
    second = State.empty().with_value(
        "item",
        Value(type_name="text", data="apple"),
    )

    assert first.identity() == second.identity()


def test_different_state_has_different_identity() -> None:
    first = State.empty().with_value(
        "item",
        Value(type_name="text", data="apple"),
    )
    second = State.empty().with_value(
        "item",
        Value(type_name="text", data="orange"),
    )

    assert first.identity() != second.identity()


def test_execution_result_requires_matching_evidence() -> None:
    from forge_core.evidence import Evidence

    state = State.empty()
    evidence = Evidence(
        operation_id="set_value",
        validation_passed=True,
        execution_succeeded=False,
        state_before_id=state.identity(),
        state_after_id=None,
        verification_facts=(),
    )

    try:
        ExecutionResult(
            success=True,
            state=state,
            errors=(),
            evidence=evidence,
        )
    except ValueError as exc:
        assert str(exc) == "execution result and evidence must agree"
    else:
        raise AssertionError("Mismatched execution evidence was accepted")
