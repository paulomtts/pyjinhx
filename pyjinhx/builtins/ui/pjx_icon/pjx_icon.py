import logging

from pydantic import computed_field

from pyjinhx import BaseComponent
from pyjinhx.base import AttrValue

from ._icons import ICONS

logger = logging.getLogger(__name__)


class PJXIcon(BaseComponent):
    name: str
    size: int | str = 16
    stroke_width: float = 1.5
    label: str | None = None
    class_name: AttrValue = ""

    @computed_field
    @property
    def svg_inner(self) -> str:
        inner = ICONS.get(self.name)
        if inner is None:
            logger.warning("PJXIcon: unknown icon name %r; rendering nothing", self.name)
            return ""
        return inner

    @computed_field
    @property
    def svg_size(self) -> str:
        return f"{self.size}px" if isinstance(self.size, int) else str(self.size)
