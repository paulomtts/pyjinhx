from typing import Self

from pydantic import Field, model_validator

from pyjinhx._component import AttrValue, BaseComponent, ExtraAttrs
from pyjinhx.builtins.ui.pjx_roster_chip import PJXRosterChip
from pyjinhx.builtins.ui.pjx_roster_picker.item import PJXRosterItem


class PJXRosterPicker(BaseComponent):
    """A searchable picker that holds its selection as removable chips.

    The search box asks ``candidates_url`` for result rows as the user types;
    each selected item renders as a ``PJXRosterChip`` whose hidden input posts
    under ``name``. ``max_items`` caps the selection (0 means no cap).

    ``disabled`` drops the search box and every remove button but keeps the
    chips' hidden inputs, so the selection still submits. ``required`` adds a
    visually hidden input that fails constraint validation while nothing is
    selected; a disabled picker's copy is disabled too, so a picker the user
    cannot change never blocks its form.
    """

    name: str = Field(min_length=1)
    candidates_url: str = Field(min_length=1)
    items: list[PJXRosterItem] = Field(default_factory=list)
    max_items: int = Field(default=0, ge=0)
    required: bool = False
    disabled: bool = False
    portal: bool = False
    placeholder: str = "Search…"
    remove_label: str = "Remove"
    limit_label: str = "Limit reached"
    empty_message: str = "No results"
    class_name: AttrValue = ""
    extra_attrs: ExtraAttrs = Field(default_factory=dict)

    # Derived from items, not user-supplied. Built in Python rather than as tag
    # literals in the template for the same reason PJXRosterChip.visual is.
    chips: list[PJXRosterChip] = Field(default_factory=list)

    @model_validator(mode="after")
    def _build_chips(self) -> Self:
        seen: set[str] = set()
        for item in self.items:
            if item.value in seen:
                raise ValueError(f"duplicate item value {item.value!r}")
            seen.add(item.value)
        if self.max_items and len(self.items) > self.max_items:
            raise ValueError(
                f"{len(self.items)} items exceed max_items={self.max_items}"
            )
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
                name=self.name,
                remove_label=self.remove_label,
                disabled=self.disabled,
            )
            for item in self.items
        ]
        return self
