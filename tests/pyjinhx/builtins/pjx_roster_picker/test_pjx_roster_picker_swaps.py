"""PJXRosterPicker under real htmx swaps, in real chromium with the vendored htmx.

Every page loads the committed pjx_roster_picker.js, so these tests exercise
the asset that ships. Each swap is a real htmx.ajax request whose response
is routed: a freshly rendered picker for the whole picker, a rendered chip
(or nothing) for one chip, a results page for the list. The candidates stub
logs each request URL and answers with three people, v0 to v2, whatever
exclude says. An event recorder logs every pjx:roster-picker:* event the
page hears. A swap is awaited on its DOM result; a negative is proven by
letting a beat pass and checking nothing changed.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING, Any
from urllib.parse import parse_qs, urlsplit

import pytest

from pyjinhx.builtins.ui.pjx_roster_chip import PJXRosterChip
from pyjinhx.builtins.ui.pjx_roster_picker import PJXRosterItem, PJXRosterPicker
from pyjinhx.builtins.ui.pjx_roster_results import PJXRosterResults
from pyjinhx.client import read_vendored_htmx
from pyjinhx.rendering import render

if TYPE_CHECKING:
    from playwright.sync_api import Locator, Page, Route

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
SWAP_URL = "http://pjx.test/swap"
MORE_URL = "http://pjx.test/more"
HTMX_TAG = f"<script>{read_vendored_htmx()}</script>"
ASSET_TAG = f"<script>{ASSET}</script>"
OPEN = ("true", False)
CLOSED = ("false", True)
CHIP = (
    "#p .pjx-roster-picker__chips > [data-pjx-roster-chip]"
    ':has(> .pjx-roster-picker__chip-input[value="{value}"])'
)

# Listens on document, so every event the picker fires is heard wherever it
# starts. connected tells a live picker from one a swap took away.
RECORD_EVENTS = """() => {
    window.events = [];
    for (const name of ['before-pick', 'pick', 'before-remove', 'remove', 'change']) {
        document.addEventListener(`pjx:roster-picker:${name}`, (event) => {
            window.events.push({
                name: name,
                target: event.target.id,
                connected: event.target.isConnected,
            });
        });
    }
}"""

# The target is an element, not a selector, as an app swapping one chip
# would pass it.
SWAP = """([selector, swap]) => htmx.ajax('GET', '/swap', {
    target: document.querySelector(selector),
    swap: swap,
})"""


def _picker(session: RenderSession, picker_id: str = "p", **kwargs: Any) -> str:
    return render(
        PJXRosterPicker(
            id=picker_id, name="members", candidates_url=CANDIDATES_URL, **kwargs
        ),
        session,
    )


def _item(value: str) -> PJXRosterItem:
    return PJXRosterItem(value=value, label=value.upper())


def _items(*values: str) -> list[PJXRosterItem]:
    return [_item(value) for value in values]


def _chip(session: RenderSession, value: str, label: str | None = None) -> str:
    """A chip as an app re-renders it: its own id, named for the picker."""
    return render(
        PJXRosterChip(
            id=f"chip-{value}",
            value=value,
            label=label or value.upper(),
            name="members",
        ),
        session,
    )


def _answer(body: str) -> Callable[[Route], None]:
    # One parameter: page.route passes a handler (route, request) when it takes two.
    return lambda route: route.fulfill(body=body, content_type="text/html")


def _serve(
    page: Page,
    session: RenderSession,
    body: str,
    *,
    swap: str = "",
    rows: str | None = None,
) -> list[str]:
    """Load body with the CSS and scripts, answer /swap with swap and every search with rows, return the search log."""
    if rows is None:
        rows = render(
            PJXRosterResults(picker_id="p", items=_items("v0", "v1", "v2")), session
        )
    answer = rows
    html = (
        f'<html><head><meta charset="utf-8"><style>{CSS}</style></head>'
        f"<body>{body}{HTMX_TAG}{ASSET_TAG}</body></html>"
    )
    requests: list[str] = []

    def candidates(route: Route) -> None:
        requests.append(route.request.url)
        route.fulfill(body=answer, content_type="text/html")

    page.route(URL, _answer(html))
    page.route(CANDIDATES, candidates)
    page.route(SWAP_URL, _answer(swap))
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


def _swap(page: Page, selector: str, swap: str) -> None:
    """Swap /swap's answer into the element selector finds, through htmx.ajax."""
    page.evaluate(SWAP, [selector, swap])


def _input(page: Page, picker_id: str = "p") -> Locator:
    return page.locator(f"#{picker_id} .pjx-roster-picker__input")


def _state(page: Page, picker_id: str = "p") -> tuple[str, bool]:
    """The input's aria-expanded and the mount's hidden, which must agree."""
    expanded, hidden = page.evaluate(
        """id => [
            document.querySelector(`#${id} .pjx-roster-picker__input`).getAttribute('aria-expanded'),
            document.getElementById(`${id}-results`).hidden,
        ]""",
        picker_id,
    )
    return expanded, hidden


def _open(page: Page, picker_id: str = "p") -> None:
    """Click the box and wait until the first search's rows are in.

    Attached, not visible: a row for a chipped value arrives hidden."""
    _input(page, picker_id).click()
    page.wait_for_selector(
        f"#{picker_id}-results [data-pjx-roster-pick]",
        state="attached",
        timeout=5000,
    )
    page.wait_for_function(
        "id => document.querySelector(`#${id} .pjx-roster-picker__input`)"
        ".getAttribute('data-last-query') === ''",
        arg=picker_id,
        timeout=5000,
    )


def _close_by_blur(page: Page) -> None:
    """Take focus off the box, which closes the list and keeps its rows."""
    page.evaluate("() => document.activeElement.blur()")
    _settle(page)


def _pick(page: Page, value: str, picker_id: str = "p") -> Locator:
    return page.locator(
        f'#{picker_id}-results [data-pjx-roster-pick][data-value="{value}"]'
    )


def _values(page: Page, picker_id: str = "p") -> list[str]:
    """The selection as the public API reads it."""
    return page.evaluate(
        "id => pjx.rosterPicker.values(document.getElementById(id))", picker_id
    )


def _wait_values(page: Page, expected: list[str], picker_id: str = "p") -> None:
    page.wait_for_function(
        "([id, expected]) => JSON.stringify(pjx.rosterPicker.values("
        "document.getElementById(id))) === JSON.stringify(expected)",
        arg=[picker_id, expected],
        timeout=5000,
    )


def _hidden_rows(page: Page, picker_id: str = "p") -> dict[str, bool]:
    """Each result row's value mapped to its hidden flag."""
    return page.evaluate(
        """id => Object.fromEntries(Array.from(
            document.querySelectorAll(`#${id}-results [data-pjx-roster-pick]`),
            (row) => [row.dataset.value, row.hidden]
        ))""",
        picker_id,
    )


def _row_values(page: Page, picker_id: str = "p") -> list[str]:
    return page.eval_on_selector_all(
        f"#{picker_id}-results [data-pjx-roster-pick]",
        "rows => rows.map((row) => row.dataset.value)",
    )


def _hint_hidden(page: Page, picker_id: str = "p") -> bool:
    return page.evaluate(
        "id => document.querySelector(`#${id} .pjx-roster-picker__hint`).hidden",
        picker_id,
    )


def _validity(page: Page, picker_id: str = "p") -> str:
    return page.evaluate(
        "id => document.querySelector(`#${id} > .pjx-roster-picker__validity`).value",
        picker_id,
    )


def _has_focus(locator: Locator) -> bool:
    return locator.evaluate("el => el === document.activeElement")


def _focus_in_picker(page: Page, picker_id: str = "p") -> bool:
    """Whether focus is in the picker's search box or its list, wherever the list lives."""
    return page.evaluate(
        """id => {
            const active = document.activeElement;
            return document.querySelector(`#${id} .pjx-roster-picker__search`).contains(active)
                || document.getElementById(`${id}-results`).contains(active);
        }""",
        picker_id,
    )


def _record_events(page: Page) -> None:
    page.evaluate(RECORD_EVENTS)


def _events(page: Page) -> list[dict[str, Any]]:
    return page.evaluate("() => window.events")


def _exclude(url: str) -> list[str]:
    return parse_qs(urlsplit(url).query, keep_blank_values=True)["exclude"]


@pytest.mark.parametrize("old_state", ["open", "closed"])
def test_whole_picker_swap_starts_closed_and_agrees_with_its_chips(
    page: Page, session: RenderSession, page_errors: list[str], old_state: str
):
    fresh = _picker(session, items=_items("v1", "v2"), max_items=2, required=True)
    requests = _serve(
        page,
        session,
        _picker(session, items=_items("v0"), max_items=3, required=True),
        swap=fresh,
    )
    if old_state == "open":
        _open(page)
    sent = len(requests)

    _swap(page, "#p", "outerHTML")
    _wait_values(page, ["v1", "v2"])
    _settle(page)

    counts = page.evaluate(
        """() => [
            document.querySelectorAll('#p').length,
            document.querySelectorAll('#p-results').length,
            document.getElementById('p-results').childElementCount,
        ]"""
    )
    assert counts == [1, 1, 0]
    assert _state(page) == CLOSED
    assert _input(page).is_disabled()
    assert _hint_hidden(page) is False
    assert _validity(page) == "v1,v2"
    assert not _has_focus(_input(page))
    # Past the 300 ms debounce, so an open's search would have been sent.
    page.wait_for_timeout(300)
    assert len(requests) == sent
    assert page_errors == []


def test_whole_picker_swap_forgets_the_kept_query_and_excludes_new_chips(
    page: Page, session: RenderSession, page_errors: list[str]
):
    requests = _serve(
        page,
        session,
        _picker(session, items=_items("v0")),
        swap=_picker(session, items=_items("v1")),
    )
    _open(page)
    _swap(page, "#p", "outerHTML")
    _wait_values(page, ["v1"])
    _settle(page)
    sent = len(requests)

    _open(page)
    # Past the 300 ms debounce, so a second search would have been sent.
    page.wait_for_timeout(500)

    assert len(requests) == sent + 1
    assert _exclude(requests[-1]) == ["v1"]
    assert _hidden_rows(page) == {"v0": False, "v1": True, "v2": False}
    assert page_errors == []


def test_a_pick_in_a_swapped_in_picker_works_without_rebinding(
    page: Page, session: RenderSession, page_errors: list[str]
):
    _serve(
        page,
        session,
        _picker(session, items=_items("v0")),
        swap=_picker(session, items=_items("v1")),
    )
    _swap(page, "#p", "outerHTML")
    _wait_values(page, ["v1"])
    _open(page)
    _record_events(page)

    _pick(page, "v0").click()

    assert _values(page) == ["v1", "v0"]
    assert _hidden_rows(page) == {"v0": True, "v1": True, "v2": False}
    assert _state(page) == CLOSED
    assert _events(page) == [
        {"name": "before-pick", "target": "p", "connected": True},
        {"name": "pick", "target": "p", "connected": True},
        {"name": "change", "target": "p", "connected": True},
    ]
    assert page_errors == []


def test_outer_swap_of_an_open_portal_picker_leaves_no_list_on_body(
    page: Page, session: RenderSession, page_errors: list[str]
):
    _serve(
        page,
        session,
        _picker(session, items=_items("v0"), portal=True),
        swap=_picker(session, items=_items("v1"), portal=True),
    )
    # Opened by typing, not focus: a focused box removed by the swap could
    # close the list through focusout and hide a missing cleanup.
    page.evaluate(
        "() => document.querySelector('#p .pjx-roster-picker__input')"
        ".dispatchEvent(new Event('input', { bubbles: true }))"
    )
    page.wait_for_selector(
        "#p-results [data-pjx-roster-pick]", state="attached", timeout=5000
    )
    _settle(page)
    assert page.evaluate(
        "() => document.getElementById('p-results').parentElement === document.body"
    )

    _swap(page, "#p", "outerHTML")
    _wait_values(page, ["v1"])
    _settle(page)

    lists = page.evaluate(
        """() => ({
            onBody: document.querySelectorAll('body > .pjx-roster-picker__results').length,
            count: document.querySelectorAll('#p-results').length,
            inPicker: document.getElementById('p').contains(document.getElementById('p-results')),
        })"""
    )
    assert lists == {"onBody": 0, "count": 1, "inPicker": True}
    assert _state(page) == CLOSED
    assert page_errors == []


def test_a_chip_rerendered_with_its_value_keeps_the_selection(
    page: Page, session: RenderSession, page_errors: list[str]
):
    requests = _serve(
        page,
        session,
        _picker(session, items=_items("v0", "v1"), max_items=3, required=True),
        swap=_chip(session, "v0", label="Renamed"),
    )
    _open(page)
    _close_by_blur(page)
    sent = len(requests)
    _record_events(page)

    _swap(page, CHIP.format(value="v0"), "outerHTML")
    page.wait_for_selector("#chip-v0", timeout=5000)
    _settle(page)

    assert _values(page) == ["v0", "v1"]
    assert (
        page.locator("#chip-v0 .pjx-roster-picker__chip-label").inner_text()
        == "Renamed"
    )
    assert _hidden_rows(page) == {"v0": True, "v1": True, "v2": False}
    assert _state(page) == CLOSED
    assert not _input(page).is_disabled()
    assert _hint_hidden(page) is True
    assert _validity(page) == "v0,v1"
    assert _events(page) == []
    assert not _has_focus(_input(page))
    # Past the 300 ms debounce, so an open's search would have been sent.
    page.wait_for_timeout(300)
    assert len(requests) == sent
    assert page_errors == []


def test_a_results_page_swapped_into_an_open_list_hides_chipped_rows(
    page: Page, session: RenderSession, page_errors: list[str]
):
    results = render(
        PJXRosterResults(picker_id="p", items=_items("v0", "v3", "v4")), session
    )
    _serve(page, session, _picker(session, items=_items("v0")), swap=results)
    _open(page)

    _swap(page, "#p-results", "innerHTML")
    page.wait_for_selector(
        '#p-results [data-value="v3"]', state="attached", timeout=5000
    )
    _settle(page)

    assert _hidden_rows(page) == {"v0": True, "v3": False, "v4": False}
    assert _state(page) == OPEN
    assert _has_focus(_input(page))

    _record_events(page)
    _pick(page, "v3").click()

    assert _values(page) == ["v0", "v3"]
    assert _hidden_rows(page) == {"v0": True, "v3": True, "v4": False}
    assert _state(page) == CLOSED
    assert [event["name"] for event in _events(page)] == [
        "before-pick",
        "pick",
        "change",
    ]
    assert page_errors == []


def test_a_results_page_swapped_into_a_closed_list_stays_closed(
    page: Page, session: RenderSession, page_errors: list[str]
):
    results = render(PJXRosterResults(picker_id="p", items=_items("v0", "v3")), session)
    _serve(page, session, _picker(session, items=_items("v0")), swap=results)

    _swap(page, "#p-results", "innerHTML")
    page.wait_for_selector(
        '#p-results [data-value="v3"]', state="attached", timeout=5000
    )
    _settle(page)

    assert _state(page) == CLOSED
    assert _hidden_rows(page) == {"v0": True, "v3": False}
    assert page_errors == []


def test_a_results_swap_under_a_focused_row_does_not_strand_an_open_list(
    page: Page, session: RenderSession, page_errors: list[str]
):
    results = render(PJXRosterResults(picker_id="p", items=_items("v0", "v3")), session)
    _serve(page, session, _picker(session, items=_items("v0")), swap=results)
    _open(page)
    _input(page).press("ArrowDown")
    assert _has_focus(_pick(page, "v1"))

    _swap(page, "#p-results", "innerHTML")
    page.wait_for_selector(
        '#p-results [data-value="v3"]', state="attached", timeout=5000
    )
    _settle(page)

    assert _state(page) == CLOSED or _focus_in_picker(page)
    page.mouse.click(700, 500)
    _settle(page)
    assert _state(page) == CLOSED
    assert page_errors == []


def _paged(
    page: Page, session: RenderSession, first_rows: int, chipped: str
) -> list[str]:
    """Serve a picker chipping chipped, whose search answers first_rows rows a0.. and a sentinel for b0 and b1."""
    first = PJXRosterResults(
        picker_id="p",
        items=_items(*(f"a{index}" for index in range(first_rows))),
        next_url=f"{MORE_URL}?cursor=2",
        next_cursor="2",
    )
    second = render(PJXRosterResults(picker_id="p", items=_items("b0", "b1")), session)
    requests = _serve(
        page,
        session,
        _picker(session, items=_items(chipped)),
        rows=render(first, session),
    )
    page.route(f"{MORE_URL}*", _answer(second))
    return requests


def test_a_lazy_next_page_arrives_with_chipped_rows_hidden_and_focus_kept(
    page: Page, session: RenderSession, page_errors: list[str]
):
    # Thirty rows overflow the list, so the sentinel waits for a scroll.
    _paged(page, session, first_rows=30, chipped="b1")
    _open(page)
    _settle(page)
    assert page.locator("#p-more-2").count() == 1
    _input(page).press("ArrowDown")
    assert _has_focus(_pick(page, "a0"))
    # Overwritten so a value the page lands with proves it was placed again.
    page.evaluate(
        "() => document.getElementById('p-results').style"
        ".setProperty('--pjx-roster-picker-room', '123px')"
    )

    with page.expect_request(f"{MORE_URL}*", timeout=5000):
        page.evaluate(
            "() => { const list = document.getElementById('p-results');"
            " list.scrollTop = list.scrollHeight; }"
        )
    page.wait_for_selector(
        '#p-results [data-value="b1"]', state="attached", timeout=5000
    )
    _settle(page)

    assert page.locator("#p-more-2").count() == 0
    assert _row_values(page) == [f"a{index}" for index in range(30)] + ["b0", "b1"]
    hidden = _hidden_rows(page)
    assert hidden["b1"] is True
    assert [value for value, flag in hidden.items() if flag] == ["b1"]
    assert _state(page) == OPEN
    room = page.evaluate(
        "() => document.getElementById('p-results').style"
        ".getPropertyValue('--pjx-roster-picker-room')"
    )
    assert room.endswith("px")
    assert room != "123px"
    assert _has_focus(_pick(page, "a0"))
    assert page_errors == []


def test_a_pick_from_a_lazy_next_page_is_excluded_from_the_next_search(
    page: Page, session: RenderSession, page_errors: list[str]
):
    # One row leaves the sentinel in view, so the next page loads on open.
    _paged(page, session, first_rows=1, chipped="a0")
    _open(page)
    page.wait_for_selector(
        '#p-results [data-value="b0"]', state="attached", timeout=5000
    )
    _settle(page)

    _pick(page, "b0").click()

    assert _values(page) == ["a0", "b0"]
    assert _hidden_rows(page)["b0"] is True
    assert _state(page) == CLOSED
    with page.expect_request(CANDIDATES, timeout=5000) as request:
        page.keyboard.type("P")
    assert _exclude(request.value.url) == ["a0,b0"]
    assert page_errors == []


def test_a_chip_swapped_for_another_value_moves_the_hidden_row(
    page: Page, session: RenderSession, page_errors: list[str]
):
    requests = _serve(
        page,
        session,
        _picker(session, items=_items("v0", "v1"), required=True),
        swap=_chip(session, "v2"),
    )
    _open(page)
    sent = len(requests)
    _record_events(page)

    _swap(page, CHIP.format(value="v0"), "outerHTML")
    _wait_values(page, ["v2", "v1"])
    _settle(page)

    assert _hidden_rows(page) == {"v0": False, "v1": True, "v2": True}
    assert _validity(page) == "v2,v1"
    assert _state(page) == OPEN
    assert _has_focus(_input(page))
    assert _events(page) == []
    assert len(requests) == sent
    assert page_errors == []


@pytest.mark.parametrize(
    ("selector", "swap", "answer"),
    [
        # One chip's outerHTML replaced by itself and a new one.
        (CHIP.format(value="v0"), "outerHTML", ("v0", "v2")),
        # A new chip appended to the chips.
        ("#p .pjx-roster-picker__chips", "beforeend", ("v2",)),
    ],
    ids=["outer", "beforeend"],
)
def test_a_chip_added_by_a_swap_reaches_the_cap_and_validity(
    page: Page,
    session: RenderSession,
    page_errors: list[str],
    selector: str,
    swap: str,
    answer: tuple[str, ...],
):
    _serve(
        page,
        session,
        _picker(session, items=_items("v0"), max_items=2, required=True),
        swap="".join(_chip(session, value) for value in answer),
    )
    _open(page)
    _close_by_blur(page)
    _record_events(page)

    _swap(page, selector, swap)
    _wait_values(page, ["v0", "v2"])
    _settle(page)

    assert _hidden_rows(page) == {"v0": True, "v1": False, "v2": True}
    assert _input(page).is_disabled()
    assert _hint_hidden(page) is False
    assert _validity(page) == "v0,v2"
    assert _state(page) == CLOSED
    assert _events(page) == []
    assert page_errors == []


def test_a_chip_removed_by_an_empty_swap_frees_its_row_cap_and_validity(
    page: Page, session: RenderSession, page_errors: list[str]
):
    _serve(
        page,
        session,
        _picker(session, items=_items("v0"), max_items=2, required=True),
        swap="",
    )
    _open(page)
    # Reaches the cap and closes the list, keeping its rows.
    _pick(page, "v1").click()
    assert _input(page).is_disabled()
    _record_events(page)

    _swap(page, CHIP.format(value="v0"), "outerHTML")
    _wait_values(page, ["v1"])
    _settle(page)

    assert _hidden_rows(page) == {"v0": False, "v1": True, "v2": False}
    assert not _input(page).is_disabled()
    assert _hint_hidden(page) is True
    assert _validity(page) == "v1"
    assert _state(page) == CLOSED
    assert _events(page) == []
    assert page_errors == []


def test_a_chip_removed_by_an_empty_swap_shows_its_row_in_an_open_list(
    page: Page, session: RenderSession, page_errors: list[str]
):
    _serve(page, session, _picker(session, items=_items("v0", "v1")), swap="")
    _open(page)
    _record_events(page)

    _swap(page, CHIP.format(value="v0"), "outerHTML")
    _wait_values(page, ["v1"])
    _settle(page)

    assert _hidden_rows(page) == {"v0": False, "v1": True, "v2": False}
    assert _state(page) == OPEN
    assert _has_focus(_input(page))
    assert _events(page) == []
    assert page_errors == []


def test_an_empty_chip_swap_leaves_another_picker_alone(
    page: Page, session: RenderSession, page_errors: list[str]
):
    body = _picker(session, items=_items("v0"), required=True) + _picker(
        session, "q", items=_items("v0", "v1"), max_items=2, required=True
    )
    _serve(page, session, body, swap="")

    _swap(page, CHIP.format(value="v0"), "outerHTML")
    _wait_values(page, [])
    _settle(page)

    assert _validity(page) == ""
    assert _values(page, "q") == ["v0", "v1"]
    assert _input(page, "q").is_disabled()
    assert _hint_hidden(page, "q") is False
    assert _validity(page, "q") == "v0,v1"
    assert page_errors == []


def test_a_failed_chip_swap_changes_nothing(
    page: Page, session: RenderSession, page_errors: list[str]
):
    _serve(
        page,
        session,
        _picker(session, items=_items("v0", "v1"), max_items=2, required=True),
    )
    # Registered last, so it answers /swap ahead of _serve's route.
    page.route(
        SWAP_URL,
        lambda route: route.fulfill(status=500, body="no", content_type="text/html"),
    )
    _record_events(page)

    # htmx swaps nothing for a 500.
    page.evaluate(
        "selector => htmx.ajax('GET', '/swap', {"
        " target: document.querySelector(selector), swap: 'outerHTML' })"
        ".catch(() => {})",
        CHIP.format(value="v0"),
    )
    _settle(page)

    assert _values(page) == ["v0", "v1"]
    assert _input(page).is_disabled()
    assert _hint_hidden(page) is False
    assert _validity(page) == "v0,v1"
    assert _events(page) == []
    assert page_errors == []


def test_an_empty_chip_swap_in_a_disabled_picker_throws_nothing(
    page: Page, session: RenderSession, page_errors: list[str]
):
    _serve(
        page,
        session,
        _picker(session, items=_items("v0", "v1"), disabled=True),
        swap="",
    )

    _swap(page, CHIP.format(value="v0"), "outerHTML")
    _wait_values(page, ["v1"])
    _settle(page)

    assert _hint_hidden(page) is True
    assert page_errors == []


def test_a_press_across_a_whole_picker_swap_leaves_no_error(
    page: Page, session: RenderSession, page_errors: list[str]
):
    requests = _serve(
        page, session, _picker(session), swap=_picker(session, items=_items("v1"))
    )
    _open(page)
    box = _input(page).bounding_box()
    assert box is not None
    page.mouse.move(box["x"] + 5, box["y"] + 5)
    page.mouse.down()

    _swap(page, "#p", "outerHTML")
    _wait_values(page, ["v1"])
    _settle(page)
    sent = len(requests)
    # Released far from any picker: the press ends outside the new one.
    page.mouse.move(700, 500)
    page.mouse.up()
    _settle(page)
    # Past the 300 ms debounce, so an open's search would have been sent.
    page.wait_for_timeout(300)

    assert _state(page) == CLOSED
    assert len(requests) == sent
    assert page_errors == []


def test_a_click_on_a_label_around_the_picker_still_opens_it(
    page: Page, session: RenderSession, page_errors: list[str]
):
    body = f'<label><span id="caption">Members</span>{_picker(session)}</label>'
    requests = _serve(page, session, body)

    page.click("#caption")
    page.wait_for_selector(
        "#p-results [data-pjx-roster-pick]", state="attached", timeout=5000
    )

    assert _has_focus(_input(page))
    assert _state(page) == OPEN
    assert len(requests) == 1
    assert page_errors == []
