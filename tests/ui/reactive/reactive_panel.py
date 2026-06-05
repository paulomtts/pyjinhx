from typing import ClassVar, Optional

from pyjinhx import BaseComponent

from .reactive_counter import ReactiveCounter


class ReactivePanel(BaseComponent):
    child: Optional[ReactiveCounter] = None
    depends_on: ClassVar[set[str]] = {"todos"}

    @classmethod
    def load(cls) -> "ReactivePanel":
        return cls(id="panel", child=ReactiveCounter.load())
