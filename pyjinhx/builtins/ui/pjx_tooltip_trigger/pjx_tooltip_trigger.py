from pyjinhx import BaseComponent
from pyjinhx.base import AttrValue


class PJXTooltipTrigger(BaseComponent):
    class_name: AttrValue = ""
    content: str | BaseComponent = ""
