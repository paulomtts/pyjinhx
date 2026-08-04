from typing import Annotated

from examples.todo.context import TodoAppContext
from examples.todo.keys import Keys
from pyjinhx import PjxKey, ReactiveComponent


class ItemRow(ReactiveComponent, react={Keys.TODOS}):
    """One todo, keyed by its id so each row caches its own load result."""

    todo_id: Annotated[int, PjxKey()]
    title: str = ""
    done: bool = False

    @classmethod
    def load(cls, todo_id: int, ctx: TodoAppContext | None = None) -> "ItemRow":
        """Build this row from the store.

        A row can outlive the todo it stands for — a clear-completed deletes
        the todo while the client still shows its row — and the store's KeyError
        is how that says so. It is deliberately not caught: `LookupError` (which
        `KeyError` subclasses) out of `load()` is what tells the fan-out walk the
        region is gone, so it emits a delete swap instead of an empty row. The
        self-referencing return annotation (`-> "ItemRow"`) exercises #713's fix.
        """
        todo = ctx.store.get(todo_id)
        return cls(todo_id=todo_id, title=todo.text, done=todo.done)
