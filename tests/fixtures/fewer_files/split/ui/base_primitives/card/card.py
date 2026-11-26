from pyjinhx import BaseComponent, Children, Slot


class Card(BaseComponent):
    """A titled box: an optional header slot over a body of child markup."""

    title: str
    header: Slot | None = None
    body: Children = ""
