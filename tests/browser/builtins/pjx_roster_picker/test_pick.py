"""Browser tests for picking rows into chips in the roster picker, including the item cap.

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

from typing import TYPE_CHECKING

from pyjinhx.builtins.pjx_roster_results import PJXRosterResults
from pyjinhx.rendering.pipeline import render
from tests.browser.builtins.pjx_roster_picker._harness import (
    CLOSED,
    OPEN,
    _has_focus,
    _hidden_rows,
    _hint_hidden,
    _input,
    _item,
    _pick,
    _picker,
    _settle,
    _state,
)
from tests.browser.builtins.pjx_roster_picker._pick_helpers import (
    _changes,
    _chip_inputs,
    _chip_values,
    _open,
    _record_changes,
    _remove,
    _serve,
    _wait_hidden_rows,
    _wait_last_query,
)

if TYPE_CHECKING:
    from playwright.sync_api import Page

    from pyjinhx.rendering.session import RenderSession


MORE_URL = "http://pjx.test/more"


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
