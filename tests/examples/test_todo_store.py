"""The todo example's in-memory store: reads, mutations, and dirtied keys."""

import pytest

from examples.todo import store
from examples.todo.keys import Keys
from pyjinhx.session import get_dirtied, request_scope


@pytest.fixture(autouse=True)
def fresh_store():
    store.reset()
    yield
    store.reset()


def test_reset_seeds_the_demo_todos():
    assert [t.text for t in store.all_todos()] == [
        "Write the docs",
        "Ship reactivity",
        "Touch grass",
    ]
    assert all(not t.done for t in store.all_todos())


def test_add_creates_a_todo_with_a_fresh_id():
    before = store.total()
    todo = store.add("Feed the cat")
    assert todo.text == "Feed the cat"
    assert todo.done is False
    assert store.total() == before + 1
    assert store.get(todo.id) is todo


def test_add_gives_every_todo_a_unique_id():
    ids = [store.add(f"task {n}").id for n in range(5)]
    assert len(set(ids)) == 5
    assert len({t.id for t in store.all_todos()}) == store.total()


def test_all_todos_returns_insertion_order():
    store.add("last")
    assert store.all_todos()[-1].text == "last"


def test_toggle_flips_done_both_ways():
    todo = store.add("Feed the cat")
    assert store.toggle(todo.id).done is True
    assert store.toggle(todo.id).done is False


def test_toggle_raises_on_an_unknown_id():
    with pytest.raises(KeyError):
        store.toggle(9999)


def test_get_raises_on_an_unknown_id():
    with pytest.raises(KeyError):
        store.get(9999)


def test_clear_completed_removes_only_done_todos():
    kept = store.add("keep me")
    gone = store.add("drop me")
    store.toggle(gone.id)
    store.clear_completed()
    texts = [t.text for t in store.all_todos()]
    assert "drop me" not in texts
    assert "keep me" in texts
    assert store.get(kept.id) is kept


def test_counts_track_a_sequence_of_operations():
    store.reset()
    assert (store.total(), store.remaining(), store.completed()) == (3, 3, 0)
    first = store.all_todos()[0]
    store.toggle(first.id)
    assert (store.total(), store.remaining(), store.completed()) == (3, 2, 1)
    store.add("fourth")
    assert (store.total(), store.remaining(), store.completed()) == (4, 3, 1)
    store.clear_completed()
    assert (store.total(), store.remaining(), store.completed()) == (3, 3, 0)


def test_add_dirties_todos():
    with request_scope():
        store.add("Feed the cat")
        assert get_dirtied() == {Keys.TODOS.value}


def test_toggle_dirties_todos():
    todo = store.add("Feed the cat")
    with request_scope():
        store.toggle(todo.id)
        assert get_dirtied() == {Keys.TODOS.value}


def test_clear_completed_dirties_todos_and_the_list():
    with request_scope():
        store.clear_completed()
        assert get_dirtied() == {Keys.TODOS.value, Keys.TODO_LIST.value}


def test_reads_do_not_dirty_anything():
    with request_scope():
        store.all_todos()
        store.total()
        store.remaining()
        store.completed()
        assert get_dirtied() == set()
