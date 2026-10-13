"""PJXRosterPicker's search requests, in real chromium with the vendored htmx.

Every page loads the committed pjx_roster_picker.js, so these tests exercise
the asset that ships. The candidates stub logs each request URL and answers
with rows, with a chosen status, or not at all until the test fulfils the
held route. A negative is proven by letting a beat pass and checking nothing
changed.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING, Any
from urllib.parse import parse_qs, urlsplit

from pyjinhx.builtins.ui.pjx_roster_picker import PJXRosterItem, PJXRosterPicker
from pyjinhx.builtins.ui.pjx_roster_results import PJXRosterResults
from pyjinhx.client import read_vendored_htmx
from pyjinhx.rendering import render

if TYPE_CHECKING:
    from playwright.sync_api import Locator, Page, Request, Route

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
APP_URL = "http://pjx.test/app"
HTMX_TAG = f"<script>{read_vendored_htmx()}</script>"
ASSET_TAG = f"<script>{ASSET}</script>"
PICKS = "#p-results [data-pjx-roster-pick]"
OPEN = ("true", False)


def _picker(session: RenderSession, picker_id: str = "p", **kwargs: Any) -> str:
    return render(
        PJXRosterPicker(
            id=picker_id, name="members", candidates_url=CANDIDATES_URL, **kwargs
        ),
        session,
    )


def _query(url: str) -> dict[str, list[str]]:
    return parse_qs(urlsplit(url).query, keep_blank_values=True)


def _serve(
    page: Page,
    session: RenderSession,
    body: str,
    *,
    rows: str | None = None,
    statuses: dict[str, int] | None = None,
    held: dict[str, list[Route]] | None = None,
) -> list[str]:
    """Load body with the CSS and scripts, answer candidates, return the request log.

    A search is answered with rows, three people by default. A search whose q
    is a key of statuses gets that status and no body instead; one whose q is
    a key of held is appended there unanswered, for the test to fulfil.
    """
    if rows is None:
        items = [
            PJXRosterItem(value=f"v{index}", label=f"Person {index}")
            for index in range(3)
        ]
        rows = render(PJXRosterResults(picker_id="p", items=items), session)
    answer = rows
    html = (
        f'<html><head><meta charset="utf-8"><style>{CSS}</style></head>'
        f"<body>{body}{HTMX_TAG}{ASSET_TAG}</body></html>"
    )
    requests: list[str] = []

    def candidates(route: Route) -> None:
        requests.append(route.request.url)
        q = _query(route.request.url)["q"][0]
        if held is not None and q in held:
            held[q].append(route)
        elif statuses is not None and q in statuses:
            route.fulfill(status=statuses[q], body="", content_type="text/html")
        else:
            route.fulfill(body=answer, content_type="text/html")

    page.route(URL, lambda route: route.fulfill(body=html, content_type="text/html"))
    page.route(CANDIDATES, candidates)
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


def _last_query(page: Page, picker_id: str = "p") -> str | None:
    return page.evaluate(
        "id => document.querySelector(`#${id} .pjx-roster-picker__input`)"
        ".getAttribute('data-last-query')",
        picker_id,
    )


def _wait_last_query(page: Page, value: str, picker_id: str = "p") -> None:
    page.wait_for_function(
        "([id, value]) => document.querySelector(`#${id} .pjx-roster-picker__input`)"
        ".getAttribute('data-last-query') === value",
        arg=[picker_id, value],
        timeout=5000,
    )


def _asks_for(q: str) -> Callable[[Request], bool]:
    """A page.expect_request predicate that matches a search for q."""

    def matches(request: Request) -> bool:
        return request.url.startswith(CANDIDATES_URL) and _query(request.url).get(
            "q"
        ) == [q]

    return matches


def _held_route(page: Page, routes: list[Route]) -> Route:
    """Wait until the stub has held a search in routes, and return it."""
    # Route handlers run while the page is waited on, so poll in short beats.
    for _ in range(250):
        if routes:
            return routes[0]
        page.wait_for_timeout(20)
    raise AssertionError("no search was held")


def test_a_search_excludes_the_chipped_values_in_order(
    page: Page, session: RenderSession, page_errors: list[str]
):
    items = [
        PJXRosterItem(value="ada", label="Ada"),
        PJXRosterItem(value="bob", label="Bob"),
    ]
    _serve(page, session, _picker(session, items=items))

    with page.expect_request(CANDIDATES, timeout=5000) as request:
        _input(page).click()

    assert _query(request.value.url) == {
        "q": [""],
        "exclude": ["ada,bob"],
        "picker_id": ["p"],
    }
    assert page_errors == []


def test_a_picker_without_chips_sends_an_empty_exclude(
    page: Page, session: RenderSession, page_errors: list[str]
):
    _serve(page, session, _picker(session))

    with page.expect_request(CANDIDATES, timeout=5000) as request:
        _input(page).click()

    assert _query(request.value.url) == {
        "q": [""],
        "exclude": [""],
        "picker_id": ["p"],
    }
    assert page_errors == []


def test_exclude_survives_url_special_characters(
    page: Page, session: RenderSession, page_errors: list[str]
):
    items = [
        PJXRosterItem(value="a&b", label="A and B"),
        PJXRosterItem(value="c d", label="C D"),
        PJXRosterItem(value="é", label="E acute"),
    ]
    _serve(page, session, _picker(session, items=items))

    with page.expect_request(CANDIDATES, timeout=5000) as request:
        _input(page).click()

    assert _query(request.value.url)["exclude"] == ["a&b,c d,é"]
    assert page_errors == []


def test_only_a_chips_own_input_is_excluded(
    page: Page, session: RenderSession, page_errors: list[str]
):
    # An app's control in the detail slot that happens to share the class.
    nested = (
        '<input type="hidden" class="pjx-roster-picker__chip-input" value="nested">'
    )
    items = [PJXRosterItem(value="ada", label="Ada", detail=nested)]
    _serve(page, session, _picker(session, items=items))

    with page.expect_request(CANDIDATES, timeout=5000) as first:
        _input(page).click()
    page.wait_for_selector(PICKS, timeout=5000)
    # Each kept row carries a template chip with its own hidden input.
    assert page.locator("#p-results template").count() == 3

    with page.expect_request(_asks_for("v"), timeout=5000) as second:
        page.keyboard.type("v")

    assert _query(first.value.url)["exclude"] == ["ada"]
    assert _query(second.value.url)["exclude"] == ["ada"]
    assert page_errors == []


def test_exclude_is_read_when_the_search_is_sent(
    page: Page, session: RenderSession, page_errors: list[str]
):
    items = [PJXRosterItem(value="ada", label="Ada")]
    _serve(page, session, _picker(session, items=items))
    with page.expect_request(CANDIDATES, timeout=5000) as first:
        _input(page).click()
    assert _query(first.value.url)["exclude"] == ["ada"]

    page.evaluate(
        """() => {
            const chips = document.querySelector('#p .pjx-roster-picker__chips');
            chips.querySelector('[data-pjx-roster-chip]').remove();
            chips.insertAdjacentHTML('beforeend',
                '<div data-pjx-roster-chip>'
                + '<input type="hidden" class="pjx-roster-picker__chip-input" value="cy">'
                + '</div>');
        }"""
    )
    with page.expect_request(_asks_for("c"), timeout=5000) as second:
        page.keyboard.type("c")

    assert _query(second.value.url)["exclude"] == ["cy"]
    assert page_errors == []


def test_each_picker_excludes_only_its_own_chips(
    page: Page, session: RenderSession, page_errors: list[str]
):
    # Side by side, so neither open list covers the other picker's box.
    items = [PJXRosterItem(value="ada", label="Ada")]
    body = (
        '<div style="display: flex; gap: 40px">'
        f'<div style="flex: 1">{_picker(session, "a", items=items)}</div>'
        f'<div style="flex: 1">{_picker(session, "b")}</div>'
        "</div>"
    )
    _serve(page, session, body)

    with page.expect_request(CANDIDATES, timeout=5000) as request:
        _input(page, "b").click()

    assert _query(request.value.url) == {
        "q": [""],
        "exclude": [""],
        "picker_id": ["b"],
    }
    assert page_errors == []


def test_a_picker_added_after_load_sends_exclude(
    page: Page, session: RenderSession, page_errors: list[str]
):
    _serve(page, session, '<div id="host"></div>')
    items = [PJXRosterItem(value="ada", label="Ada")]

    # htmx.process stands in for the htmx swap that would bring the picker in.
    page.evaluate(
        """html => {
            const host = document.getElementById('host');
            host.innerHTML = html;
            htmx.process(host);
        }""",
        _picker(session, "late", items=items),
    )
    with page.expect_request(CANDIDATES, timeout=5000) as request:
        _input(page, "late").click()

    assert _query(request.value.url) == {
        "q": [""],
        "exclude": ["ada"],
        "picker_id": ["late"],
    }
    assert page_errors == []


def test_a_successful_search_records_the_query_it_sent(
    page: Page, session: RenderSession, page_errors: list[str]
):
    _serve(page, session, _picker(session))
    assert _last_query(page) is None

    _input(page).click()
    _wait_last_query(page, "")
    page.keyboard.type("al")
    _wait_last_query(page, "al")

    assert page_errors == []


def test_the_recorded_query_is_the_one_sent_not_the_box_text(
    page: Page, session: RenderSession, page_errors: list[str]
):
    held: dict[str, list[Route]] = {"a": [], "ab": []}
    _serve(page, session, _picker(session), held=held)
    _input(page).click()
    _wait_last_query(page, "")

    page.keyboard.type("a")
    search_for_a = _held_route(page, held["a"])
    page.keyboard.type("b")
    # Answered inside the 300 ms before the search for "ab" would replace it.
    search_for_a.fulfill(body="<p>rows for a</p>", content_type="text/html")
    _wait_last_query(page, "a")
    _settle(page)

    assert _input(page).input_value() == "ab"
    assert _last_query(page) == "a"
    assert page_errors == []


def test_an_app_request_in_a_chip_is_left_alone(
    page: Page, session: RenderSession, page_errors: list[str]
):
    button = f'<button type="button" id="app" hx-get="{APP_URL}">Go</button>'
    items = [PJXRosterItem(value="ada", label="Ada", extra=button)]
    _serve(page, session, _picker(session, items=items))
    page.route(
        f"{APP_URL}*",
        lambda route: route.fulfill(body="Done", content_type="text/html"),
    )
    _input(page).click()
    page.keyboard.type("al")
    _wait_last_query(page, "al")
    # Closed, so the open list does not cover the chip's button.
    page.keyboard.press("Escape")

    with page.expect_request(f"{APP_URL}*", timeout=5000) as request:
        page.click("#app")
    page.wait_for_selector("#app:has-text('Done')", timeout=5000)
    _settle(page)

    assert "exclude" not in _query(request.value.url)
    assert _last_query(page) == "al"
    assert page_errors == []


def test_a_request_from_inside_the_results_is_left_alone(
    page: Page, session: RenderSession, page_errors: list[str]
):
    # Stands in for the paging sentinel: an htmx element the rows bring in.
    rows = f'<div><div id="more" hx-get="{APP_URL}" hx-trigger="load">More</div></div>'
    items = [PJXRosterItem(value="ada", label="Ada")]
    _serve(page, session, _picker(session, items=items), rows=rows)
    page.route(
        f"{APP_URL}*",
        lambda route: route.fulfill(body="", content_type="text/html"),
    )

    with page.expect_request(f"{APP_URL}*", timeout=5000) as request:
        _input(page).click()
    _settle(page)

    assert "exclude" not in _query(request.value.url)
    assert _last_query(page) == ""
    assert page_errors == []
