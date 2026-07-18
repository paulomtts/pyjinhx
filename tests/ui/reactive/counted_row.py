from typing import Annotated, ClassVar

from pyjinhx import MutationKey, PjxKey, ReactiveComponent


class Keys(MutationKey):
    ROW = "row"


class CountedRow(ReactiveComponent, react={Keys.ROW}):
    load_calls: ClassVar[list[str]] = []

    row_key: Annotated[str, PjxKey()]
    label: str = ""

    @classmethod
    def load(cls, key: str) -> "CountedRow":
        cls.load_calls.append(key)
        return cls(id=f"row-{key}", row_key=key, label=f"Row {key}")
