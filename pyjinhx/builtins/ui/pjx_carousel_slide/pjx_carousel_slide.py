from typing import ClassVar

from pydantic import Field

from pyjinhx._component import AttrValue, BaseComponent, ExtraAttrs, Slot


class PJXCarouselSlide(BaseComponent):
    """One panel of a :class:`PJXCarousel`.

    The slide carries no behavior of its own: the carousel's controller finds
    it by the ``data-pjx-carousel-slide`` marker and drives visibility,
    ``inert`` and the positional aria-label from there.
    """

    _pjx_children_field: ClassVar[str | None] = "content"

    label: str = ""
    class_name: AttrValue = ""
    content: Slot = ""
    extra_attrs: ExtraAttrs = Field(default_factory=dict)
