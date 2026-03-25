import json
import re
from typing import Annotated, Any

from pydantic import BeforeValidator, Field, field_validator

from pyjinhx import BaseComponent


def _coerce_panels(value: Any) -> dict[str, str | BaseComponent]:
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return {}
        return json.loads(text)
    return value


_PANEL_KEY_PATTERN = re.compile(r"^[a-zA-Z0-9_-]+$")


class Panel(BaseComponent):
    panels: Annotated[dict[str, str | BaseComponent], BeforeValidator(_coerce_panels)] = Field(
        default_factory=dict
    )

    @field_validator("panels", mode="after")
    @classmethod
    def validate_panel_keys(cls, value: dict[str, Any]) -> dict[str, Any]:
        for key in value:
            if not _PANEL_KEY_PATTERN.match(key):
                raise ValueError(
                    f"panel key {key!r} must match [a-zA-Z0-9_-]+ for stable HTML ids"
                )
        return value
