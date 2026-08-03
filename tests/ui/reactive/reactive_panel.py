from pyjinhx_v0 import ReactiveComponent
from tests.reactive_test_support import Keys

from .reactive_counter import ReactiveCounter


class ReactivePanel(ReactiveComponent, react={Keys.TODOS}):
    child: ReactiveCounter | None = None

    @classmethod
    def load(cls) -> "ReactivePanel":
        return cls(id="panel", child=ReactiveCounter.load())
