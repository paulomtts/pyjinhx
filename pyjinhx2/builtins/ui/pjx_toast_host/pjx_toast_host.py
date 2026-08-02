from typing import Literal

from pydantic import Field

from pyjinhx2.component import AttrValue, BaseComponent, ExtraAttrs


class PJXToastHost(BaseComponent):
    """A fixed container that the client fills with transient toasts.

    The server renders an empty, configured host; ``pjx.toast`` and the
    ``event_name`` listener in the co-located script create, stack and expire
    the toast elements entirely on the client.
    """

    position: Literal["top-right", "top-left", "bottom-right", "bottom-left"] = (
        "bottom-right"
    )
    timeout: int = 4000
    dismiss_label: str = "Dismiss"
    event_name: str = "pjx:toast"
    class_name: AttrValue = ""
    extra_attrs: ExtraAttrs = Field(default_factory=dict)
