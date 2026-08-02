from pyjinhx2.component import AttrValue, BaseComponent, Slot


class PJXDrawerFooter(BaseComponent):
    """The bottom action region of a drawer."""

    class_name: AttrValue = ""
    content: Slot = ""
