from typing import Any

from pydantic import Field

from pyjinhx import BaseComponent
from pyjinhx.base import AttrValue, ExtraAttrs


class PJXAvatarStack(BaseComponent):
    # Pre-built items (original interface): HTML strings or BaseComponent instances.
    # Structured data (new interface): dicts with keys initials, color, alt, name.
    #   - initials (str): text shown in the pill
    #   - color    (str, optional): inline background color
    #   - alt      (str, optional): tooltip/title on the pill
    #   - name     (str, optional): alias for alt; alt takes precedence if both given
    avatars: list[Any] = Field(default_factory=list)
    extra_count: int = 0
    empty_label: str = ""
    class_name: AttrValue = ""
    extra_attrs: ExtraAttrs = Field(default_factory=dict)
