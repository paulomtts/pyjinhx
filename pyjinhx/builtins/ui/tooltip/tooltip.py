from typing import Literal

from pydantic import Field, field_validator

from pyjinhx import BaseComponent
from pyjinhx.base import validate_extra_attrs


class Tooltip(BaseComponent):
    trigger: str | BaseComponent = ""
    tip: str | BaseComponent = ""
    placement: Literal["top", "bottom", "start", "end"] = "top"
    class_name: str = ""
    extra_attrs: dict[str, str] = Field(default_factory=dict)

    @field_validator("extra_attrs")
    @classmethod
    def _validate_extra_attrs(cls, value: dict[str, str]) -> dict[str, str]:
        return validate_extra_attrs(value)
