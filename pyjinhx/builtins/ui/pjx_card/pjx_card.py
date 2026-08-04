from pyjinhx._component import AttrValue, BaseComponent, Slot


class PJXCard(BaseComponent):
    """The card shell; regions come from PJXCardHeader/Body/Footer, not from fields here."""

    class_name: AttrValue = ""
    content: Slot = ""
