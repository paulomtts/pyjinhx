from examples.todo.context import TodoAppContext
from examples.todo.keys import Keys
from pyjinhx import ReactiveComponent


class Counter(ReactiveComponent, react={Keys.TODOS}):
    """How many todos are still open."""

    remaining: int = 0

    @classmethod
    def load(cls, ctx: TodoAppContext) -> "Counter":
        """Read the open-todo count from the store."""
        return cls(remaining=ctx.store.remaining())
