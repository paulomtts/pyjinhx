"""The todo example's components: what each load() puts on its instance."""

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
        row = ItemRow(id=f"row-{todo.id}", todo_id=todo.id)

        row.load()

        assert row.title == todo.text
        assert row.done is False

    def test_load_reflects_a_toggled_todo(self, scope):
        todo = todo_store.all_todos()[0]
        todo_store.toggle(todo.id)
        row = ItemRow(id=f"row-{todo.id}", todo_id=todo.id)

        row.load()

        assert row.done is True

    def test_load_on_a_missing_todo_leaves_the_defaults(self, scope):
        row = ItemRow(id="row-9999", todo_id=9999)

        row.load()

        assert row.title == ""
        assert row.done is False

    def test_todo_id_is_the_load_key_field(self):
        assert ItemRow._pjx_key_field == "todo_id"

    def test_reacts_to_the_todos_key(self):
        assert ItemRow._pjx_react_keys == (Keys.TODOS.value,)


class TestCounter:
    def test_load_sets_remaining_from_the_store(self, scope):
        counter = Counter(id="counter")

        counter.load()

        assert counter.remaining == 3

    def test_load_drops_a_toggled_todo_from_remaining(self, scope):
        todo_store.toggle(todo_store.all_todos()[0].id)
        counter = Counter(id="counter")

        counter.load()

        assert counter.remaining == 2

    def test_zero_state(self, scope):
        for todo in list(todo_store.all_todos()):
            todo_store.toggle(todo.id)
        todo_store.clear_completed()
        counter = Counter(id="counter")

        counter.load()

        assert counter.remaining == 0


class TestTotal:
    def test_load_sets_count_from_the_store(self, scope):
        total = Total(id="total")

        total.load()

        assert total.count == 3

    def test_zero_state(self, scope):
        for todo in list(todo_store.all_todos()):
            todo_store.toggle(todo.id)
        todo_store.clear_completed()
        total = Total(id="total")

        total.load()

        assert total.count == 0


class TestClearButton:
    def test_load_counts_completed_todos(self, scope):
        todo_store.toggle(todo_store.all_todos()[0].id)
        button = ClearButton(id="clear")

        button.load()

        assert button.completed == 1

    def test_zero_state_with_nothing_completed(self, scope):
        button = ClearButton(id="clear")

        button.load()

        assert button.completed == 0


class TestItemList:
    def test_load_builds_one_row_per_todo(self, scope):
        item_list = ItemList(id="list")

        item_list.load()

        assert [row.todo_id for row in item_list.items] == [
            todo.id for todo in todo_store.all_todos()
        ]

    def test_every_row_comes_back_already_loaded(self, scope):
        # The regression: assigning ItemRow instances to a field does NOT fire
        # pjx_mount(), so ItemList.load() has to call each row's load() itself.
        # Forget that and every row renders with its field defaults.
        item_list = ItemList(id="list")

        item_list.load()

        assert [row.title for row in item_list.items] == [
            "Write the docs",
            "Ship reactivity",
            "Touch grass",
        ]
        assert all(row.title != "" for row in item_list.items)

    def test_row_done_state_survives_into_the_list(self, scope):
        todo_store.toggle(todo_store.all_todos()[1].id)
        item_list = ItemList(id="list")

        item_list.load()

        assert [row.done for row in item_list.items] == [False, True, False]

    def test_each_row_carries_a_stable_dom_id(self, scope):
        item_list = ItemList(id="list")

        item_list.load()

        assert [row.id for row in item_list.items] == [
            f"row-{todo.id}" for todo in todo_store.all_todos()
        ]

    def test_empty_list_is_a_zero_state_not_an_error(self, scope):
        for todo in list(todo_store.all_todos()):
            todo_store.toggle(todo.id)
        todo_store.clear_completed()
        item_list = ItemList(id="list")

        item_list.load()

        assert item_list.items == []

    def test_reacts_to_the_todo_list_key(self):
        assert ItemList._pjx_react_keys == (Keys.TODO_LIST.value,)
