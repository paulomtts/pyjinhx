from pyjinhx import MutationKey, ReactiveComponent

from .store import state


class Keys(MutationKey):
    ALPHA = "alpha"
    BETA = "beta"


class DynamicWidget(ReactiveComponent, react={Keys.ALPHA, Keys.BETA}):
    flag: str = "on"

    @classmethod
    def load(cls) -> "DynamicWidget":
        return cls(flag="on" if state.get("dynamic_narrow", True) else "off")

    def depends_on(self) -> set[str]:
        if self.flag == "on":
            return {"alpha"}
        return {"alpha", "beta"}
