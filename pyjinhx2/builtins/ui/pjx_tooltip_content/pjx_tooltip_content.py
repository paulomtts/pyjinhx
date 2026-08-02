from pyjinhx2.component import AttrValue, BaseComponent, Slot


class PJXTooltipContent(BaseComponent):
    """The hidden tip a tooltip trigger reveals; the root shell's JS positions it (port of v0.x pyjinhx/builtins/ui/pjx_tooltip_content/pjx_tooltip_content.py)."""

    class_name: AttrValue = ""
    content: Slot = ""
