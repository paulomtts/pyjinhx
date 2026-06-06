from typing import ClassVar

from pyjinhx import ReactiveComponent

names = {"1": "Alice", "2": "Bob", "3": "Carol"}


class UserRow(ReactiveComponent):
    name: str = ""
    reacts_to: ClassVar[set[str]] = {"user:{key}", "users"}

    @classmethod
    def load(cls, key) -> "UserRow":
        return cls(name=names[key])
