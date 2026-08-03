from typing import Annotated, Any

from pydantic import Field

from pyjinhx.component import AttrValue, BaseComponent, PjxSlot


class PJXAvatarStack(BaseComponent):
    """A row of overlapping avatar pills with an optional "+N" overflow badge."""

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
    #
    # The PjxSlot marker is what keeps the second shape working on v2:
    # build_context() serializes non-slot fields through model_dump(), which
    # would turn a component into a plain dict and route it down the
    # "is mapping" pill branch. Marking the field slot re-reads the live list
    # and wraps each component as an opaque node instead.
    avatars: Annotated[list[Any], PjxSlot()] = Field(default_factory=list)
    extra_count: int = 0
    empty_label: str = ""
    class_name: AttrValue = ""
