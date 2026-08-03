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
    def load(cls, todo_id: int, ctx: TodoAppContext) -> "ItemRow":
        """Build this row from the store.

        A todo_id that is not in the store returns a field-default row rather
        than raising: a row can outlive the todo it stands for (a
        clear-completed that landed between render and swap), and a demo page
        should render an empty row instead of a 500. The self-referencing
        return annotation (`-> "ItemRow"`) exercises #713's fix.
        """
        try:
            todo = ctx.store.get(todo_id)
        except KeyError:
            return cls(todo_id=todo_id)
        return cls(todo_id=todo_id, title=todo.text, done=todo.done)
