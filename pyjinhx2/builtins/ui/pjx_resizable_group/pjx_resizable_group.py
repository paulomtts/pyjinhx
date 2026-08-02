from typing import ClassVar, Literal

from pyjinhx2.component import AttrValue, BaseComponent, Slot


class PJXResizableGroup(BaseComponent):
    """A split pane composing :class:`PJXResizablePanel` / handle children.

    The server emits static markup only; the co-located controller finds the
    group, its panels and its handles through ``data-pjx-resizable-*`` markers
    and owns every grow weight from there, so no inline handler reaches the
    page and a swapped-in group re-initializes itself.
    """

    _pjx_children_field: ClassVar[str | None] = "content"

    direction: Literal["row", "column"] = "row"
    class_name: AttrValue = ""
    content: Slot = ""
