"""Browser tests for the roster picker across lazy next pages and chip swaps."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from pyjinhx.builtins.pjx_roster_results import PJXRosterResults
from pyjinhx.rendering.pipeline import render
from tests.browser.builtins.pjx_roster_picker._harness import (
    CANDIDATES,
    CLOSED,
    OPEN,
    _has_focus,
    _hidden_rows,
    _hint_hidden,
    _input,
    _pick,
    _picker,
    _settle,
    _state,
)
from tests.browser.builtins.pjx_roster_picker._swaps_helpers import (
    CHIP,
    SWAP_URL,
    _answer,
    _chip,
    _close_by_blur,
    _events,
    _exclude,
    _items,
    _open,
    _record_events,
    _serve,
    _swap,
    _validity,
    _values,
    _wait_values,
)

if TYPE_CHECKING:
    from playwright.sync_api import Page

    from pyjinhx.rendering.session import RenderSession


MORE_URL = "http://pjx.test/more"


def _row_values(page: Page, picker_id: str = "p") -> list[str]:
    return page.eval_on_selector_all(
        f"#{picker_id}-results [data-pjx-roster-pick]",
        "rows => rows.map((row) => row.dataset.value)",
    )


def _paged(
    page: Page, session: RenderSession, first_rows: int, chipped: str
) -> list[str]:
    """Serve a picker chipping chipped, whose search answers first_rows rows a0.. and a sentinel for b0 and b1."""
    first = PJXRosterResults(
        picker_id="p",
        items=_items(*(f"a{index}" for index in range(first_rows))),
        next_url=f"{MORE_URL}?cursor=2",
        next_cursor="2",
    )
    second = render(PJXRosterResults(picker_id="p", items=_items("b0", "b1")), session)
    requests = _serve(
        page,
        session,
        _picker(session, items=_items(chipped)),
        rows=render(first, session),
    )
    page.route(f"{MORE_URL}*", _answer(second))
    return requests


def test_a_lazy_next_page_arrives_with_chipped_rows_hidden_and_focus_kept(
    page: Page, session: RenderSession, page_errors: list[str]
):
    # Thirty rows overflow the list, so the sentinel waits for a scroll.
    _paged(page, session, first_rows=30, chipped="b1")
    _open(page)
    _settle(page)
    assert page.locator("#p-more-2").count() == 1
    _input(page).press("ArrowDown")
    assert _has_focus(_pick(page, "a0"))
    # Overwritten so a value the page lands with proves it was placed again.
    page.evaluate(
        "() => document.getElementById('p-results').style"
        ".setProperty('--pjx-roster-picker-room', '123px')"
    )

    with page.expect_request(f"{MORE_URL}*", timeout=5000):
        page.evaluate(
            "() => { const list = document.getElementById('p-results');"
            " list.scrollTop = list.scrollHeight; }"
        )
    page.wait_for_selector(
        '#p-results [data-value="b1"]', state="attached", timeout=5000
    )
    _settle(page)

    assert page.locator("#p-more-2").count() == 0
    assert _row_values(page) == [f"a{index}" for index in range(30)] + ["b0", "b1"]
    hidden = _hidden_rows(page)
    assert hidden["b1"] is True
    assert [value for value, flag in hidden.items() if flag] == ["b1"]
    assert _state(page) == OPEN
    room = page.evaluate(
        "() => document.getElementById('p-results').style"
        ".getPropertyValue('--pjx-roster-picker-room')"
    )
    assert room.endswith("px")
    assert room != "123px"
    assert _has_focus(_pick(page, "a0"))
    assert page_errors == []


def test_a_pick_from_a_lazy_next_page_is_excluded_from_the_next_search(
    page: Page, session: RenderSession, page_errors: list[str]
):
    # One row leaves the sentinel in view, so the next page loads on open.
    _paged(page, session, first_rows=1, chipped="a0")
    _open(page)
    page.wait_for_selector(
        '#p-results [data-value="b0"]', state="attached", timeout=5000
    )
    _settle(page)

    _pick(page, "b0").click()

    assert _values(page) == ["a0", "b0"]
    assert _hidden_rows(page)["b0"] is True
    assert _state(page) == CLOSED
    with page.expect_request(CANDIDATES, timeout=5000) as request:
        page.keyboard.type("P")
    assert _exclude(request.value.url) == ["a0,b0"]
    assert page_errors == []


def test_a_chip_swapped_for_another_value_moves_the_hidden_row(
    page: Page, session: RenderSession, page_errors: list[str]
):
    requests = _serve(
        page,
        session,
        _picker(session, items=_items("v0", "v1"), required=True),
        swap=_chip(session, "v2"),
    )
    _open(page)
    sent = len(requests)
    _record_events(page)

    _swap(page, CHIP.format(value="v0"), "outerHTML")
    _wait_values(page, ["v2", "v1"])
    _settle(page)

    assert _hidden_rows(page) == {"v0": False, "v1": True, "v2": True}
    assert _validity(page) == "v2,v1"
    assert _state(page) == OPEN
    assert _has_focus(_input(page))
    assert _events(page) == []
    # Past the 300 ms debounce, so a search the swap set off would have been sent.
    page.wait_for_timeout(300)
    assert len(requests) == sent
    assert page_errors == []


@pytest.mark.parametrize(
    ("selector", "swap", "answer"),
    [
        # One chip's outerHTML replaced by itself and a new one.
        (CHIP.format(value="v0"), "outerHTML", ("v0", "v2")),
        # A new chip appended to the chips.
        ("#p .pjx-roster-picker__chips", "beforeend", ("v2",)),
    ],
    ids=["outer", "beforeend"],
)
def test_a_chip_added_by_a_swap_reaches_the_cap_and_validity(
    page: Page,
    session: RenderSession,
    page_errors: list[str],
    selector: str,
    swap: str,
    answer: tuple[str, ...],
):
    _serve(
        page,
        session,
        _picker(session, items=_items("v0"), max_items=2, required=True),
        swap="".join(_chip(session, value) for value in answer),
    )
    _open(page)
    _close_by_blur(page)
    _record_events(page)

    _swap(page, selector, swap)
    _wait_values(page, ["v0", "v2"])
    _settle(page)

    assert _hidden_rows(page) == {"v0": True, "v1": False, "v2": True}
    assert _input(page).is_disabled()
    assert _hint_hidden(page) is False
    assert _validity(page) == "v0,v2"
    assert _state(page) == CLOSED
    assert _events(page) == []
    assert page_errors == []


def test_a_chip_removed_by_an_empty_swap_frees_its_row_cap_and_validity(
    page: Page, session: RenderSession, page_errors: list[str]
):
    _serve(
        page,
        session,
        _picker(session, items=_items("v0"), max_items=2, required=True),
        swap="",
    )
    _open(page)
    # Reaches the cap and closes the list, keeping its rows.
    _pick(page, "v1").click()
    assert _input(page).is_disabled()
    _record_events(page)

    _swap(page, CHIP.format(value="v0"), "outerHTML")
    _wait_values(page, ["v1"])
    _settle(page)

    assert _hidden_rows(page) == {"v0": False, "v1": True, "v2": False}
    assert not _input(page).is_disabled()
    assert _hint_hidden(page) is True
    assert _validity(page) == "v1"
    assert _state(page) == CLOSED
    assert _events(page) == []
    assert page_errors == []


def test_a_chip_removed_by_an_empty_swap_shows_its_row_in_an_open_list(
    page: Page, session: RenderSession, page_errors: list[str]
):
    _serve(page, session, _picker(session, items=_items("v0", "v1")), swap="")
    _open(page)
    _record_events(page)

    _swap(page, CHIP.format(value="v0"), "outerHTML")
    _wait_values(page, ["v1"])
    _settle(page)

    assert _hidden_rows(page) == {"v0": False, "v1": True, "v2": False}
    assert _state(page) == OPEN
    assert _has_focus(_input(page))
    assert _events(page) == []
    assert page_errors == []


def test_an_empty_chip_swap_leaves_another_picker_alone(
    page: Page, session: RenderSession, page_errors: list[str]
):
    body = _picker(session, items=_items("v0"), required=True) + _picker(
        session, "q", items=_items("v0", "v1"), max_items=2, required=True
    )
    _serve(page, session, body, swap="")

    _swap(page, CHIP.format(value="v0"), "outerHTML")
    _wait_values(page, [])
    _settle(page)

    assert _validity(page) == ""
    assert _values(page, "q") == ["v0", "v1"]
    assert _input(page, "q").is_disabled()
    assert _hint_hidden(page, "q") is False
    assert _validity(page, "q") == "v0,v1"
    assert page_errors == []


def test_a_failed_chip_swap_changes_nothing(
    page: Page, session: RenderSession, page_errors: list[str]
):
    _serve(
        page,
        session,
        _picker(session, items=_items("v0", "v1"), max_items=2, required=True),
    )
    # Registered last, so it answers /swap ahead of _serve's route.
    page.route(
        SWAP_URL,
        lambda route: route.fulfill(status=500, body="no", content_type="text/html"),
    )
    _record_events(page)

    # htmx swaps nothing for a 500.
    page.evaluate(
        "selector => htmx.ajax('GET', '/swap', {"
        " target: document.querySelector(selector), swap: 'outerHTML' })"
        ".catch(() => {})",
        CHIP.format(value="v0"),
    )
    _settle(page)

    assert _values(page) == ["v0", "v1"]
    assert _input(page).is_disabled()
    assert _hint_hidden(page) is False
    assert _validity(page) == "v0,v1"
    assert _events(page) == []
    assert page_errors == []


def test_an_empty_chip_swap_in_a_disabled_picker_throws_nothing(
    page: Page, session: RenderSession, page_errors: list[str]
):
    _serve(
        page,
        session,
        _picker(session, items=_items("v0", "v1"), disabled=True),
        swap="",
    )

    _swap(page, CHIP.format(value="v0"), "outerHTML")
    _wait_values(page, ["v1"])
    _settle(page)

    assert _hint_hidden(page) is True
    assert page_errors == []


def test_a_press_across_a_whole_picker_swap_leaves_no_error(
    page: Page, session: RenderSession, page_errors: list[str]
):
    requests = _serve(
        page, session, _picker(session), swap=_picker(session, items=_items("v1"))
    )
    _open(page)
    box = _input(page).bounding_box()
    assert box is not None
    page.mouse.move(box["x"] + 5, box["y"] + 5)
    page.mouse.down()

    _swap(page, "#p", "outerHTML")
    _wait_values(page, ["v1"])
    _settle(page)
    sent = len(requests)
    # Released far from any picker: the press ends outside the new one.
    page.mouse.move(700, 500)
    page.mouse.up()
    _settle(page)
    # Past the 300 ms debounce, so an open's search would have been sent.
    page.wait_for_timeout(300)

    assert _state(page) == CLOSED
    assert len(requests) == sent
    assert page_errors == []


def test_a_click_on_a_label_around_the_picker_still_opens_it(
    page: Page, session: RenderSession, page_errors: list[str]
):
    body = f'<label><span id="caption">Members</span>{_picker(session)}</label>'
    requests = _serve(page, session, body)

    page.click("#caption")
    page.wait_for_selector(
        "#p-results [data-pjx-roster-pick]", state="attached", timeout=5000
    )

    assert _has_focus(_input(page))
    assert _state(page) == OPEN
    assert len(requests) == 1
    assert page_errors == []
