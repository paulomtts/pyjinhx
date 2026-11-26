"""Browser tests for the roster picker across whole-picker and results-page htmx swaps."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from pyjinhx.builtins.pjx_roster_results import PJXRosterResults
from pyjinhx.rendering.pipeline import render
from tests.browser.builtins.pjx_roster_picker._swaps_helpers import (
    CHIP,
    CLOSED,
    OPEN,
    _chip,
    _close_by_blur,
    _events,
    _exclude,
    _has_focus,
    _hidden_rows,
    _hint_hidden,
    _input,
    _items,
    _open,
    _pick,
    _picker,
    _record_events,
    _serve,
    _settle,
    _state,
    _swap,
    _validity,
    _values,
    _wait_values,
)

if TYPE_CHECKING:
    from playwright.sync_api import Page

    from pyjinhx.rendering.session import RenderSession


def _focus_in_picker(page: Page, picker_id: str = "p") -> bool:
    """Whether focus is in the picker's search box or its list, wherever the list lives."""
    return page.evaluate(
        """id => {
            const active = document.activeElement;
            return document.querySelector(`#${id} .pjx-roster-picker__search`).contains(active)
                || document.getElementById(`${id}-results`).contains(active);
        }""",
        picker_id,
    )


@pytest.mark.parametrize("old_state", ["open", "closed"])
def test_whole_picker_swap_starts_closed_and_agrees_with_its_chips(
    page: Page, session: RenderSession, page_errors: list[str], old_state: str
):
    fresh = _picker(session, items=_items("v1", "v2"), max_items=2, required=True)
    requests = _serve(
        page,
        session,
        _picker(session, items=_items("v0"), max_items=3, required=True),
        swap=fresh,
    )
    if old_state == "open":
        _open(page)
    sent = len(requests)

    _swap(page, "#p", "outerHTML")
    _wait_values(page, ["v1", "v2"])
    _settle(page)

    counts = page.evaluate(
        """() => [
            document.querySelectorAll('#p').length,
            document.querySelectorAll('#p-results').length,
            document.getElementById('p-results').childElementCount,
        ]"""
    )
    assert counts == [1, 1, 0]
    assert _state(page) == CLOSED
    assert _input(page).is_disabled()
    assert _hint_hidden(page) is False
    assert _validity(page) == "v1,v2"
    assert not _has_focus(_input(page))
    # Past the 300 ms debounce, so an open's search would have been sent.
    page.wait_for_timeout(300)
    assert len(requests) == sent
    assert page_errors == []


def test_whole_picker_swap_forgets_the_kept_query_and_excludes_new_chips(
    page: Page, session: RenderSession, page_errors: list[str]
):
    requests = _serve(
        page,
        session,
        _picker(session, items=_items("v0")),
        swap=_picker(session, items=_items("v1")),
    )
    _open(page)
    _swap(page, "#p", "outerHTML")
    _wait_values(page, ["v1"])
    _settle(page)
    sent = len(requests)

    _open(page)
    # Past the 300 ms debounce, so a second search would have been sent.
    page.wait_for_timeout(500)

    assert len(requests) == sent + 1
    assert _exclude(requests[-1]) == ["v1"]
    assert _hidden_rows(page) == {"v0": False, "v1": True, "v2": False}
    assert page_errors == []


def test_a_pick_in_a_swapped_in_picker_works_without_rebinding(
    page: Page, session: RenderSession, page_errors: list[str]
):
    _serve(
        page,
        session,
        _picker(session, items=_items("v0")),
        swap=_picker(session, items=_items("v1")),
    )
    _swap(page, "#p", "outerHTML")
    _wait_values(page, ["v1"])
    _open(page)
    _record_events(page)

    _pick(page, "v0").click()

    assert _values(page) == ["v1", "v0"]
    assert _hidden_rows(page) == {"v0": True, "v1": True, "v2": False}
    assert _state(page) == CLOSED
    assert _events(page) == [
        {"name": "before-pick", "target": "p", "connected": True},
        {"name": "pick", "target": "p", "connected": True},
        {"name": "change", "target": "p", "connected": True},
    ]
    assert page_errors == []


def test_outer_swap_of_an_open_portal_picker_leaves_no_list_on_body(
    page: Page, session: RenderSession, page_errors: list[str]
):
    _serve(
        page,
        session,
        _picker(session, items=_items("v0"), portal=True),
        swap=_picker(session, items=_items("v1"), portal=True),
    )
    # Opened by typing, not focus: a focused box removed by the swap could
    # close the list through focusout and hide a missing cleanup.
    page.evaluate(
        "() => document.querySelector('#p .pjx-roster-picker__input')"
        ".dispatchEvent(new Event('input', { bubbles: true }))"
    )
    page.wait_for_selector(
        "#p-results [data-pjx-roster-pick]", state="attached", timeout=5000
    )
    _settle(page)
    assert page.evaluate(
        "() => document.getElementById('p-results').parentElement === document.body"
    )

    _swap(page, "#p", "outerHTML")
    _wait_values(page, ["v1"])
    _settle(page)

    lists = page.evaluate(
        """() => ({
            onBody: document.querySelectorAll('body > .pjx-roster-picker__results').length,
            count: document.querySelectorAll('#p-results').length,
            inPicker: document.getElementById('p').contains(document.getElementById('p-results')),
        })"""
    )
    assert lists == {"onBody": 0, "count": 1, "inPicker": True}
    assert _state(page) == CLOSED
    assert page_errors == []


def test_a_chip_rerendered_with_its_value_keeps_the_selection(
    page: Page, session: RenderSession, page_errors: list[str]
):
    requests = _serve(
        page,
        session,
        _picker(session, items=_items("v0", "v1"), max_items=3, required=True),
        swap=_chip(session, "v0", label="Renamed"),
    )
    _open(page)
    _close_by_blur(page)
    sent = len(requests)
    _record_events(page)

    _swap(page, CHIP.format(value="v0"), "outerHTML")
    page.wait_for_selector("#chip-v0", timeout=5000)
    _settle(page)

    assert _values(page) == ["v0", "v1"]
    assert (
        page.locator("#chip-v0 .pjx-roster-picker__chip-label").inner_text()
        == "Renamed"
    )
    assert _hidden_rows(page) == {"v0": True, "v1": True, "v2": False}
    assert _state(page) == CLOSED
    assert not _input(page).is_disabled()
    assert _hint_hidden(page) is True
    assert _validity(page) == "v0,v1"
    assert _events(page) == []
    assert not _has_focus(_input(page))
    # Past the 300 ms debounce, so an open's search would have been sent.
    page.wait_for_timeout(300)
    assert len(requests) == sent
    assert page_errors == []


def test_a_results_page_swapped_into_an_open_list_hides_chipped_rows(
    page: Page, session: RenderSession, page_errors: list[str]
):
    results = render(
        PJXRosterResults(picker_id="p", items=_items("v0", "v3", "v4")), session
    )
    _serve(page, session, _picker(session, items=_items("v0")), swap=results)
    _open(page)

    _swap(page, "#p-results", "innerHTML")
    page.wait_for_selector(
        '#p-results [data-value="v3"]', state="attached", timeout=5000
    )
    _settle(page)

    assert _hidden_rows(page) == {"v0": True, "v3": False, "v4": False}
    assert _state(page) == OPEN
    assert _has_focus(_input(page))

    _record_events(page)
    _pick(page, "v3").click()

    assert _values(page) == ["v0", "v3"]
    assert _hidden_rows(page) == {"v0": True, "v3": True, "v4": False}
    assert _state(page) == CLOSED
    assert [event["name"] for event in _events(page)] == [
        "before-pick",
        "pick",
        "change",
    ]
    assert page_errors == []


def test_a_results_page_swapped_into_a_closed_list_stays_closed(
    page: Page, session: RenderSession, page_errors: list[str]
):
    results = render(PJXRosterResults(picker_id="p", items=_items("v0", "v3")), session)
    _serve(page, session, _picker(session, items=_items("v0")), swap=results)

    _swap(page, "#p-results", "innerHTML")
    page.wait_for_selector(
        '#p-results [data-value="v3"]', state="attached", timeout=5000
    )
    _settle(page)

    assert _state(page) == CLOSED
    assert _hidden_rows(page) == {"v0": True, "v3": False}
    assert page_errors == []


def test_a_results_swap_under_a_focused_row_does_not_strand_an_open_list(
    page: Page, session: RenderSession, page_errors: list[str]
):
    results = render(PJXRosterResults(picker_id="p", items=_items("v0", "v3")), session)
    _serve(page, session, _picker(session, items=_items("v0")), swap=results)
    _open(page)
    _input(page).press("ArrowDown")
    assert _has_focus(_pick(page, "v1"))

    _swap(page, "#p-results", "innerHTML")
    page.wait_for_selector(
        '#p-results [data-value="v3"]', state="attached", timeout=5000
    )
    _settle(page)

    assert _state(page) == CLOSED or _focus_in_picker(page)
    page.mouse.click(700, 500)
    _settle(page)
    assert _state(page) == CLOSED
    assert page_errors == []
