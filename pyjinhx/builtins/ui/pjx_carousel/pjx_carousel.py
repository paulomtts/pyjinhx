from pyjinhx import BaseComponent
from pyjinhx.base import AttrValue


class PJXCarousel(BaseComponent):
    label: str = "Carousel"
    loop: bool = True
    autoplay: bool = False
    interval_ms: int = 5000
    prev_label: str = "Previous slide"
    next_label: str = "Next slide"
    autoplay_toggle_label: str = "Pause autoplay"
    class_name: AttrValue = ""
    content: str | BaseComponent = ""
