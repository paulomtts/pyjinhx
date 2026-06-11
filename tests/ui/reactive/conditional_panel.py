from pyjinhx import MutationKey, ReactiveComponent


class Keys(MutationKey):
    USER = "user"
    SETTINGS = "settings"


class ConditionalPanel(ReactiveComponent, react={Keys.USER, Keys.SETTINGS}):
    is_admin: bool = False
    label: str = ""

    @classmethod
    def load(cls) -> "ConditionalPanel":
        return cls(is_admin=False, label="guest")

    def depends_on(self) -> set[str]:
        if self.is_admin:
            return {"user", "settings"}
        return {"settings"}
