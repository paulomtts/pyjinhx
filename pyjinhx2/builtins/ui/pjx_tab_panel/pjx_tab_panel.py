from pyjinhx2.component import AttrValue, BaseComponent, Slot


class PJXTabPanel(BaseComponent):
    """The panel a tab reveals; hidden until the group JS selects its tab."""

    tab: str = ""
    class_name: AttrValue = ""
    content: Slot = ""
