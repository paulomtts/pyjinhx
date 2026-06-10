from pydantic import Field, field_validator

from pyjinhx import BaseComponent


class Card(BaseComponent):
    title: str | BaseComponent = ""
    header: str | BaseComponent = ""
    body: str | BaseComponent = ""
    footer: str | BaseComponent = ""
    class_name: str = ""
    extra_attrs: dict[str, str] = Field(default_factory=dict)

    @field_validator("extra_attrs", mode="before")
    @classmethod
    def _sanitize_extra_attrs(cls, v: dict) -> dict:
        return {k: str(val).replace("<", "").replace(">", "") for k, val in v.items()}
