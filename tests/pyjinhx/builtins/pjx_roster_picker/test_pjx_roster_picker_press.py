"""PJXRosterPicker closing when focus leaves, held until the press that moved it ends.

Real chromium with the vendored htmx and the committed pjx_roster_picker.js,
so these tests exercise the asset that ships. Touch scenarios run in their own
touch-enabled context. A negative is proven by letting a beat pass and
checking nothing changed.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

from pyjinhx.builtins.ui.pjx_roster_picker import PJXRosterItem, PJXRosterPicker
from pyjinhx.builtins.ui.pjx_roster_results import PJXRosterResults
from pyjinhx.client import read_vendored_htmx
from pyjinhx.rendering import render

if TYPE_CHECKING:
    from playwright.sync_api import Browser, Locator, Page, Route

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
# Before the picker, so the open list hanging below it never covers it.
OUTSIDE = '<button id="outside" type="button">Outside</button>'
OPEN = ("true", False)
CLOSED = ("false", True)

# Stands for a browser whose buttons take no focus on press: the row's
# mousedown moves focus nowhere, out of the picker's search box.
BLUR_ON_ROW_PRESS = """() => {
    document.addEventListener('mousedown', (event) => {
        if (!event.target.closest('[data-pjx-roster-pick]')) return;
        event.preventDefault();
        document.activeElement.blur();
    }, true);
}"""


def _picker(session: RenderSession, picker_id: str = "p", **kwargs: Any) -> str:
    return render(
        PJXRosterPicker(
            id=picker_id, name="members", candidates_url=CANDIDATES_URL, **kwargs
        ),
        session,
    )


def _serve(page: Page, session: RenderSession, body: str, css: str = "") -> list[str]:
    """Load body with the CSS and scripts, answer candidates with three rows, return the request log."""
    items = [
        PJXRosterItem(value=f"v{index}", label=f"Person {index}") for index in range(3)
    ]
    rows = render(PJXRosterResults(picker_id="p", items=items), session)
    html = (
        f"<html><head><style>{CSS}{css}</style></head>"
        f"<body>{body}{HTMX_TAG}{ASSET_TAG}</body></html>"
    )
    requests: list[str] = []

    def candidates(route: Route) -> None:
        requests.append(route.request.url)
        route.fulfill(body=rows, content_type="text/html")

    page.route(URL, lambda route: route.fulfill(body=html, content_type="text/html"))
    page.route(CANDIDATES, candidates)
    page.goto(URL)
    page.wait_for_function("() => window.htmx")
    return requests


def _open(page: Page, picker_id: str = "p") -> None:
    """Click the box and wait for its rows, so a press lands on a full list."""
    _input(page, picker_id).click()
    page.wait_for_selector(f"#{picker_id}-results [data-pjx-roster-pick]", timeout=5000)


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


def _input_has_focus(page: Page, picker_id: str = "p") -> bool:
    return page.evaluate(
        "id => document.activeElement === document.querySelector(`#${id} .pjx-roster-picker__input`)",
        picker_id,
    )


def _active_id(page: Page) -> str:
    return page.evaluate("() => document.activeElement.id")


def _chip_values(page: Page, picker_id: str = "p") -> list[str]:
    return page.evaluate(
        """id => Array.from(
            document.querySelectorAll(
                `#${id} .pjx-roster-picker__chips > [data-pjx-roster-chip] > .pjx-roster-picker__chip-input`
            ),
            (input) => input.value,
        )""",
        picker_id,
    )


def _wait_last_query_empty(page: Page, picker_id: str = "p") -> None:
    """Wait until the box has recorded a successful search for empty text."""
    page.wait_for_function(
        """id => document.querySelector(`#${id} .pjx-roster-picker__input`)
            .getAttribute('data-last-query') === ''""",
        arg=picker_id,
        timeout=5000,
    )


def _wait_closed(page: Page, timeout: float, picker_id: str = "p") -> None:
    page.wait_for_function(
        """id => document.querySelector(`#${id} .pjx-roster-picker__input`)
            .getAttribute('aria-expanded') === 'false'""",
        arg=picker_id,
        timeout=timeout,
    )


def test_tab_out_of_the_input_closes_the_list(
    page: Page, session: RenderSession, page_errors: list[str]
):
    body = '<button id="before" type="button">Before</button>' + _picker(session)
    _serve(page, session, body)
    _open(page)

    page.keyboard.press("Tab")
    assert _state(page) == OPEN
    page.keyboard.press("Shift+Tab")
    assert _input_has_focus(page)
    page.keyboard.press("Shift+Tab")

    assert _active_id(page) == "before"
    assert _state(page) == CLOSED
    assert page_errors == []


def test_tab_out_of_the_last_row_closes_the_list(
    page: Page, session: RenderSession, page_errors: list[str]
):
    body = _picker(session) + '<button id="after" type="button">After</button>'
    _serve(page, session, body)
    _open(page)
    page.keyboard.press("ArrowDown")

    # v0 to v1, v1 to v2, then past the last row.
    for _ in range(3):
        page.keyboard.press("Tab")

    assert _active_id(page) == "after"
    assert _state(page) == CLOSED
    assert page_errors == []


def test_a_click_outside_closes_the_list(
    page: Page, session: RenderSession, page_errors: list[str]
):
    body = OUTSIDE + _picker(session)
    _serve(page, session, body)
    _open(page)

    page.click("#outside")
    _settle(page)

    assert _state(page) == CLOSED
    assert _active_id(page) == "outside"
    assert page_errors == []


def test_a_click_on_plain_page_text_closes_the_list(
    page: Page, session: RenderSession, page_errors: list[str]
):
    body = '<p id="text">Plain text</p>' + _picker(session)
    _serve(page, session, body)
    _open(page)

    page.click("#text")
    _settle(page)

    assert _state(page) == CLOSED
    assert not _input_has_focus(page)
    assert page_errors == []


def test_a_press_into_another_picker_moves_the_open_list(
    page: Page, session: RenderSession, page_errors: list[str]
):
    # Side by side, so the open list does not cover the other picker's box.
    body = (
        '<div style="display: flex; gap: 40px">'
        f'<div style="flex: 1">{_picker(session, "p")}</div>'
        f'<div style="flex: 1">{_picker(session, "q")}</div>'
        "</div>"
    )
    _serve(page, session, body)
    _open(page, "p")

    _input(page, "q").click()
    _settle(page)

    assert _state(page, "p") == CLOSED
    assert _state(page, "q") == OPEN
    assert _input_has_focus(page, "q")
    assert page_errors == []


def test_typing_with_no_press_live_keeps_the_list_open(
    page: Page, session: RenderSession, page_errors: list[str]
):
    _serve(page, session, _picker(session))
    _open(page)

    page.keyboard.type("a")
    _settle(page)

    assert _state(page) == OPEN
    assert _input_has_focus(page)
    assert page_errors == []


def test_focus_leaving_with_no_press_closes_at_once_and_returning_keeps_the_rows(
    page: Page, session: RenderSession, page_errors: list[str]
):
    requests = _serve(page, session, _picker(session))
    _open(page)
    _wait_last_query_empty(page)

    # A window switch takes focus with no press: nothing defers the close.
    page.evaluate("() => document.querySelector('#p .pjx-roster-picker__input').blur()")
    assert _state(page) == CLOSED

    _input(page).focus()
    # Past the 300 ms debounce, so a reopen's search would have been sent.
    page.wait_for_timeout(500)

    assert _state(page) == OPEN
    assert len(requests) == 1
    assert page_errors == []


def test_a_click_on_a_result_lands_before_the_list_closes(
    page: Page, session: RenderSession, page_errors: list[str]
):
    _serve(page, session, _picker(session))
    _open(page)
    page.evaluate(BLUR_ON_ROW_PRESS)

    page.click('#p-results [data-pjx-roster-pick][data-value="v1"]')
    _settle(page)

    assert _chip_values(page) == ["v1"]
    assert _state(page) == CLOSED
    assert page_errors == []


def test_a_click_on_the_lists_padding_keeps_it_open(
    page: Page, session: RenderSession, page_errors: list[str]
):
    requests = _serve(
        page, session, _picker(session), css="#p-results { padding: 40px; }"
    )
    _open(page)
    box = page.locator("#p-results").bounding_box()
    assert box is not None

    page.mouse.click(box["x"] + box["width"] / 2, box["y"] + 8)
    # Past the 300 ms debounce, so a reopen's search would have been sent.
    _settle(page)
    page.wait_for_timeout(300)

    assert _state(page) == OPEN
    assert _input_has_focus(page)
    assert len(requests) == 1
    assert page_errors == []


def test_a_tap_on_the_lists_padding_keeps_it_open(
    browser: Browser, session: RenderSession
):
    context = browser.new_context(has_touch=True)
    try:
        page = context.new_page()
        page_errors: list[str] = []
        page.on("pageerror", lambda error: page_errors.append(str(error)))
        requests = _serve(
            page, session, _picker(session), css="#p-results { padding: 40px; }"
        )
        _open(page)
        box = page.locator("#p-results").bounding_box()
        assert box is not None

        page.touchscreen.tap(box["x"] + box["width"] / 2, box["y"] + 8)
        _settle(page)
        page.wait_for_timeout(300)

        assert _state(page) == OPEN
        assert _input_has_focus(page)
        assert len(requests) == 1
        assert page_errors == []
    finally:
        context.close()


def test_a_touch_tap_on_a_result_picks_it(browser: Browser, session: RenderSession):
    context = browser.new_context(has_touch=True)
    try:
        page = context.new_page()
        page_errors: list[str] = []
        page.on("pageerror", lambda error: page_errors.append(str(error)))
        _serve(page, session, _picker(session))
        _open(page)
        page.evaluate(BLUR_ON_ROW_PRESS)
        box = page.locator(
            '#p-results [data-pjx-roster-pick][data-value="v0"]'
        ).bounding_box()
        assert box is not None

        page.touchscreen.tap(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
        _settle(page)

        assert _chip_values(page) == ["v0"]
        assert _state(page) == CLOSED
        assert _input_has_focus(page)
        assert page_errors == []
    finally:
        context.close()


def test_a_press_whose_click_never_comes_ends_on_the_timer(
    page: Page, session: RenderSession, page_errors: list[str]
):
    body = OUTSIDE + _picker(session)
    _serve(page, session, body)
    _open(page)

    page.evaluate(
        """() => {
            const outside = document.getElementById('outside');
            outside.dispatchEvent(new PointerEvent('pointerdown', { bubbles: true }));
            outside.dispatchEvent(new PointerEvent('pointerup', { bubbles: true }));
            document.querySelector('#p .pjx-roster-picker__input').blur();
        }"""
    )
    # Read at once, well inside the 400 ms the timer waits.
    assert _state(page) == OPEN

    page.wait_for_timeout(600)

    assert _state(page) == CLOSED
    assert page_errors == []


def test_a_remove_click_on_an_open_list_closes_it_and_keeps_the_box_focused(
    page: Page, session: RenderSession, page_errors: list[str]
):
    # Low on the page, so the list opens upward and leaves the chips uncovered.
    body = '<div style="height: 600px"></div>' + _picker(
        session, items=[PJXRosterItem(value="a", label="A")]
    )
    requests = _serve(page, session, body)
    _open(page)

    page.click("#p [data-pjx-roster-remove]")
    # Past the 300 ms debounce, so a reopen's search would have been sent.
    _settle(page)
    page.wait_for_timeout(300)

    assert _chip_values(page) == []
    assert _state(page) == CLOSED
    assert _input_has_focus(page)
    assert len(requests) == 1
    assert page_errors == []
