"""Helpers shared by the split test files in this folder."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

from pyjinhx.builtins.pjx_roster_picker import PJXRosterItem, PJXRosterPicker
from pyjinhx.builtins.pjx_roster_results import PJXRosterResults
from pyjinhx.client import read_vendored_htmx
from pyjinhx.rendering.pipeline import render

if TYPE_CHECKING:
    from playwright.sync_api import Locator, Page, Route

    from pyjinhx.rendering.session import RenderSession


PICKER_DIR = (
    Path(__file__).resolve().parents[4] / "pyjinhx" / "builtins" / "pjx_roster_picker"
)


CSS = (PICKER_DIR / "pjx_roster_picker.css").read_text(encoding="utf-8")


ASSET = (PICKER_DIR / "pjx_roster_picker.js").read_text(encoding="utf-8")


URL = "http://pjx.test/"


CANDIDATES_URL = "http://pjx.test/candidates"


CANDIDATES = "http://pjx.test/candidates*"


HTMX_TAG = f"<script>{read_vendored_htmx()}</script>"


ASSET_TAG = f"<script>{ASSET}</script>"


OPEN = ("true", False)


CLOSED = ("false", True)


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


def _picker(session: RenderSession, picker_id: str = "p", **kwargs: Any) -> str:
    return render(
        PJXRosterPicker(
            id=picker_id, name="members", candidates_url=CANDIDATES_URL, **kwargs
        ),
        session,
    )


def _item(value: str) -> PJXRosterItem:
    return PJXRosterItem(value=value, label=value.upper())


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


def _pick(page: Page, value: str, picker_id: str = "p") -> Locator:
    return page.locator(
        f'#{picker_id}-results [data-pjx-roster-pick][data-value="{value}"]'
    )


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


def _hidden_rows(page: Page, picker_id: str = "p") -> dict[str, bool]:
    """Each result row's value mapped to its hidden flag."""
    return page.evaluate(
        """id => Object.fromEntries(Array.from(
            document.querySelectorAll(`#${id}-results [data-pjx-roster-pick]`),
            (row) => [row.dataset.value, row.hidden]
        ))""",
        picker_id,
    )


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


def _has_focus(locator: Locator) -> bool:
    return locator.evaluate("el => el === document.activeElement")


def _hint_hidden(page: Page, picker_id: str = "p") -> bool:
    return page.evaluate(
        "id => document.querySelector(`#${id} .pjx-roster-picker__hint`).hidden",
        picker_id,
    )


def _record_changes(page: Page) -> None:
    page.evaluate(RECORD_CHANGES)


def _changes(page: Page) -> list[dict[str, Any]]:
    return page.evaluate("() => window.changes")
