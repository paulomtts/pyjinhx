from typing import ClassVar, Literal

from pydantic import Field

from pyjinhx.component import AttrValue, BaseComponent, ExtraAttrs, Slot


class PJXAlert(BaseComponent):
    """An inline, optionally dismissible status banner.

    The server emits static markup only; dismissal is wired declaratively by
    the co-located script off the ``data-pjx-close`` marker, so no inline
    handler ever reaches the page.
    """

    _pjx_children_field: ClassVar[str | None] = "body"

    variant: Literal["info", "success", "warning", "error"] = "info"
    title: str = ""
    body: Slot = ""
    dismissible: bool = False
    dismiss_label: str = "Dismiss"
    class_name: AttrValue = ""
    extra_attrs: ExtraAttrs = Field(default_factory=dict)
