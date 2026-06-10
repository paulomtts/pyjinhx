from typing import Literal

from pydantic import Field, field_validator

from pyjinhx import BaseComponent


class Tooltip(BaseComponent):
    trigger: str | BaseComponent = ""
    tip: str | BaseComponent = ""
    placement: Literal["top", "bottom", "start", "end"] = "top"
    class_name: str = ""
    extra_attrs: dict[str, str] = Field(default_factory=dict)

    @field_validator("extra_attrs", mode="before")
    @classmethod
    def _sanitize_extra_attrs(cls, v: dict) -> dict:
        return {k: str(val).replace("<", "").replace(">", "") for k, val in v.items()}
