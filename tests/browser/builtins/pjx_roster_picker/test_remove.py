"""Browser tests for removing chips from the roster picker."""

from __future__ import annotations

from typing import TYPE_CHECKING

from tests.browser.builtins.pjx_roster_picker._harness import (
    CANDIDATES,
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
    _chip_values,
    _last_query,
    _open,
    _record_changes,
    _remove,
    _serve,
)

if TYPE_CHECKING:
    from playwright.sync_api import Page

    from pyjinhx.rendering.session import RenderSession


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
