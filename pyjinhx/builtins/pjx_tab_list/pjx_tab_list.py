from pydantic import Field

from pyjinhx._component import AttrValue, BaseComponent, ExtraAttrs, Slot


class PJXTabList(BaseComponent):
    """The tablist row holding a group's PJXTab triggers."""

    label: str = "Tabs"
    reorderable: bool = False
    class_name: AttrValue = ""
    extra_attrs: ExtraAttrs = Field(default_factory=dict)
    content: Slot = ""
