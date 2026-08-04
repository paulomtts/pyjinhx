from pyjinhx._component import AttrValue, BaseComponent, Slot


class PJXModalHeader(BaseComponent):
    """The top region of a modal; ``title`` is a shortcut that replaces ``content``, and the close button is always present."""

    title: str = ""
    close_label: str = "Close"
    close_content: Slot = "✕"
    class_name: AttrValue = ""
    content: Slot = ""
