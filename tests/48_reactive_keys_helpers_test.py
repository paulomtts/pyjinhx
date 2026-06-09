from pyjinhx.reactive.keys import StateKey, coerce_reactive_key, coerce_reactive_keys


class TodoKeys(StateKey):
    TODOS = "todos"


def test_state_key_enum_values_are_strings():
    assert TodoKeys.TODOS == "todos"
    assert coerce_reactive_key(TodoKeys.TODOS) == "todos"


def test_coerce_reactive_keys_accepts_enums():
    assert coerce_reactive_keys({TodoKeys.TODOS, "users"}) == {"todos", "users"}
