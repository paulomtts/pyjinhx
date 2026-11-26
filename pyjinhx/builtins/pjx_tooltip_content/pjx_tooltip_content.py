from pydantic import Field

from pyjinhx._component import AttrValue, BaseComponent, ExtraAttrs, Slot


class PJXTooltipContent(BaseComponent):
    """The hidden tip a tooltip trigger reveals; the root shell's JS positions it (port of v0.x pyjinhx/builtins/ui/pjx_tooltip_content/pjx_tooltip_content.py)."""

    class_name: AttrValue = ""
    content: Slot = ""
    extra_attrs: ExtraAttrs = Field(default_factory=dict)
