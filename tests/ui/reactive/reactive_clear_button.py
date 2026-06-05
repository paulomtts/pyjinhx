from typing import ClassVar

from pyjinhx import ReactiveComponent

from .store import state


class ReactiveClearButton(ReactiveComponent):
    completed: int = 0
    reacts_to: ClassVar[set[str]] = {"todos"}

    @classmethod
    def load(cls) -> "ReactiveClearButton":
        return cls(id="clear-btn", completed=state["completed"])
