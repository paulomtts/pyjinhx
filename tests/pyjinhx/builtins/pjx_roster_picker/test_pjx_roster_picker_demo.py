"""The gallery's roster picker demo page, built by the docs hooks and driven in real chromium.

The page is the real build output, served for a fake origin as the graph
demo's is. Its search route is the page's own inline script; every request
that reaches the fake origin is logged, so a test can tell an answer played
in-page from a request that went to the network.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import TYPE_CHECKING
from urllib.parse import parse_qs, urlsplit

import pytest

DOCS = Path(__file__).resolve().parents[4] / "docs"
sys.path.insert(0, str(DOCS))

import hooks
from demos.roster_picker import PEOPLE

if TYPE_CHECKING:
    from playwright.sync_api import Page, Route

SITE = "http://pjx.test/"
URL = SITE + "demos/pjx-roster-picker.html"
TEAM = "demo-roster-team"
OWNER = "demo-roster-owner"
APPROVERS = "demo-roster-approvers"

# The route's page size, as the demo script sets it.
PAGE_SIZE = 4

# The value of every row in the DOM under selector, hidden or not, in order.
ROW_VALUES = """selector => Array.from(
    document.querySelectorAll(selector), (row) => row.dataset.value)"""

# True once the rows a picker shows (not hidden) are exactly want, in order.
SHOWS = """([selector, want]) => JSON.stringify(
    Array.from(document.querySelectorAll(selector))
        .filter((row) => !row.hidden).map((row) => row.dataset.value)
) === JSON.stringify(want)"""

# Each chip's own posted value, in chip order.
CHIP_VALUES = """id => Array.from(document.querySelectorAll('#' + id
    + ' .pjx-roster-picker__chips > [data-pjx-roster-chip] > .pjx-roster-picker__chip-input'),
    (input) => input.value)"""

# Scrolls the list to its end on every poll, so each sentinel comes into
# view; done once rows are in and no sentinel is left.
PAGED_THROUGH = """id => {
    const mount = document.getElementById(id);
    mount.scrollTop = mount.scrollHeight;
    return mount.querySelector('[data-pjx-roster-pick]') !== null
        && mount.querySelector('.pjx-roster-picker__more') === null;
}"""

PAGE_IDS = """id => Array.from(
    document.getElementById(id).querySelectorAll('[data-pjx-roster-results]'),
    (page) => page.id)"""

# Counts the swaps the route makes into the list from here on.
COUNT_ANSWERS = """id => {
    window.__answers = 0;
    document.addEventListener('htmx:afterSettle', (event) => {
        if (event.target.closest('#' + id)) window.__answers += 1;
    });
}"""

HOSTILE = '"><b>x</b>'


@pytest.fixture(scope="module")
def site(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """A docs site_dir that on_post_build has written every demo page into."""
    root = tmp_path_factory.mktemp("site")
    hooks.on_post_build({"site_dir": str(root)})
    return root


def _serve(page: Page, site: Path) -> list[str]:
    """Serve the built site for SITE, open the demo, and return the log of requests it got."""
    requests: list[str] = []

    def fulfill(route: Route) -> None:
        requests.append(route.request.url)
        path = site / route.request.url.removeprefix(SITE)
        if path.is_file():
            route.fulfill(path=path)
        else:
            route.fulfill(status=204)

    page.route(SITE + "**", fulfill)
    page.goto(URL)
    return requests


def _input(picker: str) -> str:
    return f"#{picker} .pjx-roster-picker__input"


def _rows(picker: str) -> str:
    return f"#{picker}-results [data-pjx-roster-pick]"


def _row(picker: str, value: str) -> str:
    return f'{_rows(picker)}[data-value="{value}"]'


def _matching(text: str, chipped: set[str]) -> list[str]:
    """The values the route answers for text, in PEOPLE order, before paging."""
    return [
        person.value
        for person in PEOPLE
        if text.lower() in person.label.lower() and person.value not in chipped
    ]


def _wait_until_shown(page: Page, picker: str, values: list[str]) -> None:
    page.wait_for_function(SHOWS, arg=[_rows(picker), values], timeout=5000)


def test_the_page_boots(page, page_errors, console_errors, site):
    _serve(page, site)
    assert page.evaluate("() => typeof htmx.swap") == "function"
    assert page.locator("[data-pjx-roster-picker]").count() == 3
    assert page_errors == []
    assert console_errors == []


def test_typing_filters_the_fixed_list(page, page_errors, console_errors, site):
    requests = _serve(page, site)
    want = _matching("ar", {"ada"})
    assert 1 < len(want) <= PAGE_SIZE
    page.fill(_input(TEAM), "ar")
    _wait_until_shown(page, TEAM, want)
    assert page.evaluate(ROW_VALUES, _rows(TEAM)) == want
    assert [url for url in requests if "/demo/people" in url] == []
    assert page_errors == []
    assert console_errors == []


def test_the_route_honours_exclude(page, page_errors, console_errors, site):
    _serve(page, site)
    page.click(_input(TEAM))
    page.wait_for_selector(_row(TEAM, "alan"), state="attached", timeout=5000)
    # Every row in the DOM, hidden or not: the chipped person was never sent,
    # so the route left them out, not the client.
    values = page.evaluate(ROW_VALUES, _rows(TEAM))
    assert values[:PAGE_SIZE] == _matching("", {"ada"})[:PAGE_SIZE]
    assert "ada" not in values
    assert page_errors == []
    assert console_errors == []


def test_scrolling_pages_through_every_match(page, page_errors, console_errors, site):
    _serve(page, site)
    page.click(_input(TEAM))
    page.wait_for_function(PAGED_THROUGH, arg=f"{TEAM}-results", timeout=5000)
    want = _matching("", {"ada"})
    assert page.evaluate(ROW_VALUES, _rows(TEAM)) == want
    # Each page's id comes from the picker and its cursor, so no two collide.
    assert page.evaluate(PAGE_IDS, f"{TEAM}-results") == [
        f"{TEAM}-page-{cursor}" for cursor in range(0, len(want), PAGE_SIZE)
    ]
    assert page_errors == []
    assert console_errors == []


def test_no_match_shows_the_empty_message(page, page_errors, console_errors, site):
    _serve(page, site)
    assert _matching("zzz", set()) == []
    page.fill(_input(TEAM), "zzz")
    page.wait_for_selector(
        f"#{TEAM}-results .pjx-roster-picker__empty", state="visible", timeout=5000
    )
    assert page.locator(f"#{TEAM}-results .pjx-roster-picker__more").count() == 0
    assert page.locator(_rows(TEAM)).count() == 0
    assert page_errors == []
    assert console_errors == []


def test_single_picker_replaces_its_chip(page, page_errors, console_errors, site):
    _serve(page, site)
    assert page.evaluate(CHIP_VALUES, OWNER) == ["grace"]
    page.click(_input(OWNER))
    page.wait_for_selector(_row(OWNER, "ada"), state="visible", timeout=5000)
    page.click(_row(OWNER, "ada"))
    assert page.evaluate(CHIP_VALUES, OWNER) == ["ada"]
    assert page.locator(f'#{OWNER} input[name="owner"]').count() == 1
    assert page_errors == []
    assert console_errors == []


def test_capped_picker_fills_and_frees(page, page_errors, console_errors, site):
    _serve(page, site)
    hint = f"#{APPROVERS} .pjx-roster-picker__hint"
    assert page.is_hidden(hint)
    page.click(_input(APPROVERS))
    page.wait_for_selector(_row(APPROVERS, "ada"), state="visible", timeout=5000)
    page.click(_row(APPROVERS, "ada"))
    assert page.evaluate(CHIP_VALUES, APPROVERS) == ["barbara", "edsger", "ada"]
    assert page.is_disabled(_input(APPROVERS))
    assert page.is_visible(hint)
    page.locator(f"#{APPROVERS} [data-pjx-roster-remove]").first.click()
    assert page.evaluate(CHIP_VALUES, APPROVERS) == ["edsger", "ada"]
    assert page.is_enabled(_input(APPROVERS))
    assert page.is_hidden(hint)
    assert page_errors == []
    assert console_errors == []


def test_reopen_keeps_the_rows(page, page_errors, console_errors, site):
    _serve(page, site)
    # Opened and answered first, so typing below is the only search left.
    page.click(_input(TEAM))
    page.wait_for_selector(_rows(TEAM), state="attached", timeout=5000)
    page.fill(_input(TEAM), "ar")
    _wait_until_shown(page, TEAM, _matching("ar", {"ada"}))
    page.evaluate(
        "selector => { window.__row = document.querySelector(selector); }",
        _rows(TEAM),
    )
    page.evaluate(COUNT_ANSWERS, f"{TEAM}-results")
    page.keyboard.press("Escape")
    assert page.get_attribute(_input(TEAM), "aria-expanded") == "false"
    page.click(_input(TEAM))
    assert page.get_attribute(_input(TEAM), "aria-expanded") == "true"
    # Past the search's 300ms debounce, so a reopen that asked would have
    # been answered by now.
    page.wait_for_timeout(700)
    assert page.evaluate("() => window.__row.isConnected") is True
    assert page.evaluate("() => window.__answers") == 0
    assert page_errors == []
    assert console_errors == []


def test_other_requests_pass_through(page, page_errors, console_errors, site):
    requests = _serve(page, site)
    page.evaluate(
        "() => htmx.ajax('GET', '/elsewhere', {target: 'body', swap: 'none'})"
    )
    assert SITE + "elsewhere" in requests
    assert page_errors == []
    assert console_errors == []


def test_a_removed_person_comes_back_on_reopen(page, page_errors, console_errors, site):
    _serve(page, site)
    page.click(_input(APPROVERS))
    page.wait_for_selector(_row(APPROVERS, "ada"), state="attached", timeout=5000)
    assert page.locator(_row(APPROVERS, "barbara")).count() == 0
    page.keyboard.press("Escape")
    page.locator(
        f'#{APPROVERS} [data-pjx-roster-chip]:has(input[value="barbara"])'
        " [data-pjx-roster-remove]"
    ).click()
    page.click(_input(APPROVERS))
    page.wait_for_selector(_row(APPROVERS, "barbara"), state="visible", timeout=5000)
    assert page_errors == []
    assert console_errors == []


def test_request_values_become_attribute_text_only(
    page, page_errors, console_errors, site
):
    _serve(page, site)
    page.evaluate(
        """exclude => htmx.ajax('GET', '/demo/people?' + new URLSearchParams(
            {exclude, picker_id: 'demo-roster-team'}),
            {target: '#demo-roster-team-results', swap: 'innerHTML'})""",
        HOSTILE,
    )
    more = page.get_attribute(f"#{TEAM}-results .pjx-roster-picker__more", "hx-get")
    assert more is not None
    assert parse_qs(urlsplit(more).query)["exclude"] == [HOSTILE]
    assert page.locator(f"#{TEAM}-results b, #{TEAM}-results [onclick]").count() == 0
    assert page_errors == []
    assert console_errors == []


def test_an_unknown_picker_is_left_to_the_network(
    page, page_errors, console_errors, site
):
    requests = _serve(page, site)
    page.evaluate(
        """() => htmx.ajax('GET', '/demo/people?picker_id=nope',
            {target: 'body', swap: 'none'})"""
    )
    assert SITE + "demo/people?picker_id=nope" in requests
    assert page_errors == []
    assert console_errors == []


def test_clearing_the_box_lists_the_first_entries_again(
    page, page_errors, console_errors, site
):
    _serve(page, site)
    page.fill(_input(TEAM), "ar")
    _wait_until_shown(page, TEAM, _matching("ar", {"ada"}))
    page.fill(_input(TEAM), "")
    page.wait_for_selector(_row(TEAM, "alan"), state="attached", timeout=5000)
    values = page.evaluate(ROW_VALUES, _rows(TEAM))
    assert values[:PAGE_SIZE] == _matching("", {"ada"})[:PAGE_SIZE]
    assert page_errors == []
    assert console_errors == []
