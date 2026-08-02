from enum import Enum

import pytest

from pyjinhx2.reactive.keys import MutationKey, reactive_key
from pyjinhx2.reactive.mutations import dirty, mutates
from pyjinhx2.session import add_dirtied, get_dirtied, request_scope


class Keys(MutationKey):
    TODOS = "todos"
    USER = "user"


class PlainEnum(Enum):
    NOPE = "nope"


def test_dirty_records_the_normalized_key():
    with request_scope():
        dirty(Keys.TODOS)
        assert get_dirtied() == {"todos"}


def test_dirty_records_several_keys_at_once():
    with request_scope():
        dirty(Keys.TODOS, Keys.USER)
        assert get_dirtied() == {"todos", "user"}


def test_dirty_records_a_reactive_key():
    with request_scope():
        dirty(reactive_key(Keys.TODOS, 7))
        assert get_dirtied() == {"todos:7"}


def test_mutates_records_the_key_and_returns_the_result():
    @mutates(Keys.TODOS)
    def add_todo(title: str) -> str:
        return title.upper()

    with request_scope():
        assert add_todo("milk") == "MILK"
        assert get_dirtied() == {"todos"}


def test_mutates_keeps_the_wrapped_functions_identity():
    @mutates(Keys.TODOS)
    def add_todo() -> None:
        """Add a todo."""

    assert add_todo.__name__ == "add_todo"
    assert add_todo.__doc__ == "Add a todo."


def test_mutates_records_every_key_it_was_given():
    @mutates(Keys.TODOS, Keys.USER)
    def rename_user() -> None:
        pass

    with request_scope():
        rename_user()
        assert get_dirtied() == {"todos", "user"}


def test_mutates_dirties_only_after_the_function_returns():
    seen: list[set[str]] = []

    @mutates(Keys.TODOS)
    def add_todo() -> None:
        seen.append(get_dirtied().copy())

    with request_scope():
        add_todo()

    assert seen == [set()]


def test_mutates_accepts_a_reactive_key():
    @mutates(reactive_key(Keys.TODOS, 7))  # type: ignore[arg-type]
    def toggle() -> None:
        pass

    with request_scope():
        toggle()
        assert get_dirtied() == {"todos:7"}


def test_mutates_with_key_records_a_per_instance_key():
    class Store:
        @mutates(Keys.TODOS, key=lambda self, todo_id: todo_id)
        def toggle(self, todo_id: int) -> None:
            pass

    with request_scope():
        Store().toggle(7)
        assert get_dirtied() == {"todos:7"}


def test_mutates_with_key_records_one_key_per_distinct_arg():
    class Store:
        @mutates(Keys.TODOS, key=lambda self, todo_id: todo_id)
        def toggle(self, todo_id: int) -> None:
            pass

    with request_scope():
        store = Store()
        store.toggle(7)
        store.toggle(8)
        assert get_dirtied() == {"todos:7", "todos:8"}


def test_repeated_dirtying_of_one_key_collapses():
    with request_scope():
        dirty(Keys.TODOS)
        dirty(Keys.TODOS)
        assert get_dirtied() == {"todos"}


def test_dirty_and_mutates_accumulate_across_calls_in_one_scope():
    @mutates(Keys.USER)
    def rename_user() -> None:
        pass

    with request_scope():
        dirty(Keys.TODOS)
        rename_user()
        dirty(reactive_key(Keys.TODOS, 7))
        assert get_dirtied() == {"todos", "user", "todos:7"}


def test_dirty_with_no_keys_leaves_the_dirtied_set_untouched():
    with request_scope():
        dirty(Keys.TODOS)
        dirty()
        assert get_dirtied() == {"todos"}


def test_get_dirtied_outside_a_scope_is_empty():
    assert get_dirtied() == set()


def test_dirty_outside_a_scope_is_a_no_op():
    dirty(Keys.TODOS)
    with request_scope():
        assert get_dirtied() == set()


def test_add_dirtied_outside_a_scope_is_a_no_op():
    add_dirtied({"todos"})
    with request_scope():
        assert get_dirtied() == set()


def test_mutates_outside_a_scope_is_a_no_op():
    @mutates(Keys.TODOS)
    def add_todo() -> None:
        pass

    add_todo()
    assert get_dirtied() == set()


def test_sequential_scopes_do_not_share_dirtied_keys():
    with request_scope():
        dirty(Keys.TODOS)
        assert get_dirtied() == {"todos"}

    with request_scope():
        assert get_dirtied() == set()


def test_a_nested_scope_hands_the_outer_scope_its_own_state_back():
    with request_scope():
        dirty(Keys.TODOS)

        with request_scope():
            assert get_dirtied() == set()
            dirty(Keys.USER)
            assert get_dirtied() == {"user"}

        assert get_dirtied() == {"todos"}


@pytest.mark.parametrize("bad", ["not-a-key", PlainEnum.NOPE, 3, None])
def test_dirty_rejects_non_mutation_keys(bad: object):
    with pytest.raises(TypeError, match=r"dirty\(\) only accepts MutationKey"):
        dirty(bad)  # type: ignore[arg-type]


@pytest.mark.parametrize("bad", ["not-a-key", PlainEnum.NOPE, 3, None])
def test_mutates_rejects_bad_keys_at_decoration_time(bad: object):
    with pytest.raises(TypeError, match=r"@mutates only accepts MutationKey"):
        mutates(bad)  # type: ignore[arg-type]


def test_mutates_rejects_a_bad_key_when_the_decorator_is_applied():
    with pytest.raises(TypeError, match=r"@mutates only accepts MutationKey"):

        @mutates("todos")  # type: ignore[arg-type]
        def add_todo() -> None:
            pass
