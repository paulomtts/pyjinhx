from pyjinhx.component import AttrValue, BaseComponent, Slot


class PJXTabGroup(BaseComponent):
    """The outer shell that binds a tab list to its panels; the JS finds its members through data-pjx-tab-group."""

    class_name: AttrValue = ""
    content: Slot = ""
