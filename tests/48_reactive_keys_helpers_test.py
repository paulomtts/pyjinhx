from pyjinhx.reactive.keys import StateKey


class TodoKeys(StateKey):
    TODOS = "todos"


def test_instance_key_formats_stem_and_key():
    assert StateKey.instance_key("todo", 42) == "todo:42"
    assert StateKey.instance_key("todo", "abc") == "todo:abc"


def test_dirty_keys_builds_two_tier_set():
    assert StateKey.dirty_keys("todo", 42, "todos") == {"todo:42", "todos"}
    assert StateKey.dirty_keys("todo", 42, TodoKeys.TODOS) == {"todo:42", "todos"}
