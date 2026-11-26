"""Browser tests for the roster picker's before-pick, pick, before-remove and remove events."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

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
    _chip_values,
    _last_query,
    _open,
    _remove,
    _serve,
    _wait_hidden_rows,
    _wait_last_query,
)

if TYPE_CHECKING:
    from playwright.sync_api import Page

    from pyjinhx.rendering.session import RenderSession


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


def _record_events(
    page: Page, refuse: str | None = None, explode: str | None = None
) -> None:
    """Log every picker event; refuse cancels the named one, explode throws from its listener."""
    page.evaluate(RECORD_EVENTS, {"refuse": refuse, "explode": explode})


def _events(page: Page) -> list[dict[str, Any]]:
    return page.evaluate("() => window.events")


def _names(page: Page) -> list[str]:
    return [event["name"] for event in _events(page)]


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
