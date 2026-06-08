from typing import ClassVar

from pyjinhx import ReactiveComponent

from .store import state


class DynamicWidget(ReactiveComponent):
    reacts_to: ClassVar[set[str]] = {"alpha", "beta"}
    flag: str = "on"

    @classmethod
    def load(cls) -> "DynamicWidget":
        return cls(flag="on" if state.get("dynamic_narrow", True) else "off")

    def effective_reacts_to(self) -> set[str]:
        if self.flag == "on":
            return {"alpha"}
        return {"alpha", "beta"}
