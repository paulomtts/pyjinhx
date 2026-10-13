"""PJXRosterPicker opening and closing, in real chromium with the vendored htmx.

Every page loads the committed pjx_roster_picker.js, so these tests exercise
the asset that ships. An init script counts roster-picker-open per picker and
records the Escape presses that reach window. A negative is proven by letting
a beat pass and checking nothing changed.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any
from urllib.parse import parse_qs, urlsplit

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
HTMX_TAG = f"<script>{read_vendored_htmx()}</script>"
ASSET_TAG = f"<script>{ASSET}</script>"
PICKS = "#p-results [data-pjx-roster-pick]"
OPEN = ("true", False)
CLOSED = ("false", True)

# roster-picker-open does not bubble, so only a capturing listener on document
# hears it. The capturing keydown listener keeps the Escape and ArrowDown
# events themselves, so their final defaultPrevented can be read once
# dispatch is over.
RECORDER = """
window.opens = {};
window.escapesAtWindow = [];
document.addEventListener('roster-picker-open', (event) => {
    const id = event.target.closest('[data-pjx-roster-picker]').id;
    window.opens[id] = (window.opens[id] || 0) + 1;
}, true);
document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape') window.lastEscape = event;
    if (event.key === 'ArrowDown') window.lastArrowDown = event;
}, true);
window.addEventListener('keydown', (event) => {
    if (event.key === 'Escape') window.escapesAtWindow.push(event.defaultPrevented);
});
"""


def _picker(session: RenderSession, picker_id: str = "p", **kwargs: Any) -> str:
    return render(
        PJXRosterPicker(
            id=picker_id, name="members", candidates_url=CANDIDATES_URL, **kwargs
        ),
        session,
    )


def _serve(
    page: Page,
    session: RenderSession,
    body: str,
    scripts: str = HTMX_TAG + ASSET_TAG,
) -> list[str]:
    """Load body with the CSS and scripts, answer candidates with three rows, return the request log."""
    items = [
        PJXRosterItem(value=f"v{index}", label=f"Person {index}") for index in range(3)
    ]
    rows = render(PJXRosterResults(picker_id="p", items=items), session)
    html = f"<html><head><style>{CSS}</style></head><body>{body}{scripts}</body></html>"
    requests: list[str] = []

    def candidates(route: Route) -> None:
        requests.append(route.request.url)
        route.fulfill(body=rows, content_type="text/html")

    page.add_init_script(RECORDER)
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


def _opens(page: Page, picker_id: str = "p") -> int:
    return page.evaluate("id => window.opens[id] || 0", picker_id)


def _input_has_focus(page: Page, picker_id: str = "p") -> bool:
    return page.evaluate(
        "id => document.activeElement === document.querySelector(`#${id} .pjx-roster-picker__input`)",
        picker_id,
    )


def _focused_row(page: Page, picker_id: str = "p") -> str | None:
    """The value of the focused result row in this picker's list, or None."""
    return page.evaluate(
        """id => {
            const active = document.activeElement;
            return active && active.matches(`#${id}-results [data-pjx-roster-pick]`)
                ? active.dataset.value
                : null;
        }""",
        picker_id,
    )


def _wait_rows_hidden(page: Page, values: list[str], picker_id: str = "p") -> None:
    """Wait until the list holds a row for each value and every one is hidden."""
    page.wait_for_function(
        """([id, values]) => values.every((value) => {
            const row = document.querySelector(
                `#${id}-results [data-pjx-roster-pick][data-value="${value}"]`
            );
            return row !== null && row.hidden;
        })""",
        arg=[picker_id, values],
        timeout=5000,
    )


def _wait_last_query_empty(page: Page, picker_id: str = "p") -> None:
    """Wait until the box has recorded a successful search for empty text."""
    page.wait_for_function(
        """id => document.querySelector(`#${id} .pjx-roster-picker__input`)
            .getAttribute('data-last-query') === ''""",
        arg=picker_id,
        timeout=5000,
    )


def _arrow_down_prevented(page: Page) -> bool:
    return page.evaluate("() => window.lastArrowDown.defaultPrevented")


def test_click_opens_the_list_and_asks_once(
    page: Page, session: RenderSession, page_errors: list[str]
):
    requests = _serve(page, session, _picker(session))

    with page.expect_request(CANDIDATES, timeout=5000) as request:
        _input(page).click()
        # A mouse press focuses the box and then clicks it: one open between them.
        assert _state(page) == OPEN
        assert _opens(page) == 1
    # Past the 300 ms debounce, so a second search would have been sent.
    page.wait_for_timeout(500)

    query = parse_qs(urlsplit(request.value.url).query, keep_blank_values=True)
    assert query == {"q": [""], "exclude": [""], "picker_id": ["p"]}
    assert len(requests) == 1
    assert page_errors == []


def test_keyboard_focus_opens_the_list(
    page: Page, session: RenderSession, page_errors: list[str]
):
    body = '<button id="before" type="button">Before</button>' + _picker(session)
    _serve(page, session, body)

    page.focus("#before")
    page.keyboard.press("Tab")

    assert _input_has_focus(page)
    assert _state(page) == OPEN
    assert _opens(page) == 1
    assert page_errors == []


def test_a_second_click_on_an_open_list_does_nothing(
    page: Page, session: RenderSession, page_errors: list[str]
):
    _serve(page, session, _picker(session))

    _input(page).click()
    _input(page).click()
    _settle(page)

    assert _state(page) == OPEN
    assert _opens(page) == 1
    assert page_errors == []


def test_the_script_loaded_twice_binds_once(
    page: Page, session: RenderSession, page_errors: list[str]
):
    # A second binding would be invisible to clicks and Escape, since each
    # handler sees the state the first one left, so count what the second
    # copy hands to document.addEventListener while it runs.
    count_binds = """<script>
        window.firstNamespace = window.pjx.rosterPicker;
        window.secondCopyBinds = 0;
        document.addEventListener = function (...args) {
            window.secondCopyBinds += 1;
            return EventTarget.prototype.addEventListener.apply(this, args);
        };
    </script>"""
    stop_counting = "<script>delete document.addEventListener;</script>"
    scripts = HTMX_TAG + ASSET_TAG + count_binds + ASSET_TAG + stop_counting
    _serve(page, session, _picker(session), scripts=scripts)
    assert page.evaluate("() => window.secondCopyBinds") == 0

    _input(page).click()
    _settle(page)

    assert _state(page) == OPEN
    assert _opens(page) == 1
    assert page.evaluate(
        "() => typeof window.firstNamespace === 'object'"
        " && window.pjx.rosterPicker === window.firstNamespace"
    )

    page.keyboard.press("Escape")
    _settle(page)

    assert _state(page) == CLOSED
    assert _opens(page) == 1
    assert page_errors == []


def test_a_picker_added_after_load_opens_without_rebinding(
    page: Page, session: RenderSession, page_errors: list[str]
):
    _serve(page, session, '<div id="host"></div>')

    page.evaluate(
        "html => { document.getElementById('host').innerHTML = html; }",
        _picker(session, "late"),
    )
    _input(page, "late").click()

    assert _state(page, "late") == OPEN
    assert _opens(page, "late") == 1
    assert page_errors == []


def test_a_disabled_picker_ignores_clicks_and_keys(
    page: Page, session: RenderSession, page_errors: list[str]
):
    items = [PJXRosterItem(value="ada", label="Ada")]
    _serve(page, session, _picker(session, "d", disabled=True, items=items))
    before = page.eval_on_selector("#d", "picker => picker.outerHTML")

    page.click("#d .pjx-roster-picker__chip-label")
    page.click("#d")
    page.keyboard.press("Escape")
    page.keyboard.press("ArrowDown")
    _settle(page)

    assert page.eval_on_selector("#d", "picker => picker.outerHTML") == before
    assert page.evaluate("() => window.opens") == {}
    assert page_errors == []


def test_a_disabled_input_stays_closed_on_focus(
    page: Page, session: RenderSession, page_errors: list[str]
):
    _serve(page, session, _picker(session))

    # A disabled box cannot take real focus, so the focusin is synthetic.
    page.evaluate(
        """() => {
            const input = document.querySelector('#p .pjx-roster-picker__input');
            input.disabled = true;
            input.dispatchEvent(new FocusEvent('focusin', { bubbles: true }));
        }"""
    )
    _settle(page)

    assert _state(page) == CLOSED
    assert _opens(page) == 0
    assert page_errors == []


def test_click_on_the_focused_box_reopens_after_escape(
    page: Page, session: RenderSession, page_errors: list[str]
):
    _serve(page, session, _picker(session))
    _input(page).click()
    page.keyboard.press("Escape")
    assert _state(page) == CLOSED
    assert _input_has_focus(page)

    _input(page).click()

    assert _state(page) == OPEN
    assert _opens(page) == 2
    assert page_errors == []


def test_escape_closes_an_open_list_and_stops_there(
    page: Page, session: RenderSession, page_errors: list[str]
):
    _serve(page, session, _picker(session))
    _input(page).click()
    page.wait_for_selector(PICKS, timeout=5000)

    page.keyboard.press("Escape")

    assert _state(page) == CLOSED
    assert page.locator(PICKS).count() == 3
    assert _input_has_focus(page)
    assert page.evaluate("() => window.escapesAtWindow") == []
    assert page.evaluate("() => window.lastEscape.defaultPrevented") is True
    assert page_errors == []


def test_escape_on_a_closed_list_passes_through(
    page: Page, session: RenderSession, page_errors: list[str]
):
    _serve(page, session, _picker(session))
    _input(page).click()
    page.keyboard.press("Escape")

    page.keyboard.press("Escape")

    assert page.evaluate("() => window.escapesAtWindow") == [False]
    assert page.evaluate("() => window.lastEscape.defaultPrevented") is False
    assert _state(page) == CLOSED
    assert page_errors == []


def test_escape_from_inside_the_list_returns_focus_without_reopening(
    page: Page, session: RenderSession, page_errors: list[str]
):
    _serve(page, session, _picker(session))
    _input(page).click()
    page.wait_for_selector(PICKS, timeout=5000)
    page.locator(PICKS).first.focus()
    assert _state(page) == OPEN

    page.keyboard.press("Escape")

    assert _state(page) == CLOSED
    assert _input_has_focus(page)
    _settle(page)
    assert _state(page) == CLOSED
    assert _opens(page) == 1
    assert page_errors == []


def test_arrow_down_focuses_the_first_result(
    page: Page, session: RenderSession, page_errors: list[str]
):
    requests = _serve(page, session, _picker(session))
    _input(page).click()
    page.wait_for_selector(PICKS, timeout=5000)

    page.keyboard.press("ArrowDown")

    assert _focused_row(page) == "v0"
    assert _arrow_down_prevented(page) is True
    # Past the 300 ms debounce, so a reopen's search would have been sent.
    page.wait_for_timeout(500)
    assert _state(page) == OPEN
    assert _opens(page) == 1
    assert len(requests) == 1
    assert page_errors == []


def test_arrow_down_skips_a_hidden_first_row(
    page: Page, session: RenderSession, page_errors: list[str]
):
    items = [PJXRosterItem(value="v0", label="Person 0")]
    _serve(page, session, _picker(session, items=items))
    _input(page).click()
    _wait_rows_hidden(page, ["v0"])

    page.keyboard.press("ArrowDown")

    assert _focused_row(page) == "v1"
    assert _arrow_down_prevented(page) is True
    assert _state(page) == OPEN
    assert page_errors == []


def test_arrow_down_skips_a_row_picked_this_session(
    page: Page, session: RenderSession, page_errors: list[str]
):
    _serve(page, session, _picker(session))
    _input(page).click()
    page.wait_for_selector(PICKS, timeout=5000)
    # With the empty search recorded, the reopen below keeps these rows
    # instead of fetching new ones, so the hiding comes from the pick alone.
    _wait_last_query_empty(page)
    page.click('#p-results [data-pjx-roster-pick][data-value="v0"]')
    assert _state(page) == CLOSED

    _input(page).click()
    _wait_rows_hidden(page, ["v0"])
    assert _state(page) == OPEN
    page.keyboard.press("ArrowDown")

    assert _focused_row(page) == "v1"
    assert _state(page) == OPEN
    assert page_errors == []


def test_arrow_down_focuses_its_own_pickers_first_result(
    page: Page, session: RenderSession, page_errors: list[str]
):
    # Side by side, so neither open list covers the other picker's box.
    body = (
        '<div style="display: flex; gap: 40px">'
        f'<div style="flex: 1">{_picker(session, "a")}</div>'
        f'<div style="flex: 1">{_picker(session, "b")}</div>'
        "</div>"
    )
    _serve(page, session, body)
    _input(page, "a").click()
    page.wait_for_selector("#a-results [data-pjx-roster-pick]", timeout=5000)
    _input(page, "b").click()
    page.wait_for_selector("#b-results [data-pjx-roster-pick]", timeout=5000)

    page.keyboard.press("ArrowDown")

    assert _focused_row(page, "b") == "v0"
    assert _focused_row(page, "a") is None
    assert _state(page, "a") == OPEN
    assert _state(page, "b") == OPEN
    assert page_errors == []


def test_arrow_down_with_every_row_hidden_stays_in_the_input(
    page: Page, session: RenderSession, page_errors: list[str]
):
    items = [
        PJXRosterItem(value=f"v{index}", label=f"Person {index}") for index in range(3)
    ]
    _serve(page, session, _picker(session, items=items))
    _input(page).click()
    _wait_rows_hidden(page, ["v0", "v1", "v2"])

    page.keyboard.press("ArrowDown")

    assert _input_has_focus(page)
    assert _arrow_down_prevented(page) is False
    _settle(page)
    assert _state(page) == OPEN
    assert page_errors == []


def test_arrow_down_before_the_rows_arrive_stays_in_the_input(
    page: Page, session: RenderSession, page_errors: list[str]
):
    _serve(page, session, _picker(session))
    _input(page).click()
    page.wait_for_selector(PICKS, timeout=5000)

    # An open list whose search has not answered yet has an empty mount.
    # Emptying it and pressing in one script turn stands for that without
    # racing the search debounce.
    prevented = page.evaluate(
        """() => {
            document.getElementById('p-results').replaceChildren();
            const event = new KeyboardEvent('keydown', {
                key: 'ArrowDown', bubbles: true, cancelable: true,
            });
            document.querySelector('#p .pjx-roster-picker__input').dispatchEvent(event);
            return event.defaultPrevented;
        }"""
    )

    assert prevented is False
    assert _input_has_focus(page)
    assert _state(page) == OPEN
    assert page_errors == []


def test_arrow_down_on_a_closed_list_does_nothing(
    page: Page, session: RenderSession, page_errors: list[str]
):
    requests = _serve(page, session, _picker(session))
    _input(page).click()
    page.wait_for_selector(PICKS, timeout=5000)
    page.keyboard.press("Escape")
    assert _state(page) == CLOSED

    page.keyboard.press("ArrowDown")

    assert _input_has_focus(page)
    assert _arrow_down_prevented(page) is False
    # Past the 300 ms debounce, so a search from the press would have been sent.
    page.wait_for_timeout(500)
    assert _state(page) == CLOSED
    assert _opens(page) == 1
    assert len(requests) == 1
    assert page_errors == []


def test_arrow_down_on_a_result_stays_put(
    page: Page, session: RenderSession, page_errors: list[str]
):
    _serve(page, session, _picker(session))
    _input(page).click()
    page.wait_for_selector(PICKS, timeout=5000)
    page.keyboard.press("ArrowDown")
    assert _focused_row(page) == "v0"

    page.keyboard.press("ArrowDown")

    assert _focused_row(page) == "v0"
    assert _arrow_down_prevented(page) is False
    _settle(page)
    assert _state(page) == OPEN
    assert page_errors == []


def test_escape_after_arrow_down_returns_focus_without_reopening(
    page: Page, session: RenderSession, page_errors: list[str]
):
    _serve(page, session, _picker(session))
    _input(page).click()
    page.wait_for_selector(PICKS, timeout=5000)
    page.keyboard.press("ArrowDown")
    assert _focused_row(page) == "v0"

    page.keyboard.press("Escape")

    assert _state(page) == CLOSED
    assert _input_has_focus(page)
    _settle(page)
    assert _state(page) == CLOSED
    assert _opens(page) == 1
    assert page_errors == []


def test_pickers_open_and_close_independently(
    page: Page, session: RenderSession, page_errors: list[str]
):
    # Side by side, so neither open list covers the other picker's box.
    body = (
        '<div style="display: flex; gap: 40px">'
        f'<div style="flex: 1">{_picker(session, "a")}</div>'
        f'<div style="flex: 1">{_picker(session, "b")}</div>'
        "</div>"
    )
    _serve(page, session, body)

    _input(page, "a").click()
    assert _state(page, "a") == OPEN
    assert _state(page, "b") == CLOSED
    assert _opens(page, "b") == 0

    _input(page, "b").click()
    assert _state(page, "a") == OPEN
    assert _state(page, "b") == OPEN

    _input(page, "a").click()
    page.keyboard.press("Escape")

    assert _state(page, "a") == CLOSED
    assert _state(page, "b") == OPEN
    assert _opens(page, "a") == 1
    assert page_errors == []


def test_typing_into_a_closed_list_opens_it(
    page: Page, session: RenderSession, page_errors: list[str]
):
    _serve(page, session, _picker(session))
    _input(page).click()
    page.keyboard.press("Escape")
    assert _state(page) == CLOSED

    page.keyboard.type("a")

    assert _state(page) == OPEN
    _settle(page)
    # The input's own hx-trigger searches for typed text; opening adds no ask.
    assert _opens(page) == 1
    assert page_errors == []


def test_typing_in_another_input_leaves_the_picker_alone(
    page: Page, session: RenderSession, page_errors: list[str]
):
    body = '<input id="other" type="text">' + _picker(session)
    _serve(page, session, body)

    page.click("#other")
    page.keyboard.type("hi")
    _settle(page)

    assert _state(page) == CLOSED
    assert page.evaluate("() => window.opens") == {}
    assert page_errors == []


def test_events_aimed_at_the_document_itself_are_ignored(
    page: Page, session: RenderSession, page_errors: list[str]
):
    _serve(page, session, _picker(session))

    page.evaluate(
        """() => {
            document.dispatchEvent(new FocusEvent('focusin', { bubbles: true }));
            document.dispatchEvent(new MouseEvent('click', { bubbles: true }));
            document.dispatchEvent(new InputEvent('input', { bubbles: true }));
            document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true }));
            document.dispatchEvent(new KeyboardEvent('keydown', { key: 'ArrowDown', bubbles: true }));
        }"""
    )
    _settle(page)

    assert _state(page) == CLOSED
    assert page.evaluate("() => window.opens") == {}
    assert page_errors == []
