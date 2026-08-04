from pyjinhx._component import AttrValue, BaseComponent, Slot


class PJXModalFooter(BaseComponent):
    """The bottom action region of a modal."""

    class_name: AttrValue = ""
    content: Slot = ""
