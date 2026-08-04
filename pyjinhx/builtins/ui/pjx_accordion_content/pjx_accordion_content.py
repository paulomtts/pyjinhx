from pyjinhx._component import AttrValue, BaseComponent, Slot


class PJXAccordionContent(BaseComponent):
    """The body region revealed when its parent PJXAccordion is open."""

    class_name: AttrValue = ""
    content: Slot = ""
