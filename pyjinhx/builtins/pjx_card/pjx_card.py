from pydantic import Field

from pyjinhx._component import AttrValue, BaseComponent, ExtraAttrs, Slot


class PJXCard(BaseComponent):
    """The card shell; regions come from PJXCardHeader/Body/Footer, not from fields here."""

    class_name: AttrValue = ""
    content: Slot = ""
    extra_attrs: ExtraAttrs = Field(default_factory=dict)
