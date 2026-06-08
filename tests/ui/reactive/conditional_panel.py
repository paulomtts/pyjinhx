from typing import ClassVar

from pyjinhx import ReactiveComponent


class ConditionalPanel(ReactiveComponent):
    reacts_to: ClassVar[set[str]] = {"user", "settings"}
    is_admin: bool = False
    label: str = ""

    @classmethod
    def load(cls) -> "ConditionalPanel":
        return cls(is_admin=False, label="guest")

    def depends_on(self) -> set[str]:
        if self.is_admin:
            return {"user", "settings"}
        return {"settings"}
