from pyjinhx import BaseComponent, Slot


class EmptyState(BaseComponent):
    """What a list shows with nothing in it; the icon slot takes raw markup."""

    message: str
    icon: Slot = ""
