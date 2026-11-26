from pydantic import Field

from pyjinhx._component import AttrValue, BaseComponent, ExtraAttrs, Slot


class PJXTooltipTrigger(BaseComponent):
    """The focusable element whose hover/focus reveals its tooltip tip (port of v0.x pyjinhx/builtins/ui/pjx_tooltip_trigger/pjx_tooltip_trigger.py)."""

    class_name: AttrValue = ""
    content: Slot = ""
    extra_attrs: ExtraAttrs = Field(default_factory=dict)
