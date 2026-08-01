from enum import Enum

import pytest

from pyjinhx2.reactive.keys import (
    DynamicReactiveKey,
    MutationKey,
    coerce_reactive_key,
    coerce_reactive_keys,
    reactive_key,
)


class Keys(MutationKey):
    TODOS = "todos"
    USER = "user"


class PlainEnum(Enum):
    COLOR = "color"


def test_coerce_reactive_key_passes_a_plain_string_through():
    assert coerce_reactive_key("todos") == "todos"


def test_coerce_reactive_key_unwraps_a_mutation_key_to_its_value():
    assert coerce_reactive_key(Keys.TODOS) == "todos"


def test_coerce_reactive_key_unwraps_a_plain_enum_to_its_value():
    assert coerce_reactive_key(PlainEnum.COLOR) == "color"


def test_coerce_reactive_key_stringifies_other_objects():
    assert coerce_reactive_key(7) == "7"


def test_coerce_reactive_keys_normalizes_a_mixed_iterable_to_strings():
    assert coerce_reactive_keys([Keys.TODOS, "user", PlainEnum.COLOR]) == {
        "todos",
        "user",
        "color",
    }


@pytest.mark.parametrize("empty", [None, [], set(), ()])
def test_coerce_reactive_keys_returns_an_empty_set_for_empty_input(empty: object):
    assert coerce_reactive_keys(empty) == set()  # type: ignore[arg-type]


def test_mutation_key_members_are_strings_equal_to_their_value():
    assert Keys.TODOS == "todos"
    assert isinstance(Keys.TODOS, str)


def test_mutation_key_members_work_as_dict_keys_and_set_members():
    assert {Keys.TODOS: 1}["todos"] == 1  # type: ignore[index]
    assert "todos" in {Keys.TODOS}


def test_reactive_key_joins_the_key_value_and_the_arg():
    key = reactive_key(Keys.TODOS, 7)
    assert key == "todos:7"
    assert isinstance(key, DynamicReactiveKey)
    assert isinstance(key, str)


def test_reactive_key_distinguishes_args_for_the_same_key():
    assert reactive_key(Keys.TODOS, 7) != reactive_key(Keys.TODOS, 8)


def test_reactive_key_distinguishes_keys_for_the_same_arg():
    assert reactive_key(Keys.TODOS, 7) != reactive_key(Keys.USER, 7)


def test_coerce_load_key_str_passes_none_through():
    from pyjinhx2.reactive.keys import coerce_load_key_str

    assert coerce_load_key_str(None) is None


def test_coerce_load_key_str_stringifies_scalars_and_enums():
    from enum import Enum

    from pyjinhx2.reactive.keys import coerce_load_key_str

    class Color(Enum):
        RED = "red"

    assert coerce_load_key_str(7) == "7"
    assert coerce_load_key_str("7") == "7"
    assert coerce_load_key_str(Color.RED) == "red"
