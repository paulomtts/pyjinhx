from pyjinhx.keys import StateKey, dirty_keys, instance_key


class TodoKeys(StateKey):
    TODOS = "todos"
    TODO = "todo"


def test_instance_key_formats_stem_and_key():
    assert instance_key("todo", 42) == "todo:42"
    assert instance_key("todo", "abc") == "todo:abc"


def test_dirty_keys_builds_two_tier_set():
    assert dirty_keys("todo", 42, "todos") == {"todo:42", "todos"}
    assert dirty_keys("todo", 42, TodoKeys.TODOS) == {"todo:42", "todos"}


def test_state_key_subclass_values():
    assert TodoKeys.TODOS == "todos"
    assert isinstance(TodoKeys.TODOS, str)
