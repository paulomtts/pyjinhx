import json
from typing import Annotated, Any

from pydantic import BeforeValidator, Field

from pyjinhx import BaseComponent


def _coerce_tabs(value: Any) -> dict[str, str | BaseComponent]:
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return {}
        return json.loads(text)
    return value


class TabGroup(BaseComponent):
    tabs: Annotated[dict[str, str | BaseComponent], BeforeValidator(_coerce_tabs)] = Field(
        default_factory=dict
    )
