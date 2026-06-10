import json
from typing import Annotated, Any

from pydantic import BeforeValidator, Field, field_validator

from pyjinhx import BaseComponent


def _coerce_breadcrumb_items(value: Any) -> list[tuple[str, str | None]]:
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return []
        raw: list[list[str | None]] = json.loads(text)
        return [(str(row[0]), row[1]) for row in raw]
    return value


class Breadcrumb(BaseComponent):
    items: Annotated[
        list[tuple[str, str | None]],
        BeforeValidator(_coerce_breadcrumb_items),
    ] = Field(default_factory=list)
    aria_label: str = "Breadcrumb"
    class_name: str = ""
    extra_attrs: dict[str, str] = Field(default_factory=dict)

    @field_validator("extra_attrs", mode="before")
    @classmethod
    def _sanitize_extra_attrs(cls, v: dict) -> dict:
        return {k: str(val).replace("<", "").replace(">", "") for k, val in v.items()}
