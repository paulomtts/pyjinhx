from typing import ClassVar

from pyjinhx import BaseComponent

from .store import state


class ReactiveClearButton(BaseComponent):
    completed: int = 0
    depends_on: ClassVar[set[str]] = {"todos"}

    @classmethod
    def load(cls) -> "ReactiveClearButton":
        return cls(id="clear-btn", completed=state["completed"])
