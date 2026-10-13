from pydantic import Field

from pyjinhx._component import AttrValue, BaseComponent, ExtraAttrs
from pyjinhx.builtins.ui.pjx_roster_picker.item import PJXRosterItem


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
