"""The todo example's components: what each load() puts on its instance."""

import pytest

from examples.todo import store as todo_store
from examples.todo.components import (
    ClearButton,
    Counter,
    ItemList,
    ItemRow,
    Total,
)
from examples.todo.keys import Keys


class TestItemRow:
    def test_load_populates_title_and_done_from_the_store(self, scope):
        todo = todo_store.all_todos()[0]

        row = ItemRow.load(todo.id)

        assert row.title == todo.text
        assert row.done is False

    def test_load_reflects_a_toggled_todo(self, scope):
        todo = todo_store.all_todos()[0]
        todo_store.toggle(todo.id)

        row = ItemRow.load(todo.id)

        assert row.done is True

    def test_load_on_a_missing_todo_raises_so_the_row_is_deleted(self, scope):
        """A row can outlive its todo; the store's KeyError is how it says so.

        `KeyError` subclasses `LookupError`, which is what the fan-out walk
        turns into a delete swap — so letting it out is what removes the stale
        row from the client instead of swapping in a blank one.
        """
        with pytest.raises(LookupError):
            ItemRow.load(9999)

    def test_todo_id_is_the_load_key_field(self):
        assert ItemRow._pjx_key_field == "todo_id"

    def test_reacts_to_the_todos_key(self):
        assert ItemRow._pjx_react_keys == (Keys.TODOS.value,)


class TestCounter:
    def test_load_sets_remaining_from_the_store(self, scope):
        assert Counter.load().remaining == 3

    def test_load_drops_a_toggled_todo_from_remaining(self, scope):
        todo_store.toggle(todo_store.all_todos()[0].id)

        assert Counter.load().remaining == 2

    def test_zero_state(self, scope):
        for todo in list(todo_store.all_todos()):
            todo_store.toggle(todo.id)
        todo_store.clear_completed()

        assert Counter.load().remaining == 0


class TestTotal:
    def test_load_sets_count_from_the_store(self, scope):
        assert Total.load().count == 3

    def test_zero_state(self, scope):
        for todo in list(todo_store.all_todos()):
            todo_store.toggle(todo.id)
        todo_store.clear_completed()

        assert Total.load().count == 0


class TestClearButton:
    def test_load_counts_completed_todos(self, scope):
        todo_store.toggle(todo_store.all_todos()[0].id)

        assert ClearButton.load().completed == 1

    def test_zero_state_with_nothing_completed(self, scope):
        assert ClearButton.load().completed == 0


class TestItemList:
    def test_load_builds_one_row_per_todo(self, scope):
        item_list = ItemList.load()

        assert [row.todo_id for row in item_list.items] == [
            todo.id for todo in todo_store.all_todos()
        ]

    def test_every_row_comes_back_already_loaded(self, scope):
        # The regression: ItemList.load() has to route each row through
        # ItemRow.load() itself, not just construct plain instances - forget
        # that and every row renders with its field defaults.
        item_list = ItemList.load()

        assert [row.title for row in item_list.items] == [
            "Write the docs",
            "Ship reactivity",
            "Touch grass",
        ]
        assert all(row.title != "" for row in item_list.items)

    def test_row_done_state_survives_into_the_list(self, scope):
        todo_store.toggle(todo_store.all_todos()[1].id)

        item_list = ItemList.load()

        assert [row.done for row in item_list.items] == [False, True, False]

    def test_each_row_carries_a_stable_dom_id(self, scope):
        item_list = ItemList.load()

        assert [row.id for row in item_list.items] == [
            f"row-{todo.id}" for todo in todo_store.all_todos()
        ]

    def test_empty_list_is_a_zero_state_not_an_error(self, scope):
        for todo in list(todo_store.all_todos()):
            todo_store.toggle(todo.id)
        todo_store.clear_completed()

        assert ItemList.load().items == []

    def test_reacts_to_the_todo_list_key(self):
        assert ItemList._pjx_react_keys == (Keys.TODO_LIST.value,)
