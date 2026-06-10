from typing import Literal

from pydantic import Field, field_validator

from pyjinhx import BaseComponent
from pyjinhx.base import AttrValue, ExtraAttrs


class Avatar(BaseComponent):
    src: str = ""
    alt: str = ""
    initials: str = ""
    size: Literal["sm", "md", "lg"] = "md"
    class_name: AttrValue = ""
    color: AttrValue = ""
    extra_attrs: ExtraAttrs = Field(default_factory=dict)

    @field_validator("initials", mode="before")
    @classmethod
    def cap_initials(cls, value: str) -> str:
        if not value:
            return ""
        text = str(value).strip()
        return text[:2] if len(text) > 2 else text
