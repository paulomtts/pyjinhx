import math
import re
from typing import ClassVar

from pydantic import ValidationInfo, computed_field, field_validator

from pyjinhx2.component import AttrValue, BaseComponent, Slot

_PX = re.compile(r"^\d+(\.\d+)?px$")
_NUM = re.compile(r"\d+(\.\d+)?")


def _is_pct(v: object) -> bool:
    if isinstance(v, bool):
        return False
    if isinstance(v, (int, float)):
        return math.isfinite(v) and v >= 0 and _NUM.fullmatch(str(v)) is not None
    if isinstance(v, str):
        return _NUM.fullmatch(v) is not None
    return False


def _floor_css(v: object) -> str | None:
    """CSS length for the min/max CSS var, or None for a percentage."""
    if _is_pct(v):
        return None
    if v == "content":
        return "min-content"
    return str(v)  # validated "<n>px"


class PJXResizablePanel(BaseComponent):
    """One resizable region of a :class:`PJXResizableGroup`.

    A bound given as a bare number is a percentage the group's controller
    clamps in JS; a ``"<n>px"`` bound (or ``min="content"``) is a hard floor
    the browser owns through a CSS custom property, because a pixel strip must
    stay visible even when the percentage math would hide it.
    """

    _pjx_children_field: ClassVar[str | None] = "content"

    size: float | None = None
    min: str | float = 0.0
    max: str | float = 100.0
    class_name: AttrValue = ""
    content: Slot = ""

    @field_validator("min", "max")
    @classmethod
    def _check_bound(cls, v: object, info: ValidationInfo) -> object:
        if _is_pct(v):
            return v
        if isinstance(v, str):
            if _PX.match(v):
                return v
            if v == "content" and info.field_name == "min":
                return v
        raise ValueError(
            f"PJXResizablePanel.{info.field_name} must be a percentage number, "
            f"an '<n>px' string, or (min only) 'content'; got {v!r}"
        )

    @computed_field
    @property
    def min_css(self) -> str | None:
        return _floor_css(self.min)

    @computed_field
    @property
    def max_css(self) -> str | None:
        return _floor_css(self.max)
