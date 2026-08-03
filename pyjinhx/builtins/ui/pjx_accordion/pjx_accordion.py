from pyjinhx.component import AttrValue, BaseComponent, Slot


class PJXAccordion(BaseComponent):
    """The <details> shell of one accordion item; the summary and body come from PJXAccordionTrigger/Content."""

    open: bool = True
    group: str | None = None
    class_name: AttrValue = ""
    content: Slot = ""
