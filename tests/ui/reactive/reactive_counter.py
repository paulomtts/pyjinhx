from typing import ClassVar

from pyjinhx import ReactiveComponent

from .store import state


class ReactiveCounter(ReactiveComponent):
    remaining: int = 0
    depends_on: ClassVar[set[str]] = {"todos"}

    @classmethod
    def load(cls) -> "ReactiveCounter":
        return cls(id="counter", remaining=state["remaining"])
