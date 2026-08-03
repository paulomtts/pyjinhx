from pyjinhx.component import AttrValue, BaseComponent, Slot


class PJXTabList(BaseComponent):
    """The tablist row holding a group's PJXTab triggers."""

    label: str = "Tabs"
    reorderable: bool = False
    class_name: AttrValue = ""
    content: Slot = ""
