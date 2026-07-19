from pyjinhx import BaseComponent
from pyjinhx.base import AttrValue


class PJXCarouselSlide(BaseComponent):
    label: str = ""
    class_name: AttrValue = ""
    content: str | BaseComponent = ""
