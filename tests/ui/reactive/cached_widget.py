from typing import ClassVar

from pyjinhx import ReactiveComponent

load_calls = {"count": 0}


class CachedWidget(ReactiveComponent):
    value: int = 0
    reacts_to: ClassVar[set[str]] = {"widgets"}

    @classmethod
    def load(cls) -> "CachedWidget":
        load_calls["count"] += 1
        return cls(id="cached-widget", value=load_calls["count"])
