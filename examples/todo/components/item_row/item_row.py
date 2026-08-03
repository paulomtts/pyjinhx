from typing import Annotated

from examples.todo.context import TodoAppContext
from examples.todo.keys import Keys
from pyjinhx import PjxKey, ReactiveComponent


class ItemRow(ReactiveComponent, react={Keys.TODOS}):
    """One todo, keyed by its id so each row caches its own load result."""

    todo_id: Annotated[int, PjxKey()]
    title: str = ""
    done: bool = False

    # No return annotation: a `-> None` here trips bug #713.
    def load(self, ctx: TodoAppContext):
        """Read this row's todo from the store.

        A todo_id that is not in the store leaves the fields at their defaults
        rather than raising: a row can outlive the todo it stands for (a
        clear-completed that landed between render and swap), and a demo page
        should render an empty row instead of a 500.
        """
        try:
            todo = ctx.store.get(self.todo_id)
        except KeyError:
            return
        self.title = todo.text
        self.done = todo.done
