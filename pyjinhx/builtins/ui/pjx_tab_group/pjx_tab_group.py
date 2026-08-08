from pydantic import Field

from pyjinhx._component import AttrValue, BaseComponent, ExtraAttrs, Slot


class PJXTabGroup(BaseComponent):
    """The outer shell that binds a tab list to its panels; the JS finds its members through data-pjx-tab-group."""

    class_name: AttrValue = ""
    extra_attrs: ExtraAttrs = Field(default_factory=dict)
    content: Slot = ""
