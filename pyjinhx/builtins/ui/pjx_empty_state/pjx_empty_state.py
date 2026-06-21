from typing import Any

from pydantic import Field

from pyjinhx import BaseComponent
from pyjinhx.base import AttrValue, ExtraAttrs


class PJXEmptyState(BaseComponent):
    # First-class interactive suggestion chips (issue #77). Each item is a dict:
    #   - label (str): button text
    #   - value (str, optional): dispatched with the event; defaults to label
    #   - event (str, optional): custom event name; defaults to "pjx:suggestion"
    suggestions: list[Any] = Field(default_factory=list)
    class_name: AttrValue = ""
    content: str | BaseComponent = ""
    extra_attrs: ExtraAttrs = Field(default_factory=dict)
