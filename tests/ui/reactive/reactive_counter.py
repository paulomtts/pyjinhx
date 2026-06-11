from pyjinhx import ReactiveComponent

from tests.reactive_test_support import Keys

from .store import state


class ReactiveCounter(ReactiveComponent, react={Keys.TODOS}):
    remaining: int = 0

    @classmethod
    def load(cls) -> "ReactiveCounter":
        return cls(id="counter", remaining=state["remaining"])
