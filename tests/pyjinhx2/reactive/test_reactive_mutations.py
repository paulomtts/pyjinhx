from enum import Enum

import pytest

from pyjinhx2.reactive.keys import MutationKey, reactive_key
from pyjinhx2.reactive.mutations import dirty, mutates
from pyjinhx2.session import get_dirtied, request_scope


class Keys(MutationKey):
    TODOS = "todos"
    USER = "user"


class PlainEnum(Enum):
    NOPE = "nope"


def test_dirty_records_the_normalized_key():
    with request_scope():
        dirty(Keys.TODOS)
        assert get_dirtied() == {"todos"}


def test_dirty_records_a_reactive_key():
    with request_scope():
        dirty(reactive_key(Keys.TODOS, 7))
        assert get_dirtied() == {"todos:7"}


@pytest.mark.parametrize("bad", ["not-a-key", PlainEnum.NOPE, 3])
def test_dirty_rejects_non_mutation_keys(bad: object):
    with pytest.raises(TypeError, match=r"dirty\(\) only accepts MutationKey"):
        dirty(bad)  # type: ignore[arg-type]


def test_mutates_records_the_key_and_returns_the_result():
    @mutates(Keys.TODOS)
    def add_todo(title: str) -> str:
        return title.upper()

    with request_scope():
        assert add_todo("milk") == "MILK"
        assert get_dirtied() == {"todos"}


def test_mutates_with_key_records_a_per_instance_key():
    class Store:
        @mutates(Keys.TODOS, key=lambda self, todo_id: todo_id)
        def toggle(self, todo_id: int) -> None:
            pass

    with request_scope():
        Store().toggle(7)
        assert get_dirtied() == {"todos:7"}


def test_mutates_outside_a_scope_is_a_no_op():
    @mutates(Keys.TODOS)
    def add_todo() -> None:
        pass

    add_todo()
    assert get_dirtied() == set()


def test_mutates_rejects_bad_keys_at_decoration_time():
    with pytest.raises(TypeError, match=r"@mutates only accepts MutationKey"):

        @mutates("todos")  # type: ignore[arg-type]
        def add_todo() -> None:
            pass
