from examples.todo.components.item_row import ItemRow
from examples.todo.context import TodoAppContext
from examples.todo.keys import Keys
from pyjinhx import ReactiveComponent


class ItemList(ReactiveComponent, react={Keys.TODO_LIST}):
    """The list of todo rows."""

    items: list[ItemRow] = []  # noqa: RUF012 -- pydantic field, not a shared mutable default

    @classmethod
    def load(cls, ctx: TodoAppContext | None = None) -> "ItemList":
        """Build one cache-routed row per todo.

        ``ItemRow.load(todo.id)`` is load-bearing: the renderer only auto-loads
        a child it instantiates itself from a tag, never an instance assigned
        to a field, so rows built here go through the factory directly
        instead. The dom id is stamped after: it identifies the
        mounted region, not the loaded data, so it is never a load()
        parameter, and the cached instance is shared across renders of the
        same todo_id regardless of which row happens to touch it first.
        """
        rows = []
        for todo in ctx.store.all_todos():
            row = ItemRow.load(todo.id)
            row.id = f"row-{todo.id}"
            rows.append(row)
        return cls(items=rows)
