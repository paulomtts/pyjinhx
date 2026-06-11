from pyjinhx import MutationKey, ReactiveComponent

load_calls = {"count": 0}


class Keys(MutationKey):
    WIDGETS = "widgets"


class CachedWidget(ReactiveComponent, react={Keys.WIDGETS}):
    value: int = 0

    @classmethod
    def load(cls) -> "CachedWidget":
        load_calls["count"] += 1
        return cls(id="cached-widget", value=load_calls["count"])
