from typing import Optional

from pyjinhx import ReactiveComponent

from tests.reactive_test_support import Keys

from .reactive_counter import ReactiveCounter


class ReactivePanel(ReactiveComponent, react={Keys.TODOS}):
    child: Optional[ReactiveCounter] = None

    @classmethod
    def load(cls) -> "ReactivePanel":
        return cls(id="panel", child=ReactiveCounter.load())
