from examples.todo.context import TodoAppContext
from examples.todo.keys import Keys
from pyjinhx import ReactiveComponent


class Total(ReactiveComponent, react={Keys.TODOS}):
    """How many todos exist in total."""

    count: int = 0

    def load(self, ctx: TodoAppContext):
        """Read the total todo count from the store."""
        self.count = ctx.store.total()
