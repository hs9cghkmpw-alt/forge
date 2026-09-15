from forge_core.state import State
from forge_core.value import Value


def test_empty_state_has_no_values() -> None:
    state = State.empty()

    assert not state.values


def test_state_is_immutable_by_update() -> None:
    original = State.empty()
    updated = original.with_value(
        "item",
        Value(type_name="text", data="apple"),
    )

    assert not original.contains("item")
    assert updated.contains("item")
    assert updated.get("item") == Value(type_name="text", data="apple")


def test_state_replaces_existing_value() -> None:
    original = State.empty().with_value(
        "item",
        Value(type_name="text", data="apple"),
    )

    updated = original.with_value(
        "item",
        Value(type_name="text", data="orange"),
    )

    assert updated.get("item") == Value(type_name="text", data="orange")


def test_state_removes_value() -> None:
    original = State.empty().with_value(
        "item",
        Value(type_name="text", data="apple"),
    )

    updated = original.without("item")

    assert original.contains("item")
    assert not updated.contains("item")


def test_state_identity_is_independent_of_mapping_insertion_order() -> None:
    first = State(
        values={
            "a": Value(type_name="text", data="apple"),
            "b": Value(type_name="text", data="banana"),
        }
    )

    second = State(
        values={
            "b": Value(type_name="text", data="banana"),
            "a": Value(type_name="text", data="apple"),
        }
    )

    assert first.identity() == second.identity()


def test_state_identity_changes_when_nested_data_changes() -> None:
    first = State.empty().with_value(
        "item",
        Value(
            type_name="record",
            data={"name": "apple", "count": 1},
        ),
    )

    second = State.empty().with_value(
        "item",
        Value(
            type_name="record",
            data={"name": "apple", "count": 2},
        ),
    )

    assert first.identity() != second.identity()
