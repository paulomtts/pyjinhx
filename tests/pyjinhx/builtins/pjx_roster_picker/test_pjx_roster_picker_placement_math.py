"""pjx.rosterPicker.placement(): the box translation the picker hands to pjx.popoverPosition.

The function is browser code with no DOM access, so the tests load the
committed asset in chromium and call it with synthetic numbers. The numbers
are pinned here, apart from any layout, so popoverPosition's own contract
never has to move to keep the picker right.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pytest

if TYPE_CHECKING:
    from playwright.sync_api import Page

ASSET = (
    Path(__file__).resolve().parents[4]
    / "pyjinhx"
    / "builtins"
    / "ui"
    / "pjx_roster_picker"
    / "pjx_roster_picker.js"
).read_text(encoding="utf-8")
GAP = 4
VIEWPORT = {"top": 0, "bottom": 600}

CASES = [
    pytest.param(
        {"top": 100, "bottom": 140},
        200,
        VIEWPORT,
        {"above": False, "room": 456},
        id="fits-below",
    ),
    pytest.param(
        {"top": 400, "bottom": 440},
        200,
        VIEWPORT,
        {"above": True, "room": 396},
        id="short-below-fits-above",
    ),
    pytest.param(
        {"top": 400, "bottom": 440},
        500,
        VIEWPORT,
        {"above": True, "room": 396},
        id="too-tall-for-both-above-roomier",
    ),
    pytest.param(
        {"top": 150, "bottom": 190},
        500,
        VIEWPORT,
        {"above": False, "room": 406},
        id="too-tall-for-both-below-roomier",
    ),
    pytest.param(
        {"top": 300, "bottom": 340},
        180,
        {"top": 100, "bottom": 500},
        {"above": True, "room": 196},
        id="box-offset-by-a-clipping-ancestor",
    ),
    pytest.param(
        {"top": 300, "bottom": 340},
        180,
        VIEWPORT,
        {"above": False, "room": 256},
        id="same-search-box-not-offset",
    ),
    pytest.param(
        {"top": 200, "bottom": 240},
        300,
        {"top": 0, "bottom": 440},
        {"above": False, "room": 196},
        id="tie-stays-below",
    ),
    pytest.param(
        {"top": 520, "bottom": 560},
        100,
        {"top": 100, "bottom": 500},
        {"above": True, "room": 416},
        id="search-box-scrolled-past-the-box",
    ),
]


@pytest.fixture
def placement(page: Page) -> Callable[..., dict[str, Any]]:
    """Call placement in the browser and hand back its plain-object result."""
    page.set_content("<html><body></body></html>")
    page.add_script_tag(content=ASSET)

    def call(
        search: dict[str, int], list_height: int, box: dict[str, int], gap: int
    ) -> dict[str, Any]:
        args = json.dumps([search, list_height, box, gap])
        return page.evaluate(f"pjx.rosterPicker.placement(...{args})")

    return call


@pytest.mark.parametrize(("search", "list_height", "box", "expected"), CASES)
def test_placement_picks_the_side_and_its_room(
    placement, search, list_height, box, expected
):
    assert placement(search, list_height, box, GAP) == expected


def test_room_is_never_negative(placement):
    # The search box is taller than the clipping box, so both rooms are -14.
    assert placement(
        {"top": -10, "bottom": 110}, 50, {"top": 0, "bottom": 100}, GAP
    ) == {
        "above": False,
        "room": 0,
    }
