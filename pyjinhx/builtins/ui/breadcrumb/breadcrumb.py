import json
from typing import Annotated, Any

from pydantic import BeforeValidator, Field

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
