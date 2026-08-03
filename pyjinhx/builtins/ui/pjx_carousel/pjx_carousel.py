from typing import ClassVar

from pydantic import Field

from pyjinhx.builtins.ui.pjx_icon import PJXIcon
from pyjinhx.component import AttrValue, BaseComponent, ExtraAttrs, Slot


class PJXCarousel(BaseComponent):
    """A slide deck with arrows, dots, keyboard nav, swipe and opt-in autoplay.

    The server emits static markup only. Every interactive affordance is found
    by the co-located controller through ``data-pjx-carousel*`` markers, so no
    inline handler ever reaches the page, and autoplay stays opt-in because an
    unrequested moving region is an accessibility hazard.
    """

    _pjx_children_field: ClassVar[str | None] = "content"

    label: str = "Carousel"
    loop: bool = True
    autoplay: bool = False
    interval_ms: int = 5000
    prev_label: str = "Previous slide"
    next_label: str = "Next slide"
    autoplay_toggle_label: str = "Pause autoplay"
    class_name: AttrValue = ""
    content: Slot = ""
    extra_attrs: ExtraAttrs = Field(default_factory=dict)
    # Composed in Python rather than as <PJXIcon/> tag literals: a literal
    # only resolves once build_registry() has run, so these four icons came
    # out as raw tag text in any render path that never called setup() (#693).
    prev_icon: PJXIcon = Field(default_factory=lambda: PJXIcon(name="chevron-left"))
    next_icon: PJXIcon = Field(default_factory=lambda: PJXIcon(name="chevron-right"))
    pause_icon: PJXIcon = Field(
        default_factory=lambda: PJXIcon(
            name="pause", class_name="pjx-carousel__autoplay-icon-pause"
        )
    )
    play_icon: PJXIcon = Field(
        default_factory=lambda: PJXIcon(
            name="play", class_name="pjx-carousel__autoplay-icon-play"
        )
    )
