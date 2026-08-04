from typing import Any

from pydantic import Field

from pyjinhx._component import AttrValue, BaseComponent, Slot


class PJXEmptyState(BaseComponent):
    """An empty-state panel with slot content and optional suggestion chips."""

    # Each chip is a dict: label (str, button text), value (str, optional,
    # dispatched with the event; defaults to label), event (str, optional,
    # custom event name; defaults to "pjx:suggestion").
    suggestions: list[Any] = Field(default_factory=list)
    class_name: AttrValue = ""
    content: Slot = ""
