import re

from pydantic import ValidationInfo, computed_field, field_validator

from pyjinhx import BaseComponent
from pyjinhx.base import AttrValue

_PX = re.compile(r"^\d+(\.\d+)?px$")


def _is_pct(v: object) -> bool:
    if isinstance(v, bool):
        return False
    if isinstance(v, (int, float)):
        return True
    try:
        float(v)  # type: ignore[arg-type]
        return True
    except (TypeError, ValueError):
        return False


def _floor_css(v: object) -> str | None:
    """CSS length for the min/max CSS var, or None for a percentage."""
    if _is_pct(v):
        return None
    if v == "content":
        return "min-content"
    return str(v)  # validated "<n>px"


class PJXResizablePanel(BaseComponent):
    size: float | None = None
    min: str | float = 0.0
    max: str | float = 100.0
    class_name: AttrValue = ""
    content: str | BaseComponent = ""

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
