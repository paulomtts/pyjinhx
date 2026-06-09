from typing import Annotated, ClassVar

from pyjinhx import PjxKey, ReactiveComponent

names = {"1": "Alice", "2": "Bob", "3": "Carol"}


class UserRow(ReactiveComponent):
    user_key: Annotated[str, PjxKey()]
    name: str = ""
    reacts_to: ClassVar[set[str]] = {"users"}

    @classmethod
    def load(cls, key: str) -> "UserRow":
        return cls(user_key=key, name=names[key])
