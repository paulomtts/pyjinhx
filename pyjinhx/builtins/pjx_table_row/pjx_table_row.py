from pydantic import Field

from pyjinhx._component import AttrValue, BaseComponent, ExtraAttrs, Slot


class PJXTableRow(BaseComponent):
    """A table row, optionally carrying a selection checkbox."""

    selectable: bool = False
    value: str = ""
    select_label: str = "Select row"
    class_name: AttrValue = ""
    content: Slot = ""
    extra_attrs: ExtraAttrs = Field(default_factory=dict)
