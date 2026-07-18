from pyjinhx.keys import DynamicReactiveKey, MutationKey, coerce_reactive_key, reactive_key


class _Keys(MutationKey):
    MESSAGE = "chat.message"


def test_reactive_key_formats_prefix_and_arg():
    key = reactive_key(_Keys.MESSAGE, "42")
    assert key == "chat.message:42"


def test_reactive_key_returns_dynamic_reactive_key_instance():
    key = reactive_key(_Keys.MESSAGE, "42")
    assert isinstance(key, DynamicReactiveKey)
    assert isinstance(key, str)


def test_reactive_key_coerces_non_string_arg():
    key = reactive_key(_Keys.MESSAGE, 42)
    assert key == "chat.message:42"


def test_coerce_reactive_key_passes_dynamic_reactive_key_through():
    key = reactive_key(_Keys.MESSAGE, "42")
    assert coerce_reactive_key(key) == "chat.message:42"
