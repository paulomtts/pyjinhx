from pyjinhx import BaseComponent


class BrokenNote(BaseComponent):
    """A template with a syntax error on a known line."""

    text: str = ""


class StrayLookup(BaseComponent):
    """A template that fails while rendering, on a known line."""
