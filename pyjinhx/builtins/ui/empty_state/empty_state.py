from pydantic import Field, field_validator

from pyjinhx import BaseComponent


class EmptyState(BaseComponent):
    image: str | BaseComponent = ""
    title: str | BaseComponent = ""
    description: str | BaseComponent = ""
    action: str | BaseComponent = ""
    actions: list[str | BaseComponent] = Field(default_factory=list)
    class_name: str = ""
    extra_attrs: dict[str, str] = Field(default_factory=dict)

    @field_validator("extra_attrs", mode="before")
    @classmethod
    def _sanitize_extra_attrs(cls, v: dict) -> dict:
        return {k: str(val).replace("<", "").replace(">", "") for k, val in v.items()}
