from pyjinhx import BaseComponent, Slot
from pyjinhx.base import AttrValue


class PJXAccordion(BaseComponent):
    label: str = ""
    header: Slot | None = None
    open: bool = True
    disabled: bool = False
    group: str | None = None
    content: str | BaseComponent = ""
    actions: Slot | None = None
    class_name: AttrValue = ""
