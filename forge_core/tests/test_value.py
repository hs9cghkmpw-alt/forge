from forge_core.value import Value
import pytest


def test_value_equality_and_type_check() -> None:
    first = Value(type_name="text", data="apple")
    second = Value(type_name="text", data="apple")

    assert first == second
    assert first.is_type("text")
    assert not first.is_type("number")


def test_value_rejects_empty_type_name() -> None:
    with pytest.raises(ValueError):
        Value(type_name="", data="apple")


def test_value_accepts_deterministic_collection_data() -> None:
    value = Value(
        type_name="record",
        data={
            "name": "apple",
            "tags": ["fruit", "food"],
            "metadata": {"count": 1},
        },
    )

    assert value.canonical() == (
        "dict",
        (
            ("metadata", ("dict", (("count", ("int", 1)),))),
            ("name", ("str", "apple")),
            (
                "tags",
                ("list", (("str", "fruit"), ("str", "food"))),
            ),
        ),
    )


def test_value_rejects_non_deterministic_set() -> None:
    with pytest.raises(TypeError):
        Value(type_name="set", data={"apple", "orange"})


def test_value_rejects_non_finite_float() -> None:
    with pytest.raises(ValueError):
        Value(type_name="number", data=float("nan"))


def test_value_distinguishes_list_and_tuple() -> None:
    list_value = Value(type_name="data", data=["apple"])
    tuple_value = Value(type_name="data", data=("apple",))

    assert list_value.canonical() != tuple_value.canonical()


def test_value_is_deeply_immutable() -> None:
    original = {
        "name": "apple",
        "metadata": {
            "count": 1,
        },
        "tags": [
            "fruit",
            "food",
        ],
    }

    value = Value(
        type_name="record",
        data=original,
    )

    original["name"] = "orange"
    original["metadata"]["count"] = 999
    original["tags"].append("new")

    assert value.canonical() == (
        "dict",
        (
            ("metadata", ("dict", (("count", ("int", 1)),))),
            ("name", ("str", "apple")),
            (
                "tags",
                ("list", (("str", "fruit"), ("str", "food"))),
            ),
        ),
    )


def test_value_nested_data_cannot_be_mutated() -> None:
    value = Value(
        type_name="record",
        data={
            "metadata": {
                "count": 1,
            },
            "tags": [
                "fruit",
            ],
        },
    )

    with pytest.raises(TypeError):
        value.data[0] = ("metadata", ("dict", (("count", 2),)))

    assert value.canonical() == (
        "dict",
        (
            ("metadata", ("dict", (("count", ("int", 1)),))),
            ("tags", ("list", (("str", "fruit"),))),
        ),
    )
