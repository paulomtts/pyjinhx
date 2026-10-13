from pydantic import Field, model_validator

from pyjinhx._component import AttrValue, BaseComponent, ExtraAttrs, Slot
from pyjinhx.builtins.ui.pjx_avatar import PJXAvatar
from pyjinhx.builtins.ui.pjx_icon import PJXIcon


def _remove_icon() -> PJXIcon:
    return PJXIcon(name="x")


class PJXRosterChip(BaseComponent):
    """One selected roster entry: a hidden input, then the avatar or icon, label,
    ``extra`` and remove button, then an optional ``detail`` row.

    ``name`` may be empty: a chip inside a result's template is named when the
    picker clones it. ``disabled`` drops the remove button but keeps the hidden
    input, so a disabled chip still submits.
    """

    value: str = Field(min_length=1)
    label: str = Field(min_length=1)
    initials: str = ""
    color: AttrValue = ""
    src: str = ""
    icon: str = ""
    extra: Slot = ""
    detail: Slot = ""
    name: str = ""
    remove_label: str = "Remove"
    disabled: bool = False
    class_name: AttrValue = ""
    extra_attrs: ExtraAttrs = Field(default_factory=dict)

    # Derived, not user-supplied. The avatar, the icon and the remove icon are
    # composed in Python rather than as tag literals in the template: a literal
    # only resolves once build_registry() has run, and passing props through
    # tag attributes would escape them a second time.
    visual: Slot = ""
    remove_icon: PJXIcon = Field(default_factory=_remove_icon)

    @model_validator(mode="after")
    def _compose_visual(self) -> "PJXRosterChip":
        if self.icon:
            self.visual = PJXIcon(
                name=self.icon, class_name="pjx-roster-picker__chip-icon"
            )
        else:
            # alt is empty because the label beside the avatar already names it.
            self.visual = PJXAvatar(
                src=self.src,
                initials=self.initials,
                color=self.color,
                alt="",
                size="sm",
                class_name="pjx-roster-picker__chip-avatar",
            )
        return self
