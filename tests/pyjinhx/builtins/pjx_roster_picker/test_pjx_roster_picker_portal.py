"""PJXRosterPicker(portal=True): its open list moves to body, out of every clipping ancestor, and back on close.

Real chromium with the vendored htmx, the committed asset and the CSS:
reparenting, fixed positioning, hit-testing and focus only exist in a
laid-out page with real events. Every picker sits at a known spot in an
800px-wide viewport of known height, and the candidates route answers with
twelve rows, enough to reach the 16rem cap.
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
    from playwright.sync_api import Page, Route

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
FRESH_URL = "http://pjx.test/fresh"
HTMX_TAG = f"<script>{read_vendored_htmx()}</script>"
ASSET_TAG = f"<script>{ASSET}</script>"
# The CSS offset between search box and list at home.
GAP = 4

GEOMETRY = """id => {
    const search = document.querySelector(`#${id} .pjx-roster-picker__search`);
    const box = search.getBoundingClientRect();
    const mount = document.getElementById(`${id}-results`);
    const list = mount.getBoundingClientRect();
    return {
        searchTop: box.top,
        searchBottom: box.bottom,
        searchLeft: box.left,
        searchWidth: box.width,
        listTop: list.top,
        listBottom: list.bottom,
        listLeft: list.left,
        listWidth: list.width,
        above: mount.classList.contains('pjx-roster-picker__results--above'),
        room: mount.style.getPropertyValue('--pjx-roster-picker-room'),
        viewport: window.innerHeight,
        hidden: mount.hidden,
        expanded: document
            .querySelector(`#${id} .pjx-roster-picker__input`)
            .getAttribute('aria-expanded'),
        onBody: mount.parentElement === document.body,
        home: mount.parentElement === search && search.lastElementChild === mount,
        position: getComputedStyle(mount).position,
        inline: ['position', 'left', 'right', 'top', 'bottom', 'width']
            .map((name) => mount.style.getPropertyValue(name))
            .join(''),
    };
}"""

# Hit-tests a point 10px under the #clip box's bottom edge, inside the list.
HIT_BELOW_CLIP = """() => {
    const clip = document.getElementById('clip').getBoundingClientRect();
    const mount = document.getElementById('p-results');
    const list = mount.getBoundingClientRect();
    const y = clip.bottom + 10;
    const hit = document.elementFromPoint(list.left + list.width / 2, y);
    return { listBottom: list.bottom, y: y, inList: mount.contains(hit) };
}"""

CONTROLS = """id => {
    const input = document.querySelector(`#${id} .pjx-roster-picker__input`);
    const target = document.getElementById(input.getAttribute('aria-controls'));
    return {
        isList: target !== null && target.classList.contains('pjx-roster-picker__results'),
        onBody: target !== null && target.parentElement === document.body,
        inPicker: target !== null && document.getElementById(id).contains(target),
        count: document.querySelectorAll(`#${id}-results`).length,
    };
}"""

RECORD_CHANGES = """() => {
    window.changes = [];
    document.addEventListener('pjx:roster-picker:change', (event) => {
        window.changes.push({ values: event.detail.values, target: event.target.id });
    });
}"""

# What an enclosing dialog's own Escape handler would see.
RECORD_WINDOW_ESCAPES = """() => {
    window.escapes = 0;
    window.addEventListener('keydown', (event) => {
        if (event.key === 'Escape') window.escapes += 1;
    });
}"""


def _picker(
    session: RenderSession, picker_id: str = "p", portal: bool = True, **kwargs: Any
) -> str:
    return render(
        PJXRosterPicker(
            id=picker_id,
            name="members",
            candidates_url=CANDIDATES_URL,
            portal=portal,
            **kwargs,
        ),
        session,
    )


def _at(top: int, inner: str, wrapper_id: str = "spot") -> str:
    """inner in a 320px-wide absolutely positioned wrapper whose top edge is at top px."""
    return (
        f'<div id="{wrapper_id}" style="position:absolute; top:{top}px; left:20px;'
        f' width:320px">{inner}</div>'
    )


def _clip(inner: str) -> str:
    """inner in a 60px-tall overflow:hidden box at top:100px, too short to show an open list."""
    return (
        '<div id="clip" style="position:absolute; top:100px; left:20px; width:320px;'
        f' height:60px; overflow:hidden">{inner}</div>'
    )


def _in_box(inner: str, height: int, spacer: int = 0, tail: int = 0) -> str:
    """inner inside an overflow:auto box at top:100px, after spacer px and before tail px of filler."""
    return (
        '<div id="box" style="position:absolute; top:100px; left:20px; width:320px;'
        f' height:{height}px; overflow:auto"><div style="height:{spacer}px"></div>'
        f'{inner}<div style="height:{tail}px"></div></div>'
    )


def _serve(
    page: Page,
    session: RenderSession,
    body: str,
    height: int = 600,
    rows: int = 12,
    css: str = "",
    fresh: str = "",
) -> list[str]:
    """Load body in an 800 x height viewport with the CSS and scripts, and return the candidates request log.

    candidates answers with rows rows; fresh answers with the fresh markup.
    """
    items = [
        PJXRosterItem(value=f"v{index}", label=f"Person {index}")
        for index in range(rows)
    ]
    results = render(PJXRosterResults(picker_id="p", items=items), session)
    html = (
        f"<html><head><style>{CSS}{css}</style></head>"
        f"<body>{body}{HTMX_TAG}{ASSET_TAG}</body></html>"
    )
    requests: list[str] = []

    def candidates(route: Route) -> None:
        requests.append(route.request.url)
        route.fulfill(body=results, content_type="text/html")

    page.set_viewport_size({"width": 800, "height": height})
    page.route(URL, lambda route: route.fulfill(body=html, content_type="text/html"))
    page.route(CANDIDATES, candidates)
    page.route(
        FRESH_URL, lambda route: route.fulfill(body=fresh, content_type="text/html")
    )
    page.goto(URL)
    page.wait_for_function("() => window.htmx")
    return requests


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
    """Viewport rects of the search box and list, the list's side, room, open state and home."""
    return page.evaluate(GEOMETRY, picker_id)


def _px(value: str) -> float:
    assert value.endswith("px"), value
    return float(value[:-2])


def _input_has_focus(page: Page, picker_id: str = "p") -> bool:
    return page.evaluate(
        "id => document.activeElement === document.querySelector(`#${id} .pjx-roster-picker__input`)",
        picker_id,
    )


def _chip_values(page: Page, picker_id: str = "p") -> list[str]:
    return page.evaluate(
        """id => Array.from(
            document.querySelectorAll(
                `#${id} .pjx-roster-picker__chips > [data-pjx-roster-chip] > .pjx-roster-picker__chip-input`
            ),
            (input) => input.value,
        )""",
        picker_id,
    )


def _row_hidden(page: Page, value: str) -> bool:
    """Whether p's result row for value is hidden, wherever the list lives."""
    return page.evaluate(
        'value => document.querySelector(`#p-results [data-value="${value}"]`).hidden',
        value,
    )


def test_overflow_hidden_ancestor_clips_the_list_without_portal(
    page: Page, session: RenderSession, page_errors: list[str]
):
    _serve(page, session, _clip(_picker(session, portal=False)))
    _open(page)

    hit = page.evaluate(HIT_BELOW_CLIP)
    assert _geometry(page)["home"] is True
    # The list reaches past the box's bottom edge, but nothing there can be hit.
    assert hit["listBottom"] > hit["y"]
    assert hit["inList"] is False
    assert page_errors == []


def test_portal_list_escapes_overflow_hidden_ancestor(
    page: Page, session: RenderSession, page_errors: list[str]
):
    _serve(page, session, _clip(_picker(session)))
    _open(page)

    geometry = _geometry(page)
    hit = page.evaluate(HIT_BELOW_CLIP)
    assert geometry["onBody"] is True
    assert geometry["position"] == "fixed"
    assert hit["listBottom"] > hit["y"]
    assert hit["inList"] is True
    assert geometry["above"] is False
    assert geometry["listTop"] == pytest.approx(geometry["searchBottom"] + GAP, abs=1)
    assert geometry["listLeft"] == pytest.approx(geometry["searchLeft"], abs=1)
    assert geometry["listWidth"] == pytest.approx(geometry["searchWidth"], abs=1)
    # Only the viewport bounds it now, not the 60px box.
    assert _px(geometry["room"]) == pytest.approx(
        geometry["viewport"] - geometry["searchBottom"] - GAP, abs=1
    )
    assert page_errors == []


def test_portal_list_returns_home_on_escape(
    page: Page, session: RenderSession, page_errors: list[str]
):
    _serve(page, session, _at(20, _picker(session)))
    _open(page)
    assert _geometry(page)["onBody"] is True
    assert page.evaluate(CONTROLS, "p") == {
        "isList": True,
        "onBody": True,
        "inPicker": False,
        "count": 1,
    }

    page.keyboard.press("Escape")

    geometry = _geometry(page)
    assert geometry["hidden"] is True
    assert geometry["expanded"] == "false"
    assert geometry["home"] is True
    assert geometry["inline"] == ""
    assert geometry["above"] is False
    assert geometry["room"] == ""
    assert page.evaluate(CONTROLS, "p") == {
        "isList": True,
        "onBody": False,
        "inPicker": True,
        "count": 1,
    }
    assert page_errors == []


def test_portal_list_opens_upward_in_viewport_coords(
    page: Page, session: RenderSession, page_errors: list[str]
):
    # The first open places an empty mount below; the rows settling turn it up.
    _serve(page, session, _at(520, _picker(session)))
    _open(page)

    geometry = _geometry(page)
    assert geometry["onBody"] is True
    assert geometry["above"] is True
    assert geometry["listBottom"] == pytest.approx(geometry["searchTop"] - GAP, abs=1)
    assert geometry["listTop"] >= 0
    assert _px(geometry["room"]) == pytest.approx(geometry["searchTop"] - GAP, abs=1)
    assert page_errors == []


def test_portal_list_follows_page_scroll_and_resize(
    page: Page, session: RenderSession, page_errors: list[str]
):
    filler = '<div style="height:2000px"></div>'
    _serve(page, session, filler + _at(300, _picker(session)))
    _open(page)
    before = _geometry(page)

    page.evaluate("() => window.scrollBy(0, 50)")
    _settle(page)

    geometry = _geometry(page)
    assert geometry["searchTop"] == pytest.approx(before["searchTop"] - 50, abs=1)
    assert geometry["above"] is False
    assert geometry["listTop"] == pytest.approx(geometry["searchBottom"] + GAP, abs=1)

    # 450px tall leaves too little room below the box at 250px, so it flips.
    page.set_viewport_size({"width": 800, "height": 450})
    _settle(page)

    geometry = _geometry(page)
    assert geometry["viewport"] == 450
    assert geometry["above"] is True
    assert geometry["listBottom"] == pytest.approx(geometry["searchTop"] - GAP, abs=1)
    assert _px(geometry["room"]) == pytest.approx(geometry["searchTop"] - GAP, abs=1)
    assert page_errors == []


def test_portal_list_follows_ancestor_scroll(
    page: Page, session: RenderSession, page_errors: list[str]
):
    _serve(page, session, _in_box(_picker(session), height=240, spacer=40, tail=400))
    _open(page)
    before = _geometry(page)

    page.evaluate("() => { document.getElementById('box').scrollTop = 30; }")
    _settle(page)

    geometry = _geometry(page)
    assert geometry["searchTop"] == pytest.approx(before["searchTop"] - 30, abs=1)
    assert geometry["above"] is False
    assert geometry["listTop"] == pytest.approx(geometry["searchBottom"] + GAP, abs=1)
    # Measured against the viewport, not the 240px box it no longer sits in.
    assert _px(geometry["room"]) == pytest.approx(
        geometry["viewport"] - geometry["searchBottom"] - GAP, abs=1
    )
    assert page_errors == []


def test_opening_a_second_portal_picker_sends_the_first_list_home(
    page: Page, session: RenderSession, page_errors: list[str]
):
    body = _at(20, _picker(session, "a"), "spot-a") + _at(
        300, _picker(session, "b"), "spot-b"
    )
    _serve(page, session, body)
    _open(page, "a")
    assert _geometry(page, "a")["onBody"] is True

    _open(page, "b")

    first = _geometry(page, "a")
    second = _geometry(page, "b")
    assert first["hidden"] is True
    assert first["home"] is True
    assert first["inline"] == ""
    assert second["onBody"] is True
    assert second["hidden"] is False
    assert page_errors == []


def test_reopening_a_portal_list_over_the_same_text_sends_no_request(
    page: Page, session: RenderSession, page_errors: list[str]
):
    requests = _serve(page, session, _at(20, _picker(session)))
    _open(page)
    page.keyboard.press("Escape")
    assert _geometry(page)["home"] is True

    # The box kept focus through Escape, so only a click reopens it.
    page.locator("#p .pjx-roster-picker__input").click()
    # Past the 300 ms debounce, so a search would have been sent.
    _settle(page)
    page.wait_for_timeout(300)

    geometry = _geometry(page)
    assert geometry["onBody"] is True
    assert geometry["hidden"] is False
    rows = page.evaluate(
        "() => document.querySelectorAll('#p-results [data-pjx-roster-pick]').length"
    )
    assert rows == 12
    assert len(requests) == 1
    assert page_errors == []


def test_portal_list_keeps_a_themed_gap(
    page: Page, session: RenderSession, page_errors: list[str]
):
    # A theme that hangs the list 12px under its box instead of 4px.
    css = ".pjx-roster-picker__results { top: calc(100% + 12px); }"
    _serve(page, session, _at(20, _picker(session)), css=css)
    _open(page)

    geometry = _geometry(page)
    assert geometry["onBody"] is True
    assert geometry["listTop"] == pytest.approx(geometry["searchBottom"] + 12, abs=1)
    assert _px(geometry["room"]) == pytest.approx(
        geometry["viewport"] - geometry["searchBottom"] - 12, abs=1
    )
    assert page_errors == []


def test_pick_from_portal_list(
    page: Page, session: RenderSession, page_errors: list[str]
):
    _serve(page, session, _clip(_picker(session)))
    _open(page)
    page.evaluate(RECORD_CHANGES)
    assert _geometry(page)["onBody"] is True

    page.click('#p-results [data-pjx-roster-pick][data-value="v2"]')
    _settle(page)

    assert _chip_values(page) == ["v2"]
    name = page.evaluate(
        "() => document.querySelector('#p .pjx-roster-picker__chip-input').name"
    )
    assert name == "members"
    assert page.evaluate("() => window.changes") == [{"values": ["v2"], "target": "p"}]
    geometry = _geometry(page)
    assert geometry["hidden"] is True
    assert geometry["home"] is True
    assert geometry["inline"] == ""
    assert _row_hidden(page, "v2") is True
    assert _input_has_focus(page)
    assert page_errors == []


def test_arrow_down_and_escape_from_portal_row(
    page: Page, session: RenderSession, page_errors: list[str]
):
    _serve(page, session, _at(20, _picker(session)))
    page.evaluate(RECORD_WINDOW_ESCAPES)
    _open(page)

    page.keyboard.press("ArrowDown")
    _settle(page)

    first_row_focused = page.evaluate(
        "() => document.activeElement"
        " === document.querySelector('#p-results [data-pjx-roster-pick]:not([hidden])')"
    )
    assert first_row_focused is True
    geometry = _geometry(page)
    assert geometry["onBody"] is True
    assert geometry["hidden"] is False

    page.keyboard.press("Escape")

    geometry = _geometry(page)
    assert geometry["hidden"] is True
    assert geometry["home"] is True
    assert _input_has_focus(page)
    assert page.evaluate("() => window.escapes") == 0
    assert page_errors == []


def test_focus_leaving_portal_list_closes_it(
    page: Page, session: RenderSession, page_errors: list[str]
):
    after = '<button id="after" type="button">After</button>'
    _serve(page, session, _at(20, _picker(session) + after))
    _open(page)
    page.keyboard.press("ArrowDown")
    page.keyboard.press("Tab")
    _settle(page)

    # Tab moved between rows of the box's own list, which is not leaving.
    second_row_focused = page.evaluate(
        "() => document.activeElement"
        " === document.querySelectorAll('#p-results [data-pjx-roster-pick]')[1]"
    )
    assert second_row_focused is True
    assert _geometry(page)["hidden"] is False

    # The rows sit last on body, so a Tab past them leaves the page; focus()
    # moves to a control after the picker, as a press-free Tab would.
    page.locator("#after").focus()
    _settle(page)

    geometry = _geometry(page)
    assert geometry["hidden"] is True
    assert geometry["home"] is True
    assert geometry["inline"] == ""
    assert page_errors == []


def test_chipped_row_hidden_in_portal_list(
    page: Page, session: RenderSession, page_errors: list[str]
):
    picker = _picker(session, items=[PJXRosterItem(value="v1", label="Person 1")])
    _serve(page, session, _at(20, picker))
    _open(page)

    rows = page.evaluate(
        "() => Array.from(document.querySelectorAll('#p-results [data-pjx-roster-pick]'),"
        " (row) => [row.dataset.value, row.hidden])"
    )
    assert _geometry(page)["onBody"] is True
    assert [value for value, hidden in rows if hidden] == ["v1"]
    assert len(rows) == 12
    assert page_errors == []


def test_removing_a_chip_unhides_its_row_in_portal_list(
    page: Page, session: RenderSession, page_errors: list[str]
):
    # At 400px the list opens above the box, so it does not cover the chip.
    picker = _picker(session, items=[PJXRosterItem(value="v1", label="Person 1")])
    _serve(page, session, _at(400, picker))
    _open(page)
    assert _geometry(page)["above"] is True
    assert _row_hidden(page, "v1") is True

    page.click("#p [data-pjx-roster-remove]")
    _settle(page)

    assert _chip_values(page) == []
    assert _row_hidden(page, "v1") is False
    assert _geometry(page)["home"] is True
    assert page_errors == []


def test_a_click_on_the_portal_lists_padding_keeps_it_open(
    page: Page, session: RenderSession, page_errors: list[str]
):
    requests = _serve(
        page, session, _at(20, _picker(session)), css="#p-results { padding: 40px; }"
    )
    _open(page)
    box = page.locator("#p-results").bounding_box()
    assert box is not None

    page.mouse.click(box["x"] + box["width"] / 2, box["y"] + 8)
    # Past the 300 ms debounce, so a reopen's search would have been sent.
    _settle(page)
    page.wait_for_timeout(300)

    geometry = _geometry(page)
    assert geometry["hidden"] is False
    assert geometry["onBody"] is True
    assert _input_has_focus(page)
    assert len(requests) == 1
    assert page_errors == []


def test_htmx_swap_of_portaled_picker_leaves_no_stray_list(
    page: Page, session: RenderSession, page_errors: list[str]
):
    markup = _picker(session)
    _serve(page, session, _at(20, markup), fresh=markup)
    # Opened by typing, not focus: a focused box removed by the swap could
    # close the list through focusout and hide a missing cleanup.
    page.evaluate(
        "() => document.querySelector('#p .pjx-roster-picker__input')"
        ".dispatchEvent(new Event('input', { bubbles: true }))"
    )
    page.wait_for_selector("#p-results [data-pjx-roster-pick]", timeout=5000)
    _settle(page)
    assert _geometry(page)["onBody"] is True

    page.evaluate(
        "() => htmx.ajax('GET', '/fresh', { target: '#spot', swap: 'innerHTML' })"
    )
    _settle(page)

    lists = page.evaluate(
        """() => ({
            count: document.querySelectorAll('#p-results').length,
            inPicker: document.getElementById('p').contains(document.getElementById('p-results')),
            onBody: document.querySelectorAll('body > .pjx-roster-picker__results').length,
        })"""
    )
    assert lists == {"count": 1, "inPicker": True, "onBody": 0}
    assert _geometry(page)["hidden"] is True
    assert page_errors == []
