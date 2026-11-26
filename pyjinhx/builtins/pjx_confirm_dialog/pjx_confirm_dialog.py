from pydantic import Field

from pyjinhx._component import AttrValue, BaseComponent, ExtraAttrs


class PJXConfirmDialog(BaseComponent):
    """The confirm shell and its button labels; the message text and open/close are driven by pjx.confirm(), not by fields here."""

    confirm_label: str = "Confirm"
    cancel_label: str = "Cancel"
    class_name: AttrValue = ""
    extra_attrs: ExtraAttrs = Field(default_factory=dict)
