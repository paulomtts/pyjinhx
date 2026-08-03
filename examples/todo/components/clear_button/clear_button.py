from examples.todo.context import TodoAppContext
from examples.todo.keys import Keys
from pyjinhx import ReactiveComponent


class ClearButton(ReactiveComponent, react={Keys.TODOS}):
    """The clear-completed action, disabled while nothing is completed."""

    completed: int = 0

    def load(self, ctx: TodoAppContext):
        """Read the completed-todo count from the store."""
        self.completed = ctx.store.completed()
