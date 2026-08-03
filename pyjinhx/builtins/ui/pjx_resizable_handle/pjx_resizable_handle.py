from pyjinhx.component import AttrValue, BaseComponent


class PJXResizableHandle(BaseComponent):
    """The draggable divider between two :class:`PJXResizablePanel` siblings.

    It renders as an ARIA separator with no behavior of its own: the group's
    controller finds it by the ``data-pjx-resizable-handle`` marker and keeps
    ``aria-valuenow`` in sync as the boundary moves.
    """

    label: str = "Resize"
    class_name: AttrValue = ""
