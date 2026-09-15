from forge_core.evidence import Evidence


def test_successful_evidence_requires_after_state() -> None:
    evidence = Evidence(
        operation_id="set_value",
        validation_passed=True,
        execution_succeeded=True,
        state_before_id="before-001",
        state_after_id="after-001",
        verification_facts=("target_present",),
    )

    assert evidence.operation_id == "set_value"
    assert evidence.validation_passed
    assert evidence.execution_succeeded
    assert evidence.state_before_id == "before-001"
    assert evidence.state_after_id == "after-001"
    assert evidence.verification_facts == ("target_present",)


def test_failed_evidence_has_no_after_state() -> None:
    evidence = Evidence(
        operation_id="set_value",
        validation_passed=False,
        execution_succeeded=False,
        state_before_id="before-001",
        state_after_id=None,
        verification_facts=("target_missing",),
    )

    assert not evidence.validation_passed
    assert not evidence.execution_succeeded
    assert evidence.state_after_id is None


def test_success_without_after_state_is_rejected() -> None:
    try:
        Evidence(
            operation_id="set_value",
            validation_passed=True,
            execution_succeeded=True,
            state_before_id="before-001",
            state_after_id=None,
            verification_facts=(),
        )
    except ValueError as exc:
        assert str(exc) == "successful execution requires state_after_id"
    else:
        raise AssertionError("Invalid successful evidence was accepted")


def test_failure_with_after_state_is_rejected() -> None:
    try:
        Evidence(
            operation_id="set_value",
            validation_passed=False,
            execution_succeeded=False,
            state_before_id="before-001",
            state_after_id="after-001",
            verification_facts=(),
        )
    except ValueError as exc:
        assert str(exc) == "failed execution must not contain state_after_id"
    else:
        raise AssertionError("Invalid failed evidence was accepted")


def test_empty_operation_id_is_rejected() -> None:
    try:
        Evidence(
            operation_id="",
            validation_passed=True,
            execution_succeeded=True,
            state_before_id="before-001",
            state_after_id="after-001",
            verification_facts=(),
        )
    except ValueError as exc:
        assert str(exc) == "operation_id must not be empty"
    else:
        raise AssertionError("Empty operation_id was accepted")
