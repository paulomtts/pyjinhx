from pyjinhx2.component import AttrValue, BaseComponent, Slot


class PJXTableHead(BaseComponent):
    """A table header section."""

    class_name: AttrValue = ""
    content: Slot = ""
