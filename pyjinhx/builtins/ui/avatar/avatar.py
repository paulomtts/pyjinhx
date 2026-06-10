from typing import Literal

from pydantic import Field, field_validator

from pyjinhx import BaseComponent


class Avatar(BaseComponent):
    src: str = ""
    alt: str = ""
    initials: str = ""
    size: Literal["sm", "md", "lg"] = "md"
    class_name: str = ""
    color: str = ""
    extra_attrs: dict[str, str] = Field(default_factory=dict)

    @field_validator("extra_attrs", mode="before")
    @classmethod
    def _sanitize_extra_attrs(cls, v: dict) -> dict:
        return {k: str(val).replace("<", "").replace(">", "") for k, val in v.items()}

    @field_validator("initials", mode="before")
    @classmethod
    def cap_initials(cls, value: str) -> str:
        if not value:
            return ""
        text = str(value).strip()
        return text[:2] if len(text) > 2 else text
