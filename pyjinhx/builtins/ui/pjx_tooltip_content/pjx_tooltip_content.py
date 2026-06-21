from pyjinhx import BaseComponent
from pyjinhx.base import AttrValue


class PJXTooltipContent(BaseComponent):
    class_name: AttrValue = ""
    content: str | BaseComponent = ""
