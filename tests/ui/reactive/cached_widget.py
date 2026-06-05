from typing import ClassVar

from pyjinhx import ReactiveComponent

# Module-level counter so tests can observe how many times the *real* load() ran.
load_calls = {"count": 0}


class CachedWidget(ReactiveComponent):
    value: int = 0
    depends_on: ClassVar[set[str]] = {"widgets"}

    @classmethod
    def load(cls) -> "CachedWidget":
        load_calls["count"] += 1
        return cls(id="cached-widget", value=load_calls["count"])
