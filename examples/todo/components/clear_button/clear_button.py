from examples.todo.context import TodoAppContext
from examples.todo.keys import Keys
from pyjinhx import ReactiveComponent


class ClearButton(ReactiveComponent, react={Keys.TODOS}):
    """The clear-completed action, disabled while nothing is completed."""

    completed: int = 0

    @classmethod
    def load(cls, ctx: TodoAppContext | None = None) -> "ClearButton":
        """Read the completed-todo count from the store."""
        return cls(completed=ctx.store.completed())
