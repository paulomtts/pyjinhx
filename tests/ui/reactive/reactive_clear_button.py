from pyjinhx import ReactiveComponent

from tests.reactive_test_support import Keys

from .store import state


class ReactiveClearButton(ReactiveComponent, react={Keys.TODOS}):
    completed: int = 0

    @classmethod
    def load(cls) -> "ReactiveClearButton":
        return cls(id="clear-btn", completed=state["completed"])
