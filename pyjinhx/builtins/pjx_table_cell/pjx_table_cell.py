from pyjinhx.component import AttrValue, BaseComponent, Slot


class PJXTableCell(BaseComponent):
    """A table body cell."""

    class_name: AttrValue = ""
    content: Slot = ""
