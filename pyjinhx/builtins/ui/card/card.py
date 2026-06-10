from pydantic import Field, field_validator

from pyjinhx import BaseComponent
from pyjinhx.base import validate_extra_attrs


class Card(BaseComponent):
    title: str | BaseComponent = ""
    header: str | BaseComponent = ""
    body: str | BaseComponent = ""
    footer: str | BaseComponent = ""
    class_name: str = ""
    extra_attrs: dict[str, str] = Field(default_factory=dict)

    @field_validator("extra_attrs")
    @classmethod
    def _validate_extra_attrs(cls, value: dict[str, str]) -> dict[str, str]:
        return validate_extra_attrs(value)
