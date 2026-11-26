"""Page serving, swap and event-recording helpers for the picker swap tests."""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Any
from urllib.parse import parse_qs, urlsplit

from pyjinhx.builtins.pjx_roster_chip import PJXRosterChip
from pyjinhx.builtins.pjx_roster_picker import PJXRosterItem
from pyjinhx.builtins.pjx_roster_results import PJXRosterResults
from pyjinhx.rendering.pipeline import render
from tests.browser.builtins.pjx_roster_picker._harness import (
    ASSET_TAG,
    CANDIDATES,
    CSS,
    HTMX_TAG,
    URL,
    _input,
    _item,
    _settle,
)

if TYPE_CHECKING:
    from playwright.sync_api import Page, Route

    from pyjinhx.rendering.session import RenderSession


SWAP_URL = "http://pjx.test/swap"


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


def _swap(page: Page, selector: str, swap: str) -> None:
    """Swap /swap's answer into the element selector finds, through htmx.ajax."""
    page.evaluate(SWAP, [selector, swap])


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


def _validity(page: Page, picker_id: str = "p") -> str:
    return page.evaluate(
        "id => document.querySelector(`#${id} > .pjx-roster-picker__validity`).value",
        picker_id,
    )


def _record_events(page: Page) -> None:
    page.evaluate(RECORD_EVENTS)


def _events(page: Page) -> list[dict[str, Any]]:
    return page.evaluate("() => window.events")


def _exclude(url: str) -> list[str]:
    return parse_qs(urlsplit(url).query, keep_blank_values=True)["exclude"]
