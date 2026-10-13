"""PJXRosterPicker's pick, remove and change event, in real chromium with the vendored htmx.

Every page loads the committed pjx_roster_picker.js, so these tests exercise
the asset that ships. The candidates stub logs each request URL and answers
with three people, v0 to v2, whatever exclude says, so a row for a chipped
value really arrives and the script has to hide it. A change recorder
installed before the click logs every pjx:roster-picker:change. A negative
is proven by letting a beat pass and checking nothing changed.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

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
MORE_URL = "http://pjx.test/more"
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


def _record_changes(page: Page) -> None:
    page.evaluate(RECORD_CHANGES)


def _changes(page: Page) -> list[dict[str, Any]]:
    return page.evaluate("() => window.changes")


def test_a_pick_adds_a_chip_named_for_the_picker(
    page: Page, session: RenderSession, page_errors: list[str]
):
    _serve(page, session, _picker(session))
    _open(page)

    _pick(page, "v1").click()

    assert _chip_inputs(page) == [{"name": "members", "value": "v1"}]
    assert page_errors == []


def test_a_pick_lands_after_the_chips_already_there(
    page: Page, session: RenderSession, page_errors: list[str]
):
    _serve(page, session, _picker(session, items=[_item("a")]))
    _open(page)

    _pick(page, "v1").click()

    assert _chip_values(page) == ["a", "v1"]
    assert page_errors == []


def test_a_pick_hides_only_the_picked_row(
    page: Page, session: RenderSession, page_errors: list[str]
):
    _serve(page, session, _picker(session))
    _open(page)

    _pick(page, "v1").click()

    assert _hidden_rows(page) == {"v0": False, "v1": True, "v2": False}
    assert page_errors == []


def test_a_pick_closes_clears_and_refocuses_without_reopening(
    page: Page, session: RenderSession, page_errors: list[str]
):
    requests = _serve(page, session, _picker(session))
    _open(page)
    page.keyboard.type("Pe")
    _wait_last_query(page, "Pe")
    sent = len(requests)

    _pick(page, "v1").click()

    assert _state(page) == CLOSED
    assert _input(page).input_value() == ""
    assert _has_focus(_input(page))
    # Past the 300 ms debounce, so a reopen's search would have been sent.
    page.wait_for_timeout(500)
    assert _state(page) == CLOSED
    assert len(requests) == sent
    assert page_errors == []


def test_a_pick_fires_one_change_with_the_selection(
    page: Page, session: RenderSession, page_errors: list[str]
):
    _serve(page, session, _picker(session))
    _open(page)
    _record_changes(page)

    _pick(page, "v1").click()

    assert _changes(page) == [
        {"values": ["v1"], "target": "p", "bubbles": True, "cancelable": False}
    ]
    assert page_errors == []


def test_a_click_on_the_rows_label_picks(
    page: Page, session: RenderSession, page_errors: list[str]
):
    _serve(page, session, _picker(session))
    _open(page)

    _pick(page, "v1").locator(".pjx-roster-picker__pick-label").click()

    assert _chip_values(page) == ["v1"]
    assert page_errors == []


def test_two_pickers_pick_independently(
    page: Page, session: RenderSession, page_errors: list[str]
):
    # Side by side, so neither open list covers the other picker's box.
    body = (
        '<div style="display: flex; gap: 40px">'
        f'<div style="flex: 1">{_picker(session, "p")}</div>'
        f'<div style="flex: 1">{_picker(session, "q")}</div>'
        "</div>"
    )
    _serve(page, session, body)
    _open(page, "q")
    page.keyboard.press("Escape")
    _open(page, "p")
    _record_changes(page)

    _pick(page, "v1", "p").click()

    assert _chip_values(page, "p") == ["v1"]
    assert _chip_values(page, "q") == []
    assert _hidden_rows(page, "q") == {"v0": False, "v1": False, "v2": False}
    assert [change["target"] for change in _changes(page)] == ["p"]
    assert page_errors == []


def test_enter_on_a_focused_row_picks_it(
    page: Page, session: RenderSession, page_errors: list[str]
):
    _serve(page, session, _picker(session))
    _open(page)
    _pick(page, "v1").focus()

    page.keyboard.press("Enter")

    assert _chip_values(page) == ["v1"]
    assert _state(page) == CLOSED
    assert _has_focus(_input(page))
    assert page_errors == []


def test_a_row_without_a_chip_template_is_ignored(
    page: Page, session: RenderSession, page_errors: list[str]
):
    _serve(page, session, _picker(session))
    _open(page)
    # v1 loses its template, so its next sibling is v2's button; v2's
    # template is emptied of its chip.
    page.evaluate(
        """() => {
            const rows = document.querySelectorAll('#p-results [data-pjx-roster-pick]');
            rows[1].nextElementSibling.remove();
            rows[2].nextElementSibling.innerHTML = '';
        }"""
    )
    _record_changes(page)

    _pick(page, "v1").click()
    _pick(page, "v2").click()
    _settle(page)

    assert _chip_values(page) == []
    assert _changes(page) == []
    assert _state(page) == OPEN
    assert _hidden_rows(page) == {"v0": False, "v1": False, "v2": False}
    assert page_errors == []


def test_a_swapped_page_hides_rows_already_chipped(
    page: Page, session: RenderSession, page_errors: list[str]
):
    _serve(page, session, _picker(session, items=[_item("v0")]))

    _open(page)

    _wait_hidden_rows(page, {"v0": True, "v1": False, "v2": False})
    assert page_errors == []


def test_a_later_page_hides_rows_already_chipped(
    page: Page, session: RenderSession, page_errors: list[str]
):
    first = render(
        PJXRosterResults(picker_id="p", items=[_item("v0"), _item("v1")]), session
    )
    # Stands in for the paging sentinel, which swaps itself for the next page.
    more = f'<div hx-get="{MORE_URL}" hx-trigger="load" hx-swap="outerHTML"></div>'
    second = render(
        PJXRosterResults(picker_id="p", items=[_item("v2"), _item("v3")]), session
    )
    _serve(page, session, _picker(session, items=[_item("v2")]), rows=first + more)
    page.route(
        f"{MORE_URL}*",
        lambda route: route.fulfill(body=second, content_type="text/html"),
    )

    _input(page).click()

    _wait_hidden_rows(page, {"v0": False, "v1": False, "v2": True, "v3": False})
    assert page_errors == []


def test_a_pick_of_a_value_already_chipped_does_nothing(
    page: Page, session: RenderSession, page_errors: list[str]
):
    _serve(page, session, _picker(session, items=[_item("v0")]))
    _open(page)
    _wait_hidden_rows(page, {"v0": True, "v1": False, "v2": False})
    # Stands in for a row the script has not hidden yet.
    page.evaluate(
        """() => {
            document.querySelector('#p-results [data-value="v0"]').hidden = false;
        }"""
    )
    _record_changes(page)

    _pick(page, "v0").click()
    _settle(page)

    assert _chip_values(page) == ["v0"]
    assert _changes(page) == []
    assert _state(page) == OPEN
    assert _hidden_rows(page)["v0"] is False
    assert _has_focus(_pick(page, "v0"))
    assert page_errors == []


def test_a_single_item_picker_replaces_its_chip(
    page: Page, session: RenderSession, page_errors: list[str]
):
    _serve(page, session, _picker(session, items=[_item("v0")], max_items=1))
    _open(page)
    _wait_hidden_rows(page, {"v0": True, "v1": False, "v2": False})
    _record_changes(page)

    _pick(page, "v1").click()

    assert _chip_values(page) == ["v1"]
    assert _hidden_rows(page) == {"v0": False, "v1": True, "v2": False}
    assert _changes(page) == [
        {"values": ["v1"], "target": "p", "bubbles": True, "cancelable": False}
    ]
    assert page_errors == []


def test_a_multi_item_cap_still_appends(
    page: Page, session: RenderSession, page_errors: list[str]
):
    _serve(page, session, _picker(session, items=[_item("a")], max_items=3))
    _open(page)

    _pick(page, "v1").click()

    assert _chip_values(page) == ["a", "v1"]
    assert page_errors == []


def test_settles_outside_a_pickers_rows_are_ignored(
    page: Page, session: RenderSession, page_errors: list[str]
):
    body = (
        '<div id="outside"></div>'
        + _picker(session, "d", items=[_item("a")], disabled=True)
        + _picker(session)
    )
    _serve(page, session, body)

    page.evaluate(
        """() => {
            const settle = (target) => target.dispatchEvent(
                new CustomEvent('htmx:afterSettle', { bubbles: true })
            );
            settle(document);
            settle(document.getElementById('outside'));
            settle(document.querySelector('#d .pjx-roster-picker__chips'));
        }"""
    )
    _settle(page)

    assert _chip_values(page, "d") == ["a"]
    assert page_errors == []
