from examples.todo.components.item_row import ItemRow
from examples.todo.context import TodoAppContext
from examples.todo.keys import Keys
from pyjinhx import ReactiveComponent


class ItemList(ReactiveComponent, react={Keys.TODO_LIST}):
    """The list of todo rows."""

    items: list[ItemRow] = []  # noqa: RUF012 -- pydantic field, not a shared mutable default

    def load(self, ctx: TodoAppContext):
        """Build one row per todo and load each one before keeping it.

        The explicit row.load() is load-bearing: pjx_mount() only fires for
        children the renderer instantiates from a tag, never for instances
        assigned to a field, so rows built here would otherwise render with
        their defaults. It takes no argument — the load wrap injects the
        request's app context.
        """
        rows = []
        for todo in ctx.store.all_todos():
            row = ItemRow(id=f"row-{todo.id}", todo_id=todo.id)
            row.load()
            rows.append(row)
        self.items = rows
