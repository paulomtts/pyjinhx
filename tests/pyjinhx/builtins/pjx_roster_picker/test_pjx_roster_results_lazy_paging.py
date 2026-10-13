"""PJXRosterResults' pagination sentinel, in real chromium with the vendored htmx.

The first page sits in a fixed-height scrolling list above a spacer tall
enough for the window to scroll on its own, so a fetch can be pinned to the
list's own overflow rather than to the viewport. Requests for the next page
are routed and counted. A negative is proven by letting any pending
intersection callback run and then checking the count is still zero.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from pyjinhx.builtins.ui.pjx_roster_picker import PJXRosterItem
from pyjinhx.builtins.ui.pjx_roster_results import PJXRosterResults
from pyjinhx.client import read_vendored_htmx
from pyjinhx.rendering import render

if TYPE_CHECKING:
    from playwright.sync_api import Page, Route

    from pyjinhx.session import RenderSession

CSS = (
    Path(__file__).resolve().parents[4]
    / "pyjinhx"
    / "builtins"
    / "ui"
    / "pjx_roster_picker"
    / "pjx_roster_picker.css"
).read_text(encoding="utf-8")
URL = "http://pjx.test/"
MORE = "http://pjx.test/more*"
PICKS = "#p-results [data-pjx-roster-pick]"

# The shipped list is absolutely positioned under the picker's input and
# capped by a measured height; here it sits in normal flow at a fixed height
# so it overflows several times over and the window scrolls independently.
LIST_CSS = "#p-results { position: static; height: 160px; max-height: none; }"

# Centred in the viewport, the sentinel's own box is on screen, so only the
# list's clipping keeps it from counting as seen.
CENTRE_SENTINEL_IN_WINDOW = """() => {
    const box = document.getElementById('p-more-2').getBoundingClientRect();
    window.scrollTo(0, window.scrollY + box.top - window.innerHeight / 2);
}"""


def _items(prefix: str, count: int) -> list[PJXRosterItem]:
    return [
        PJXRosterItem(value=f"{prefix}{index}", label=f"{prefix.upper()}{index}")
        for index in range(count)
    ]


def _serve(page: Page, session: RenderSession) -> list[str]:
    """Load 30 rows into #p-results, route /more to 30 more, return the request log."""
    first = PJXRosterResults(
        picker_id="p",
        items=_items("a", 30),
        next_url="http://pjx.test/more?cursor=2",
        next_cursor="2",
    )
    second = render(PJXRosterResults(picker_id="p", items=_items("b", 30)), session)
    html = (
        f"<html><head><style>{CSS}{LIST_CSS}</style></head><body>"
        f'<div id="p-results" class="pjx-roster-picker__results">'
        f"{render(first, session)}</div>"
        '<div style="height: 200vh"></div>'
        f"<script>{read_vendored_htmx()}</script></body></html>"
    )
    requests: list[str] = []

    def more(route: Route) -> None:
        requests.append(route.request.url)
        route.fulfill(body=second, content_type="text/html")

    page.route(URL, lambda route: route.fulfill(body=html, content_type="text/html"))
    page.route(MORE, more)
    page.goto(URL)
    page.wait_for_function("() => window.htmx")
    return requests


def _settle(page: Page) -> None:
    """Let two animation frames and a short beat pass, so a pending intersection callback has run."""
    page.evaluate(
        "() => new Promise((done) => requestAnimationFrame(() => requestAnimationFrame(done)))"
    )
    # There is no event for "did not fire", so proving a negative needs a beat.
    page.wait_for_timeout(200)


def _scroll_list(page: Page, to_bottom: bool) -> None:
    page.evaluate(
        """toBottom => {
            const list = document.getElementById('p-results');
            list.scrollTop = toBottom ? list.scrollHeight : 0;
        }""",
        to_bottom,
    )


def _list_scroll_top(page: Page) -> float:
    return page.evaluate("() => document.getElementById('p-results').scrollTop")


def test_sentinel_does_not_fetch_before_the_list_scrolls(
    page: Page, session: RenderSession, page_errors: list[str]
):
    requests = _serve(page, session)
    _settle(page)

    below_the_fold = page.evaluate(
        """() => document.getElementById('p-more-2').getBoundingClientRect().top
            > document.getElementById('p-results').getBoundingClientRect().bottom"""
    )
    assert below_the_fold
    assert _list_scroll_top(page) == 0
    assert requests == []
    assert page_errors == []


def test_window_scroll_does_not_fetch_the_next_page(
    page: Page, session: RenderSession, page_errors: list[str]
):
    requests = _serve(page, session)

    page.evaluate(CENTRE_SENTINEL_IN_WINDOW)
    _settle(page)

    assert page.evaluate("() => window.scrollY") > 0
    on_screen = page.evaluate(
        """() => {
            const top = document.getElementById('p-more-2').getBoundingClientRect().top;
            return top >= 0 && top <= window.innerHeight;
        }"""
    )
    assert on_screen
    assert _list_scroll_top(page) == 0
    assert requests == []
    assert page_errors == []
