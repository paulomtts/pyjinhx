from pyjinhx.component import AttrValue, BaseComponent, Slot


class PJXDrawerHeader(BaseComponent):
    """The top region of a drawer; ``title`` is a shortcut that replaces ``content``, and the close button is always present."""

    title: str = ""
    close_label: str = "Close"
    close_content: Slot = "✕"
    class_name: AttrValue = ""
    content: Slot = ""
