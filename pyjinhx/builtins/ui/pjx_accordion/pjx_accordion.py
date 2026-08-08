from pydantic import Field

from pyjinhx._component import AttrValue, BaseComponent, ExtraAttrs, Slot


class PJXAccordion(BaseComponent):
    """The <details> shell of one accordion item; the summary and body come from PJXAccordionTrigger/Content."""

    open: bool = True
    group: str | None = None
    class_name: AttrValue = ""
    content: Slot = ""
    extra_attrs: ExtraAttrs = Field(default_factory=dict)
