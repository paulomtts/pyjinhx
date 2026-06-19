from typing import Annotated, Any

from pydantic import Field

from pyjinhx import BaseComponent, Slot
from pyjinhx.base import AttrValue, ExtraAttrs, PjxSlot


class PJXEmptyState(BaseComponent):
    image: Slot = ""
    title: str | BaseComponent = ""
    description: str | BaseComponent = ""
    action: Slot = ""
    actions: Annotated[list[str | BaseComponent], PjxSlot()] = Field(
        default_factory=list
    )
    # First-class interactive suggestion chips (option a from issue #77).
    # Each item is a dict with:
    #   - label      (str): button text
    #   - value      (str, optional): dispatched with the event; defaults to label
    #   - event      (str, optional): custom event name; defaults to "pjx:suggestion"
    suggestions: list[Any] = Field(default_factory=list)
    class_name: AttrValue = ""
    extra_attrs: ExtraAttrs = Field(default_factory=dict)
