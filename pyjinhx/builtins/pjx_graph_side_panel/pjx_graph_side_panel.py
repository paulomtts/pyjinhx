from pydantic import Field, field_validator

from pyjinhx._component import AttrValue, BaseComponent, Children, ExtraAttrs, Slot


class PJXGraphSidePanel(BaseComponent):
    """A floating card beside a :class:`PJXGraph` canvas: header plus one content region.

    Pass it as the graph's ``panel`` slot. ``open`` only sets ``data-open``;
    ``content`` renders either way, and the stylesheet hides a closed panel.
    The back button is always rendered ``hidden``. ``badge`` and ``content``
    are raw HTML; every other text is escaped, and each label is also its
    button's ``aria-label``.
    """

    title: str = ""
    aria_label: str = "Graph panel"
    marker: bool = False
    accent_color: AttrValue = ""
    badge: Slot = ""
    back_label: str = "Back"
    close_label: str = "Close"
    open: bool = False
    content: Children = ""
    class_name: AttrValue = ""
    extra_attrs: ExtraAttrs = Field(default_factory=dict)

    @field_validator("accent_color")
    @classmethod
    def _check_accent_color(cls, value: str) -> str:
        """Reject a colour that could end its declaration in the root's style attribute."""
        if ";" in value:
            raise ValueError("accent_color must not contain ';'")
        return value
