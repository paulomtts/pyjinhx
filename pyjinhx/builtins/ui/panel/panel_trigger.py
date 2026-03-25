import re

from pydantic import field_validator

from pyjinhx import BaseComponent

_PANEL_KEY_PATTERN = re.compile(r"^[a-zA-Z0-9_-]+$")


class PanelTrigger(BaseComponent):
    panel_id: str
    panel: str
    content: str | BaseComponent = ""

    @field_validator("panel", mode="after")
    @classmethod
    def validate_panel_key(cls, value: str) -> str:
        if not _PANEL_KEY_PATTERN.match(value):
            raise ValueError(
                f"panel key {value!r} must match [a-zA-Z0-9_-]+ for stable HTML ids"
            )
        return value
