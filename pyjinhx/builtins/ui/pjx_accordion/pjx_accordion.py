from typing import Annotated

from pyjinhx import BaseComponent
from pyjinhx.base import AttrValue, PjxSlot


class PJXAccordion(BaseComponent):
    label: str = ""
    # `Slot | None` (Optional[Annotated[...]]) drops the PjxSlot metadata at the
    # field level, so the marker must sit on the outer Annotated. See #118.
    header: Annotated[str | BaseComponent | None, PjxSlot()] = None
    open: bool = True
    disabled: bool = False
    group: str | None = None
    content: str | BaseComponent = ""
    actions: Annotated[str | BaseComponent | None, PjxSlot()] = None
    class_name: AttrValue = ""
