import re

from pydantic import Field, field_validator

from pyjinhx import BaseComponent
from pyjinhx.base import AttrValue, ExtraAttrs

_PANEL_KEY_PATTERN = re.compile(r"^[a-zA-Z0-9_-]+$")


class PJXPanelTrigger(BaseComponent):
    panel_id: str
    panel: str
    content: str | BaseComponent = ""
    class_name: AttrValue = ""
    extra_attrs: ExtraAttrs = Field(default_factory=dict)

    @field_validator("panel", mode="after")
    @classmethod
    def validate_panel_key(cls, value: str) -> str:
        if not _PANEL_KEY_PATTERN.match(value):
            raise ValueError(
                f"panel key {value!r} must match [a-zA-Z0-9_-]+ for stable HTML ids"
            )
        return value
