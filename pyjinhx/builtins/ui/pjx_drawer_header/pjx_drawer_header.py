from pydantic import Field

from pyjinhx._component import AttrValue, BaseComponent, ExtraAttrs, Slot


class PJXDrawerHeader(BaseComponent):
    """The top region of a drawer; ``title`` is a shortcut that replaces ``content``, and the close button is always present."""

    title: str = ""
    close_label: str = "Close"
    close_content: Slot = "✕"
    class_name: AttrValue = ""
    content: Slot = ""
    extra_attrs: ExtraAttrs = Field(default_factory=dict)
