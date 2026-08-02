from pyjinhx2.component import AttrValue, BaseComponent, Slot


class PJXCardBody(BaseComponent):
    """The padded content region of a card."""

    class_name: AttrValue = ""
    content: Slot = ""
