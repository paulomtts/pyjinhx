from typing import Any

from pydantic import Field

from pyjinhx import BaseComponent
from pyjinhx.base import AttrValue, ExtraAttrs


class PJXAvatarStack(BaseComponent):
    # Items to render.  Two accepted shapes:
    #   - Structured dict: keys initials, color, alt, name
    #       - initials (str): text shown in the pill (escaped)
    #       - color    (str, optional): inline background color
    #       - alt      (str, optional): tooltip/title on the pill (escaped)
    #       - name     (str, optional): alias for alt; alt takes precedence if both given
    #   - BaseComponent instance: rendered raw via __html__
    #
    # Note: plain HTML *strings* are now escaped (autoescape is on).
    # Pass a BaseComponent for raw markup instead of a string.
    avatars: list[Any] = Field(default_factory=list)
    extra_count: int = 0
    empty_label: str = ""
    class_name: AttrValue = ""
    extra_attrs: ExtraAttrs = Field(default_factory=dict)
