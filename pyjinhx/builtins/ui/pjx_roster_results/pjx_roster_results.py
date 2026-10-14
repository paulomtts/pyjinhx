from typing import Self

from pydantic import Field, model_validator

from pyjinhx._component import AttrValue, BaseComponent, ExtraAttrs
from pyjinhx.builtins.pjx_lazy_load import PJXLazyLoad
from pyjinhx.builtins.ui.pjx_avatar import PJXAvatar
from pyjinhx.builtins.ui.pjx_icon import PJXIcon
from pyjinhx.builtins.ui.pjx_roster_chip import PJXRosterChip
from pyjinhx.builtins.ui.pjx_roster_picker.item import PJXRosterItem


def _visual(item: PJXRosterItem) -> BaseComponent:
    if item.icon:
        return PJXIcon(name=item.icon, class_name="pjx-roster-picker__pick-icon")
    # alt is empty because the label beside the avatar already names it.
    return PJXAvatar(
        src=item.src,
        initials=item.initials,
        color=item.color,
        alt="",
        size="sm",
        class_name="pjx-roster-picker__pick-avatar",
    )


class PJXRosterResults(BaseComponent):
    """One page of a roster picker's search results.

    Each item renders as a pick button followed by a ``<template>`` holding the
    finished ``PJXRosterChip`` the picker clones when the row is picked. With
    items and a ``next_url``, a lazy-load sentinel closes the page and fetches
    the next one when it scrolls into view inside the picker's results list.
    """

    items: list[PJXRosterItem] = Field(default_factory=list)
    # The sentinel's trigger selector and id are built from it: an empty id
    # gives "#-results" and whitespace splits the trigger, and both fail
    # silently in the browser.
    picker_id: str = Field(pattern=r"^\S+$")
    next_url: str = ""
    next_cursor: str = ""
    empty_message: str = "No results"
    remove_label: str = "Remove"
    class_name: AttrValue = ""
    extra_attrs: ExtraAttrs = Field(default_factory=dict)

    # Derived from items, one entry per item, not user-supplied. Built in
    # Python rather than as tag literals in the template for the same reason
    # PJXRosterChip.visual is. visuals is typed list[BaseComponent] because a
    # list of a union is not recognised as a slot.
    visuals: list[BaseComponent] = Field(default_factory=list)
    add_icons: list[PJXIcon] = Field(default_factory=list)
    chips: list[PJXRosterChip] = Field(default_factory=list)
    sentinel: PJXLazyLoad | None = None

    @model_validator(mode="after")
    def _build_rows(self) -> Self:
        self.visuals = [_visual(item) for item in self.items]
        self.add_icons = [
            PJXIcon(name="plus", class_name="pjx-roster-picker__pick-add")
            for _ in self.items
        ]
        self.chips = [
            PJXRosterChip(
                value=item.value,
                label=item.label,
                initials=item.initials,
                color=item.color,
                src=item.src,
                icon=item.icon,
                extra=item.extra,
                detail=item.detail,
                remove_label=self.remove_label,
            )
            for item in self.items
        ]
        if self.items and self.next_url:
            sentinel_id = f"{self.picker_id}-more"
            if self.next_cursor:
                sentinel_id += f"-{self.next_cursor}"
            # The root: scope is required: the default "revealed" trigger never
            # fires for an element inside the scrolling results list.
            self.sentinel = PJXLazyLoad(
                id=sentinel_id,
                url=self.next_url,
                trigger=f"intersect once root:#{self.picker_id}-results",
                swap="outerHTML",
                class_name="pjx-roster-picker__more",
            )
        return self
