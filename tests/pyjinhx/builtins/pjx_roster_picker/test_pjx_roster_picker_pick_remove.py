"""PJXRosterPicker's pick and remove, and the events they fire, in real chromium with the vendored htmx.

Every page loads the committed pjx_roster_picker.js, so these tests exercise
the asset that ships. The candidates stub logs each request URL and answers
with three people, v0 to v2, whatever exclude says, so a row for a chipped
value really arrives and the script has to hide it. A change recorder
installed before the click logs every pjx:roster-picker:change. An event
recorder logs before-pick, pick, before-remove, remove and change with the
chips present when each fired, and can refuse or throw from one of them. A
negative is proven by letting a beat pass and checking nothing changed.
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

# Listens on document, so every recorded event bubbled. window.refuse is read
# at dispatch time, so a test can stop refusing between two clicks.
RECORD_EVENTS = """({ refuse, explode }) => {
    window.events = [];
    window.refuse = refuse;
    for (const name of ['before-pick', 'pick', 'before-remove', 'remove', 'change']) {
        document.addEventListener(`pjx:roster-picker:${name}`, (event) => {
            window.events.push({
                name: name,
                detail: event.detail,
                target: event.target.id,
                bubbles: event.bubbles,
                cancelable: event.cancelable,
                chips: Array.from(
                    event.target.querySelectorAll(
                        '.pjx-roster-picker__chips > [data-pjx-roster-chip] > .pjx-roster-picker__chip-input'
                    ),
                    (input) => input.value
                ),
            });
            if (window.refuse === name) event.preventDefault();
            if (explode === name) throw new Error(`a broken ${name} listener`);
        });
    }
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


def _record_events(
    page: Page, refuse: str | None = None, explode: str | None = None
) -> None:
    """Log every picker event; refuse cancels the named one, explode throws from its listener."""
    page.evaluate(RECORD_EVENTS, {"refuse": refuse, "explode": explode})


def _events(page: Page) -> list[dict[str, Any]]:
    return page.evaluate("() => window.events")


def _names(page: Page) -> list[str]:
    return [event["name"] for event in _events(page)]


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
    # Replacing, never full: the box stays usable.
    assert not _input(page).is_disabled()
    assert _hint_hidden(page) is True
    assert _has_focus(_input(page))
    assert page_errors == []


def test_a_multi_item_cap_still_appends(
    page: Page, session: RenderSession, page_errors: list[str]
):
    _serve(page, session, _picker(session, items=[_item("a")], max_items=3))
    _open(page)

    _pick(page, "v1").click()

    assert _chip_values(page) == ["a", "v1"]
    assert not _input(page).is_disabled()
    assert _hint_hidden(page) is True
    assert _has_focus(_input(page))
    assert page_errors == []


def test_a_pick_reaching_the_cap_disables_the_input_and_focuses_the_new_chip(
    page: Page, session: RenderSession, page_errors: list[str]
):
    _serve(page, session, _picker(session, items=[_item("a")], max_items=2))
    _open(page)
    _record_changes(page)

    _pick(page, "v1").click()

    assert _chip_values(page) == ["a", "v1"]
    assert _input(page).is_disabled()
    assert _hint_hidden(page) is False
    assert _has_focus(_remove(page, "v1"))
    assert _state(page) == CLOSED
    assert _changes(page) == [
        {"values": ["a", "v1"], "target": "p", "bubbles": True, "cancelable": False}
    ]
    assert page_errors == []


def test_enter_on_a_row_reaching_the_cap_focuses_the_new_chip(
    page: Page, session: RenderSession, page_errors: list[str]
):
    _serve(page, session, _picker(session, items=[_item("a")], max_items=2))
    _open(page)
    _pick(page, "v1").focus()

    page.keyboard.press("Enter")

    assert _chip_values(page) == ["a", "v1"]
    assert _input(page).is_disabled()
    assert _hint_hidden(page) is False
    assert _has_focus(_remove(page, "v1"))
    assert _state(page) == CLOSED
    assert page_errors == []


def test_clicking_a_capped_input_neither_opens_nor_searches(
    page: Page, session: RenderSession, page_errors: list[str]
):
    requests = _serve(page, session, _picker(session, items=[_item("a")], max_items=2))
    _open(page)
    _pick(page, "v1").click()
    sent = len(requests)

    # force: Playwright would otherwise wait for the disabled box to enable.
    _input(page).click(force=True)
    # Past the 300 ms debounce, so an open's search would have been sent.
    page.wait_for_timeout(500)

    assert _state(page) == CLOSED
    assert len(requests) == sent
    assert page_errors == []


def test_capping_one_picker_leaves_the_other_alone(
    page: Page, session: RenderSession, page_errors: list[str]
):
    # Side by side, so neither open list covers the other picker's box.
    body = (
        '<div style="display: flex; gap: 40px">'
        f'<div style="flex: 1">{_picker(session, "p", items=[_item("a")], max_items=2)}</div>'
        f'<div style="flex: 1">{_picker(session, "q", items=[_item("b")], max_items=2)}</div>'
        "</div>"
    )
    _serve(page, session, body)
    _open(page, "p")

    _pick(page, "v1", "p").click()

    assert _input(page, "p").is_disabled()
    assert not _input(page, "q").is_disabled()
    assert _hint_hidden(page, "q") is True
    assert page_errors == []


def test_an_unbounded_picker_never_caps(
    page: Page, session: RenderSession, page_errors: list[str]
):
    _serve(page, session, _picker(session))
    _open(page)

    for value in ("v0", "v1", "v2"):
        # A pick closes the list; the box already has focus, so a click reopens it.
        _input(page).click()
        _pick(page, value).click()

    assert _chip_values(page) == ["v0", "v1", "v2"]
    assert not _input(page).is_disabled()
    assert _hint_hidden(page) is True
    assert page_errors == []


def test_a_capped_picker_ignores_a_pick(
    page: Page, session: RenderSession, page_errors: list[str]
):
    _serve(page, session, _picker(session, items=[_item("a")], max_items=2))
    _open(page)
    _record_changes(page)
    _pick(page, "v1").click()

    # The closed list hides the row, so only a script can still click it.
    page.evaluate(
        """() => document.querySelector('#p-results [data-value="v2"]').click()"""
    )
    _settle(page)

    assert _chip_values(page) == ["a", "v1"]
    assert len(_changes(page)) == 1
    assert _input(page).is_disabled()
    assert _hint_hidden(page) is False
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


def test_a_remove_drops_the_chip_and_shows_its_row(
    page: Page, session: RenderSession, page_errors: list[str]
):
    _serve(page, session, _picker(session))
    _open(page)
    _pick(page, "v1").click()

    _remove(page, "v1").click()

    assert _chip_values(page) == []
    assert _hidden_rows(page) == {"v0": False, "v1": False, "v2": False}
    assert page_errors == []


def test_a_remove_moves_focus_to_the_next_chips_remove_button(
    page: Page, session: RenderSession, page_errors: list[str]
):
    items = [_item("a"), _item("b"), _item("c")]
    _serve(page, session, _picker(session, items=items))

    _remove(page, "b").click()

    assert _chip_values(page) == ["a", "c"]
    assert _has_focus(_remove(page, "c"))
    assert _state(page) == CLOSED
    assert page_errors == []


def test_a_remove_of_the_last_chip_focuses_the_box_without_opening(
    page: Page, session: RenderSession, page_errors: list[str]
):
    requests = _serve(page, session, _picker(session, items=[_item("a"), _item("b")]))

    _remove(page, "b").click()

    assert _has_focus(_input(page))
    assert _state(page) == CLOSED
    # Past the 300 ms debounce, so an open's search would have been sent.
    page.wait_for_timeout(500)
    assert _state(page) == CLOSED
    assert requests == []
    assert page_errors == []


def test_a_remove_fires_one_change_with_the_rest(
    page: Page, session: RenderSession, page_errors: list[str]
):
    items = [_item("a"), _item("b"), _item("c")]
    _serve(page, session, _picker(session, items=items))
    _record_changes(page)

    _remove(page, "a").click()

    assert _changes(page) == [
        {"values": ["b", "c"], "target": "p", "bubbles": True, "cancelable": False}
    ]
    assert page_errors == []


def test_removing_a_chip_from_a_capped_picker_reenables_the_input(
    page: Page, session: RenderSession, page_errors: list[str]
):
    _serve(page, session, _picker(session, items=[_item("a")], max_items=2))
    _open(page)
    _pick(page, "v1").click()
    _record_changes(page)

    _remove(page, "a").click()

    assert not _input(page).is_disabled()
    assert _hint_hidden(page) is True
    assert _has_focus(_remove(page, "v1"))
    assert _changes(page) == [
        {"values": ["v1"], "target": "p", "bubbles": True, "cancelable": False}
    ]
    assert _state(page) == CLOSED
    assert page_errors == []


def test_removing_the_last_chip_from_a_cap_refocuses_the_input(
    page: Page, session: RenderSession, page_errors: list[str]
):
    requests = _serve(page, session, _picker(session, items=[_item("a")], max_items=2))
    _open(page)
    _pick(page, "v1").click()
    sent = len(requests)

    _remove(page, "v1").click()

    assert not _input(page).is_disabled()
    assert _hint_hidden(page) is True
    assert _has_focus(_input(page))
    assert _state(page) == CLOSED
    # Past the 300 ms debounce, so an open's search would have been sent.
    page.wait_for_timeout(500)
    assert _state(page) == CLOSED
    assert len(requests) == sent
    assert page_errors == []


def test_a_picker_rendered_full_starts_capped(
    page: Page, session: RenderSession, page_errors: list[str]
):
    requests = _serve(
        page, session, _picker(session, items=[_item("a"), _item("b")], max_items=2)
    )
    _settle(page)

    assert _input(page).is_disabled()
    assert _hint_hidden(page) is False
    assert requests == []

    _remove(page, "a").click()

    assert not _input(page).is_disabled()
    assert _hint_hidden(page) is True

    _open(page)
    _pick(page, "v1").click()

    assert _chip_values(page) == ["b", "v1"]
    assert _input(page).is_disabled()
    assert _hint_hidden(page) is False
    assert _has_focus(_remove(page, "v1"))
    assert page_errors == []


def test_a_remove_of_an_unlisted_value_forgets_the_last_query(
    page: Page, session: RenderSession, page_errors: list[str]
):
    _serve(page, session, _picker(session, items=[_item("a")]))
    _open(page)
    # Closed, so the open list does not cover the chip.
    page.keyboard.press("Escape")

    _remove(page, "a").click()

    assert _last_query(page) is None
    with page.expect_request(CANDIDATES, timeout=5000):
        _input(page).click()
    assert page_errors == []


def test_a_remove_of_a_listed_value_keeps_the_last_query(
    page: Page, session: RenderSession, page_errors: list[str]
):
    requests = _serve(page, session, _picker(session))
    _open(page)
    _pick(page, "v1").click()

    _remove(page, "v1").click()

    assert _last_query(page) == ""
    _input(page).click()
    # Past the 300 ms debounce, so a search would have been sent.
    page.wait_for_timeout(500)
    assert len(requests) == 1
    assert _state(page) == OPEN
    assert _hidden_rows(page) == {"v0": False, "v1": False, "v2": False}
    assert page_errors == []


def test_pick_and_remove_buttons_outside_a_picker_are_ignored(
    page: Page, session: RenderSession, page_errors: list[str]
):
    stray = (
        '<button type="button" id="stray-pick" data-pjx-roster-pick data-value="x">'
        "Stray</button>"
        '<div id="stray-chip" data-pjx-roster-chip>'
        '<input type="hidden" class="pjx-roster-picker__chip-input" value="y">'
        '<button type="button" id="stray-remove" data-pjx-roster-remove>Remove</button>'
        "</div>"
    )
    _serve(page, session, stray + _picker(session, items=[_item("a")]))
    _record_changes(page)

    page.click("#stray-pick")
    page.click("#stray-remove")
    _settle(page)

    assert page.locator("#stray-chip").count() == 1
    assert _chip_values(page) == ["a"]
    assert _changes(page) == []
    assert page_errors == []


def test_a_pick_fires_before_pick_pick_then_change(
    page: Page, session: RenderSession, page_errors: list[str]
):
    _serve(page, session, _picker(session))
    _open(page)
    _record_events(page)

    _pick(page, "v1").click()

    assert [(event["name"], event["chips"]) for event in _events(page)] == [
        ("before-pick", []),
        ("pick", ["v1"]),
        ("change", ["v1"]),
    ]
    assert page_errors == []


def test_pick_events_carry_the_value_and_bubble_from_the_picker(
    page: Page, session: RenderSession, page_errors: list[str]
):
    _serve(page, session, _picker(session))
    _open(page)
    _record_events(page)

    _pick(page, "v1").click()

    assert _events(page)[:2] == [
        {
            "name": "before-pick",
            "detail": {"value": "v1"},
            "target": "p",
            "bubbles": True,
            "cancelable": True,
            "chips": [],
        },
        {
            "name": "pick",
            "detail": {"value": "v1"},
            "target": "p",
            "bubbles": True,
            "cancelable": False,
            "chips": ["v1"],
        },
    ]
    assert page_errors == []


def test_a_canceled_before_pick_adds_nothing_and_keeps_the_list_open(
    page: Page, session: RenderSession, page_errors: list[str]
):
    _serve(page, session, _picker(session))
    _open(page)
    page.keyboard.type("Pe")
    _wait_last_query(page, "Pe")
    _record_events(page, refuse="before-pick")

    _pick(page, "v1").click()
    _settle(page)

    assert _chip_values(page) == []
    assert _state(page) == OPEN
    assert _hidden_rows(page) == {"v0": False, "v1": False, "v2": False}
    assert _input(page).input_value() == "Pe"
    assert _last_query(page) == "Pe"
    # The click's own focus; the script moved nothing.
    assert _has_focus(_pick(page, "v1"))
    assert _names(page) == ["before-pick"]
    assert page_errors == []


def test_a_canceled_before_pick_keeps_the_invalid_mark(
    page: Page, session: RenderSession, page_errors: list[str]
):
    _serve(page, session, _picker(session))
    _open(page)
    # Stands in for the browser's invalid event, the only thing that marks it.
    page.evaluate(
        """() => {
            document.getElementById('p').classList.add('pjx-roster-picker--invalid');
            document.querySelector('#p .pjx-roster-picker__input').setAttribute('aria-invalid', 'true');
        }"""
    )
    _record_events(page, refuse="before-pick")

    _pick(page, "v1").click()
    _settle(page)

    marked = page.evaluate(
        """() => [
            document.getElementById('p').classList.contains('pjx-roster-picker--invalid'),
            document.querySelector('#p .pjx-roster-picker__input').getAttribute('aria-invalid'),
        ]"""
    )
    assert marked == [True, "true"]
    assert _chip_values(page) == []
    assert page_errors == []


def test_a_pick_after_a_refused_one_goes_through(
    page: Page, session: RenderSession, page_errors: list[str]
):
    _serve(page, session, _picker(session))
    _open(page)
    _record_events(page, refuse="before-pick")
    _pick(page, "v1").click()
    _settle(page)
    page.evaluate("() => { window.refuse = null; }")

    _pick(page, "v1").click()

    assert _chip_values(page) == ["v1"]
    assert _state(page) == CLOSED
    assert _names(page) == ["before-pick", "before-pick", "pick", "change"]
    assert page_errors == []


def test_a_throwing_before_pick_listener_does_not_refuse_the_pick(
    page: Page, session: RenderSession, page_errors: list[str]
):
    _serve(page, session, _picker(session))
    _open(page)
    _record_events(page, explode="before-pick")

    _pick(page, "v1").click()
    _settle(page)

    assert _chip_values(page) == ["v1"]
    assert _names(page) == ["before-pick", "pick", "change"]
    # dispatchEvent reports a listener's error and carries on.
    assert len(page_errors) == 1
    assert "a broken before-pick listener" in page_errors[0]


def test_an_ignored_pick_fires_no_before_pick(
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
    _record_events(page)

    _pick(page, "v0").click()
    _settle(page)

    assert _chip_values(page) == ["v0"]
    assert _events(page) == []
    assert page_errors == []


def test_a_single_item_swap_fires_only_pick_events(
    page: Page, session: RenderSession, page_errors: list[str]
):
    _serve(page, session, _picker(session, items=[_item("a")], max_items=1))
    _open(page)
    _record_events(page)

    _pick(page, "v1").click()

    assert [(event["name"], event["chips"]) for event in _events(page)] == [
        ("before-pick", ["a"]),
        ("pick", ["v1"]),
        ("change", ["v1"]),
    ]
    assert page_errors == []


def test_a_canceled_single_item_swap_keeps_the_old_chip(
    page: Page, session: RenderSession, page_errors: list[str]
):
    _serve(page, session, _picker(session, items=[_item("a")], max_items=1))
    _open(page)
    _record_events(page, refuse="before-pick")

    _pick(page, "v1").click()
    _settle(page)

    assert _chip_values(page) == ["a"]
    assert _state(page) == OPEN
    assert _names(page) == ["before-pick"]
    assert page_errors == []


def test_a_remove_fires_before_remove_remove_then_change(
    page: Page, session: RenderSession, page_errors: list[str]
):
    items = [_item("a"), _item("b"), _item("c")]
    _serve(page, session, _picker(session, items=items))
    _record_events(page)

    _remove(page, "b").click()

    assert [(event["name"], event["chips"]) for event in _events(page)] == [
        ("before-remove", ["a", "b", "c"]),
        ("remove", ["a", "c"]),
        ("change", ["a", "c"]),
    ]
    assert page_errors == []


def test_remove_events_carry_the_value_and_bubble_from_the_picker(
    page: Page, session: RenderSession, page_errors: list[str]
):
    _serve(page, session, _picker(session, items=[_item("a"), _item("b")]))
    _record_events(page)

    _remove(page, "a").click()

    assert _events(page)[:2] == [
        {
            "name": "before-remove",
            "detail": {"value": "a"},
            "target": "p",
            "bubbles": True,
            "cancelable": True,
            "chips": ["a", "b"],
        },
        {
            "name": "remove",
            "detail": {"value": "a"},
            "target": "p",
            "bubbles": True,
            "cancelable": False,
            "chips": ["b"],
        },
    ]
    assert page_errors == []


def test_a_canceled_before_remove_keeps_the_chip(
    page: Page, session: RenderSession, page_errors: list[str]
):
    _serve(page, session, _picker(session))
    _open(page)
    _pick(page, "v1").click()
    _record_events(page, refuse="before-remove")

    _remove(page, "v1").click()
    _settle(page)

    assert _chip_values(page) == ["v1"]
    assert _hidden_rows(page) == {"v0": False, "v1": True, "v2": False}
    # The click's own focus; the script moved nothing.
    assert _has_focus(_remove(page, "v1"))
    assert _names(page) == ["before-remove"]
    assert page_errors == []


def test_a_canceled_remove_on_a_capped_picker_stays_capped(
    page: Page, session: RenderSession, page_errors: list[str]
):
    # max_items=1 never caps (it swaps), so the smallest capped picker is two of two.
    _serve(page, session, _picker(session, items=[_item("a"), _item("b")], max_items=2))
    _settle(page)
    _record_events(page, refuse="before-remove")

    _remove(page, "a").click()
    _settle(page)

    assert _chip_values(page) == ["a", "b"]
    assert _input(page).is_disabled()
    assert _hint_hidden(page) is False
    assert _names(page) == ["before-remove"]
    assert page_errors == []


def test_a_canceled_remove_of_an_unlisted_value_keeps_the_last_query(
    page: Page, session: RenderSession, page_errors: list[str]
):
    _serve(page, session, _picker(session, items=[_item("a")]))
    _open(page)
    # Closed, so the open list does not cover the chip.
    page.keyboard.press("Escape")
    _record_events(page, refuse="before-remove")

    _remove(page, "a").click()
    _settle(page)

    assert _chip_values(page) == ["a"]
    assert _last_query(page) == ""
    assert page_errors == []
