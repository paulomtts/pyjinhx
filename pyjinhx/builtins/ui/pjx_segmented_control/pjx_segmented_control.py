import json
from typing import Annotated, Any

from pydantic import BeforeValidator, Field

from pyjinhx import BaseComponent
from pyjinhx.base import AttrValue, ExtraAttrs


def _coerce_options(value: Any) -> list[tuple[str, str]]:
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return []
        raw = json.loads(text)
        return [(str(row[0]), str(row[1])) for row in raw]
    return value


class PJXSegmentedControl(BaseComponent):
    name: str
    options: Annotated[
        list[tuple[str, str]],
        BeforeValidator(_coerce_options),
    ] = Field(default_factory=list)
    selected: str = ""
    disabled: bool = False
    class_name: AttrValue = ""
    extra_attrs: ExtraAttrs = Field(default_factory=dict)
