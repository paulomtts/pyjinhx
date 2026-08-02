from pyjinhx2.component import AttrValue, BaseComponent, Slot


class PJXCardFooter(BaseComponent):
    """The bottom region of a card, separated by a rule."""

    class_name: AttrValue = ""
    content: Slot = ""
