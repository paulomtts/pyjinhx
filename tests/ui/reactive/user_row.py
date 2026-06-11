from typing import Annotated

from pyjinhx import MutationKey, PjxKey, ReactiveComponent

names = {"1": "Alice", "2": "Bob", "3": "Carol"}


class Keys(MutationKey):
    USERS = "users"


class UserRow(ReactiveComponent, react={Keys.USERS}):
    user_key: Annotated[str, PjxKey()]
    name: str = ""

    @classmethod
    def load(cls, key: str) -> "UserRow":
        return cls(user_key=key, name=names[key])
