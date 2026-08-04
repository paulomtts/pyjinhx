import logging

from pydantic import model_validator

from pyjinhx._component import AttrValue, BaseComponent, Slot
from pyjinhx.builtins.ui.pjx_icon._icons import ICONS

logger = logging.getLogger(__name__)


class PJXIcon(BaseComponent):
    name: str
    size: int | str = 16
    stroke_width: float = 1.5
    label: str | None = None
    class_name: AttrValue = ""

    # Derived, not user-supplied. Declared as real fields (not computed_field)
    # because a computed field never lands in model_fields, and the descriptor's
    # slot-field resolution (and thus render_context.build_context) only walks
    # model_fields.
    svg_inner: Slot = ""
    svg_size: str = ""

    @model_validator(mode="after")
    def _derive(self) -> "PJXIcon":
        inner = ICONS.get(self.name)
        if inner is None:
            logger.warning(
                "PJXIcon: unknown icon name %r; rendering nothing", self.name
            )
            inner = ""
        self.svg_inner = inner
        self.svg_size = (
            f"{self.size}px" if isinstance(self.size, int) else str(self.size)
        )
        return self
