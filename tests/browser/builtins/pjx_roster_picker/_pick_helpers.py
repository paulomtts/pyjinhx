"""Page serving and change-recording helpers for the picker pick and remove tests."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

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
)

if TYPE_CHECKING:
    from playwright.sync_api import Locator, Page, Route

    from pyjinhx.rendering.session import RenderSession


RECORD_CHANGES = """() => {
    window.changes = [];
    document.addEventListener('pjx:roster-picker:change', (event) => {
        window.changes.push({
            values: event.detail.values,
            target: event.target.id,
            bubbles: event.bubbles,
            cancelable: event.cancelable,
        });
    });
}"""


def _serve(
    page: Page, session: RenderSession, body: str, *, rows: str | None = None
) -> list[str]:
    """Load body with the CSS and scripts, answer every search with rows, return the request log."""
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
        route.fulfill(body=answer, content_type="text/html")

    page.route(URL, lambda route: route.fulfill(body=html, content_type="text/html"))
    page.route(CANDIDATES, candidates)
    page.goto(URL)
    page.wait_for_function("() => window.htmx")
    return requests


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


def _open(page: Page, picker_id: str = "p") -> None:
    """Click the box and wait until the first search's rows are in.

    Attached, not visible: a row for a chipped value arrives hidden."""
    _input(page, picker_id).click()
    page.wait_for_selector(
        f"#{picker_id}-results [data-pjx-roster-pick]",
        state="attached",
        timeout=5000,
    )
    _wait_last_query(page, "", picker_id)


def _remove(page: Page, value: str, picker_id: str = "p") -> Locator:
    return page.locator(
        f"#{picker_id} .pjx-roster-picker__chips > [data-pjx-roster-chip]"
        f':has(> input[value="{value}"]) [data-pjx-roster-remove]'
    )


def _chip_inputs(page: Page, picker_id: str = "p") -> list[dict[str, str]]:
    """Each chip's own hidden input, as name and value, in DOM order."""
    return page.evaluate(
        """id => Array.from(
            document.querySelectorAll(
                `#${id} .pjx-roster-picker__chips > [data-pjx-roster-chip] > .pjx-roster-picker__chip-input`
            ),
            (input) => ({ name: input.name, value: input.value })
        )""",
        picker_id,
    )


def _chip_values(page: Page, picker_id: str = "p") -> list[str]:
    return [chip["value"] for chip in _chip_inputs(page, picker_id)]


def _wait_hidden_rows(
    page: Page, expected: dict[str, bool], picker_id: str = "p"
) -> None:
    """Wait until the rows are exactly expected's values with expected's hidden flags."""
    page.wait_for_function(
        """([id, expected]) => {
            const rows = Array.from(
                document.querySelectorAll(`#${id}-results [data-pjx-roster-pick]`)
            );
            return rows.length === Object.keys(expected).length
                && rows.every((row) => row.hidden === expected[row.dataset.value]);
        }""",
        arg=[picker_id, expected],
        timeout=5000,
    )


def _record_changes(page: Page) -> None:
    page.evaluate(RECORD_CHANGES)


def _changes(page: Page) -> list[dict[str, Any]]:
    return page.evaluate("() => window.changes")
