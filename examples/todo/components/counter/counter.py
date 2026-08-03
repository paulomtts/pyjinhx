from examples.todo.context import TodoAppContext
from examples.todo.keys import Keys
from pyjinhx import ReactiveComponent


class Counter(ReactiveComponent, react={Keys.TODOS}):
    """How many todos are still open."""

    remaining: int = 0

    def load(self, ctx: TodoAppContext):
        """Read the open-todo count from the store."""
        self.remaining = ctx.store.remaining()
