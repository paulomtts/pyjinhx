from pyjinhx.component import AttrValue, BaseComponent, Slot


class PJXTooltipTrigger(BaseComponent):
    """The focusable element whose hover/focus reveals its tooltip tip (port of v0.x pyjinhx/builtins/ui/pjx_tooltip_trigger/pjx_tooltip_trigger.py)."""

    class_name: AttrValue = ""
    content: Slot = ""
