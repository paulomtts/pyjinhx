"""PJXRosterPicker placement: which side of the search box its list opens on, and how tall it may grow.

Real chromium with the vendored htmx, the committed asset and the CSS: the
clipping-box walk, the measured gap and the CSS clamp only exist in a
laid-out page. Every picker sits at a known spot in an 800px-wide viewport
of known height, and the candidates route answers with enough rows to reach
the 16rem cap.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

import pytest

from pyjinhx.builtins.ui.pjx_roster_picker import PJXRosterItem, PJXRosterPicker
from pyjinhx.builtins.ui.pjx_roster_results import PJXRosterResults
from pyjinhx.client import read_vendored_htmx
from pyjinhx.rendering import render

if TYPE_CHECKING:
    from playwright.sync_api import Page

    from pyjinhx.session import RenderSession

PICKER_DIR = (
    Path(__file__).resolve().parents[4]
    / "pyjinhx"
    / "builtins"
    / "ui"
    / "pjx_roster_picker"
)
CSS = (PICKER_DIR / "pjx_roster_picker.css").read_text(encoding="utf-8")
ASSET = (PICKER_DIR / "pjx_roster_picker.js").read_text(encoding="utf-8")
URL = "http://pjx.test/"
CANDIDATES_URL = "http://pjx.test/candidates"
CANDIDATES = "http://pjx.test/candidates*"
HTMX_TAG = f"<script>{read_vendored_htmx()}</script>"
ASSET_TAG = f"<script>{ASSET}</script>"
# The CSS offset between search box and list, which the script measures.
GAP = 4
# --pjx-roster-picker-max-h (16rem) at the default 16px font size.
MAX_H = 256

GEOMETRY = """id => {
    const search = document.querySelector(`#${id} .pjx-roster-picker__search`).getBoundingClientRect();
    const mount = document.getElementById(`${id}-results`);
    const list = mount.getBoundingClientRect();
    return {
        searchTop: search.top,
        searchBottom: search.bottom,
        listTop: list.top,
        listBottom: list.bottom,
        listHeight: list.height,
        above: mount.classList.contains('pjx-roster-picker__results--above'),
        room: mount.style.getPropertyValue('--pjx-roster-picker-room'),
        scrolls: mount.scrollHeight > mount.clientHeight,
        viewport: window.innerHeight,
    };
}"""


def _picker(session: RenderSession, picker_id: str = "p", **kwargs: Any) -> str:
    return render(
        PJXRosterPicker(
            id=picker_id, name="members", candidates_url=CANDIDATES_URL, **kwargs
        ),
        session,
    )


def _at(top: int, inner: str, wrapper_id: str = "spot") -> str:
    """inner in a 320px-wide absolutely positioned wrapper whose top edge is at top px."""
    return (
        f'<div id="{wrapper_id}" style="position:absolute; top:{top}px; left:20px;'
        f' width:320px">{inner}</div>'
    )


def _in_box(inner: str, height: int, spacer: int = 0, tail: int = 0) -> str:
    """inner inside an overflow:auto box at top:100px, after spacer px and before tail px of filler."""
    return (
        '<div id="box" style="position:absolute; top:100px; left:20px; width:320px;'
        f' height:{height}px; overflow:auto"><div style="height:{spacer}px"></div>'
        f'{inner}<div style="height:{tail}px"></div></div>'
    )


def _serve(
    page: Page, session: RenderSession, body: str, height: int = 600, rows: int = 12
) -> None:
    """Load body in an 800 x height viewport with the CSS and scripts; candidates answers with rows rows."""
    items = [
        PJXRosterItem(value=f"v{index}", label=f"Person {index}")
        for index in range(rows)
    ]
    results = render(PJXRosterResults(picker_id="p", items=items), session)
    html = f"<html><head><style>{CSS}</style></head><body>{body}{HTMX_TAG}{ASSET_TAG}</body></html>"
    page.set_viewport_size({"width": 800, "height": height})
    page.route(URL, lambda route: route.fulfill(body=html, content_type="text/html"))
    page.route(
        CANDIDATES,
        lambda route: route.fulfill(body=results, content_type="text/html"),
    )
    page.goto(URL)
    page.wait_for_function("() => window.htmx")


def _settle(page: Page) -> None:
    """Let two animation frames and a short beat pass, so a pending handler has run."""
    page.evaluate(
        "() => new Promise((done) => requestAnimationFrame(() => requestAnimationFrame(done)))"
    )
    # There is no event for "did not fire", so proving a negative needs a beat.
    page.wait_for_timeout(200)


def _open(page: Page, picker_id: str = "p") -> None:
    """Click the search box, wait for its rows, and let the placement that follows them run."""
    page.locator(f"#{picker_id} .pjx-roster-picker__input").click()
    page.wait_for_function(
        "id => document.querySelector(`#${id}-results [data-pjx-roster-pick]`) !== null",
        arg=picker_id,
        timeout=5000,
    )
    _settle(page)


def _geometry(page: Page, picker_id: str = "p") -> dict[str, Any]:
    """Viewport rects of the search box and list, the list's side and inline room."""
    return page.evaluate(GEOMETRY, picker_id)


def _box(page: Page) -> dict[str, float]:
    """The viewport top and bottom of the #box overflow ancestor."""
    return page.evaluate(
        "() => { const r = document.getElementById('box').getBoundingClientRect();"
        " return { top: r.top, bottom: r.bottom }; }"
    )


def _px(value: str) -> float:
    assert value.endswith("px"), value
    return float(value[:-2])


def test_opens_below_with_room(
    page: Page, session: RenderSession, page_errors: list[str]
):
    _serve(page, session, _at(20, _picker(session)))
    _open(page)

    geometry = _geometry(page)
    assert geometry["above"] is False
    assert geometry["listTop"] >= geometry["searchBottom"]
    assert geometry["listBottom"] <= geometry["viewport"]
    assert _px(geometry["room"]) == pytest.approx(
        geometry["viewport"] - geometry["searchBottom"] - GAP, abs=1
    )
    assert page_errors == []


def test_opens_upward_when_short_below_and_roomier_above(
    page: Page, session: RenderSession, page_errors: list[str]
):
    # The first open measures an empty mount, which fits below; only the
    # re-place once the rows settle can turn it upward.
    _serve(page, session, _at(520, _picker(session)))
    _open(page)

    geometry = _geometry(page)
    assert geometry["above"] is True
    assert geometry["listBottom"] <= geometry["searchTop"]
    assert geometry["listTop"] >= 0
    assert _px(geometry["room"]) == pytest.approx(geometry["searchTop"] - GAP, abs=1)
    assert page_errors == []


def test_height_is_capped_to_the_room(
    page: Page, session: RenderSession, page_errors: list[str]
):
    # 300px tall with the search box near the middle: neither side fits the
    # 16rem list.
    _serve(page, session, _at(130, _picker(session)), height=300)
    _open(page)

    geometry = _geometry(page)
    room = _px(geometry["room"])
    assert room < MAX_H
    assert room == pytest.approx(
        max(geometry["viewport"] - geometry["searchBottom"], geometry["searchTop"])
        - GAP,
        abs=1,
    )
    assert geometry["listHeight"] == pytest.approx(room, abs=1)
    assert geometry["scrolls"] is True
    assert geometry["listTop"] >= 0
    assert geometry["listBottom"] <= geometry["viewport"] + 0.5
    assert page_errors == []


def test_list_inside_an_overflow_auto_ancestor(
    page: Page, session: RenderSession, page_errors: list[str]
):
    # The box ends at 340px with the search box near its bottom; the viewport
    # alone would leave room below.
    _serve(page, session, _in_box(_picker(session), height=240, spacer=180))
    _open(page)

    geometry = _geometry(page)
    box = _box(page)
    assert geometry["above"] is True
    assert _px(geometry["room"]) == pytest.approx(
        geometry["searchTop"] - box["top"] - GAP, abs=1
    )
    assert geometry["listTop"] >= box["top"] - 0.5
    assert page_errors == []


def test_closing_clears_the_placement(
    page: Page, session: RenderSession, page_errors: list[str]
):
    _serve(page, session, _at(520, _picker(session)))
    _open(page)
    assert _geometry(page)["above"] is True

    page.keyboard.press("Escape")

    geometry = _geometry(page)
    assert geometry["above"] is False
    assert geometry["room"] == ""
    assert page_errors == []


def test_floor_holds_when_room_is_tiny(
    page: Page, session: RenderSession, page_errors: list[str]
):
    _serve(page, session, _in_box(_picker(session), height=60))
    _open(page)

    assert _px(_geometry(page)["room"]) < 48
    max_height = page.evaluate(
        "() => getComputedStyle(document.getElementById('p-results')).maxHeight"
    )
    # 3rem at the default 16px font size.
    assert max_height == "48px"
    assert page_errors == []


def test_a_body_that_sets_overflow_does_not_shrink_the_room(
    page: Page, session: RenderSession, page_errors: list[str]
):
    # The body holds only an absolutely positioned wrapper, so its own rect
    # is 0px tall: counted as a clipping box it would leave no room at all.
    style = "<style>html, body { overflow-y: auto; }</style>"
    _serve(page, session, style + _at(20, _picker(session)))
    _open(page)

    geometry = _geometry(page)
    assert geometry["above"] is False
    assert _px(geometry["room"]) == pytest.approx(
        geometry["viewport"] - geometry["searchBottom"] - GAP, abs=1
    )
    assert page_errors == []


def test_reopening_by_typing_places_the_list_afresh(
    page: Page, session: RenderSession, page_errors: list[str]
):
    _serve(page, session, _at(520, _picker(session)))
    _open(page)
    assert _geometry(page)["above"] is True
    page.keyboard.press("Escape")
    page.evaluate("() => { document.getElementById('spot').style.top = '20px'; }")

    # Escape left focus in the search box, so typing reopens through the
    # input listener.
    with page.expect_request(CANDIDATES, timeout=5000):
        page.keyboard.type("P")
    _settle(page)

    geometry = _geometry(page)
    assert geometry["above"] is False
    assert _px(geometry["room"]) == pytest.approx(
        geometry["viewport"] - geometry["searchBottom"] - GAP, abs=1
    )
    assert page_errors == []


def test_placed_again_after_resize(
    page: Page, session: RenderSession, page_errors: list[str]
):
    _serve(page, session, _at(280, _picker(session)))
    _open(page)
    assert _geometry(page)["above"] is False

    page.set_viewport_size({"width": 800, "height": 450})
    _settle(page)

    geometry = _geometry(page)
    assert geometry["above"] is True
    assert _px(geometry["room"]) == pytest.approx(geometry["searchTop"] - GAP, abs=1)
    assert page_errors == []


def test_ancestor_scroll_replaces_and_list_scroll_does_not(
    page: Page, session: RenderSession, page_errors: list[str]
):
    _serve(page, session, _in_box(_picker(session), height=240, spacer=180, tail=400))
    _open(page)
    before = _px(_geometry(page)["room"])

    page.evaluate("() => { document.getElementById('box').scrollTop = 60; }")
    _settle(page)

    geometry = _geometry(page)
    box = _box(page)
    assert geometry["above"] is True
    assert _px(geometry["room"]) == pytest.approx(
        geometry["searchTop"] - box["top"] - GAP, abs=1
    )
    assert _px(geometry["room"]) < before - 30

    # A room no placement would write, so only a re-place could change it.
    page.evaluate(
        "() => document.getElementById('p-results')"
        ".style.setProperty('--pjx-roster-picker-room', '77px')"
    )
    page.evaluate("() => { document.getElementById('p-results').scrollTop = 30; }")
    _settle(page)

    assert page.evaluate("() => document.getElementById('p-results').scrollTop") == 30
    assert _geometry(page)["room"] == "77px"
    assert page_errors == []


def test_page_scroll_replaces_the_list(
    page: Page, session: RenderSession, page_errors: list[str]
):
    # A tall page, so the window itself scrolls; that scroll targets
    # document, which has no closest.
    filler = '<div style="height:2000px"></div>'
    _serve(page, session, filler + _at(300, _picker(session)))
    _open(page)
    before = _px(_geometry(page)["room"])

    page.evaluate("() => window.scrollTo(0, 200)")
    _settle(page)

    geometry = _geometry(page)
    assert geometry["above"] is False
    assert _px(geometry["room"]) == pytest.approx(
        geometry["viewport"] - geometry["searchBottom"] - GAP, abs=1
    )
    assert _px(geometry["room"]) > before + 150
    assert page_errors == []


def test_resize_replaces_every_open_picker_and_skips_a_disabled_one(
    page: Page, session: RenderSession, page_errors: list[str]
):
    body = (
        _at(20, _picker(session, "a"), "spot-a")
        + _at(380, _picker(session, "b"), "spot-b")
        + _at(470, _picker(session, "d", disabled=True), "spot-d")
    )
    _serve(page, session, body)
    _open(page, "a")
    _open(page, "b")
    assert _geometry(page, "a")["above"] is False
    assert _geometry(page, "b")["above"] is True

    page.set_viewport_size({"width": 800, "height": 900})
    _settle(page)

    for picker_id in ("a", "b"):
        geometry = _geometry(page, picker_id)
        assert geometry["above"] is False, picker_id
        assert _px(geometry["room"]) == pytest.approx(
            geometry["viewport"] - geometry["searchBottom"] - GAP, abs=1
        ), picker_id
    assert page_errors == []
