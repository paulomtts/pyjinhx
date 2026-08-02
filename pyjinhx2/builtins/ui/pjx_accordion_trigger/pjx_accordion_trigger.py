from pyjinhx2.component import AttrValue, BaseComponent, Slot


class PJXAccordionTrigger(BaseComponent):
    """The <summary> row that toggles its parent PJXAccordion, with the chevron affordance."""

    disabled: bool = False
    class_name: AttrValue = ""
    content: Slot = ""
