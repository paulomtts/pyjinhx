from pydantic import Field

from pyjinhx._component import AttrValue, BaseComponent, ExtraAttrs, Slot


class PJXCardHeader(BaseComponent):
    """The top region of a card; ``title`` is a shortcut that replaces ``content``."""

    title: str = ""
    class_name: AttrValue = ""
    content: Slot = ""
    extra_attrs: ExtraAttrs = Field(default_factory=dict)
