from pydantic import Field

from pyjinhx._component import AttrValue, BaseComponent, ExtraAttrs, Slot


class PJXModalHeader(BaseComponent):
    """The top region of a modal; ``title`` is a shortcut that replaces ``content``, and the close button is always present."""

    title: str = ""
    close_label: str = "Close"
    close_content: Slot = "✕"
    class_name: AttrValue = ""
    extra_attrs: ExtraAttrs = Field(default_factory=dict)
    content: Slot = ""
