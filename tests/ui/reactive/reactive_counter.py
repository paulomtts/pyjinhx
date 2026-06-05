from typing import ClassVar

from pyjinhx import BaseComponent

from .store import state


class ReactiveCounter(BaseComponent):
    remaining: int = 0
    depends_on: ClassVar[set[str]] = {"todos"}

    @classmethod
    def load(cls) -> "ReactiveCounter":
        return cls(id="counter", remaining=state["remaining"])
