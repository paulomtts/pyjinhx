from typing import Literal

from pydantic import Field

from pyjinhx.component import AttrValue, BaseComponent, ExtraAttrs, Slot


class PJXNotification(BaseComponent):
    """A corner-anchored status notification, shown and hidden from the client.

    Visibility, the auto-show on mount and the dismiss timer are all driven by
    ``pjx.notification`` in the co-located script — the server only emits the
    markup and its data attributes.
    """

    content: Slot = ""
    corner: Literal["top-right", "top-left", "bottom-right", "bottom-left"] = (
        "top-right"
    )
    timeout: int = 5000
    autoshow: bool = True
    dismiss_label: str = "Dismiss"
    class_name: AttrValue = ""
    extra_attrs: ExtraAttrs = Field(default_factory=dict)
