from pyjinhx._component import AttrValue, BaseComponent, Slot


class PJXTab(BaseComponent):
    """One tab trigger; ``panel`` wires it to the PJXTabPanel it reveals."""

    panel: str = ""
    icon: str = ""
    closeable: bool = False
    pinned: bool = False
    selected: bool = False
    close_label: str = "Close"
    class_name: AttrValue = ""
    content: Slot = ""
