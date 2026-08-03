from pyjinhx.component import AttrValue, BaseComponent, Slot


class PJXTableBody(BaseComponent):
    """A table body section."""

    class_name: AttrValue = ""
    content: Slot = ""
