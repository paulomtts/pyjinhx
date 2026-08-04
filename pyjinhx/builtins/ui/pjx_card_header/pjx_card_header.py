from pyjinhx._component import AttrValue, BaseComponent, Slot


class PJXCardHeader(BaseComponent):
    """The top region of a card; ``title`` is a shortcut that replaces ``content``."""

    title: str = ""
    class_name: AttrValue = ""
    content: Slot = ""
