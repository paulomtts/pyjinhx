"""PJXRosterPicker's required validity and form submission, in real chromium with the vendored htmx.

Every page loads the committed pjx_roster_picker.js, with the picker inside
a form that has a submit button. A submit recorder installed after load
cancels each submit and logs its FormData entries, so a blocked submit
leaves the log empty. The candidates stub answers every search with three
people, v0 to v2. A negative is proven by letting a beat pass and checking
nothing changed.
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
HTMX_TAG = f"<script>{read_vendored_htmx()}</script>"
ASSET_TAG = f"<script>{ASSET}</script>"
OPEN = ("true", False)
CLOSED = ("false", True)

RECORD_SUBMITS = """() => {
    window.submits = [];
    document.addEventListener('submit', (event) => {
        event.preventDefault();
        window.submits.push(Array.from(new FormData(event.target).entries()));
    });
}"""

RECORD_VALID_AT_CHANGE = """() => {
    window.validAtChange = [];
    document.addEventListener('pjx:roster-picker:change', (event) => {
        window.validAtChange.push(event.target.closest('form').checkValidity());
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


def _form(body: str) -> str:
    return f'<form id="f">{body}<button type="submit" id="go">Save</button></form>'


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


def _wait_last_query(page: Page, value: str, picker_id: str = "p") -> None:
    page.wait_for_function(
        "([id, value]) => document.querySelector(`#${id} .pjx-roster-picker__input`)"
        ".getAttribute('data-last-query') === value",
        arg=[picker_id, value],
        timeout=5000,
    )


def _open(page: Page, picker_id: str = "p") -> None:
    """Click the box and wait until the first search's rows are in."""
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


def _has_focus(locator: Locator) -> bool:
    return locator.evaluate("el => el === document.activeElement")


def _record_submits(page: Page) -> None:
    page.evaluate(RECORD_SUBMITS)


def _submits(page: Page) -> list[list[list[str]]]:
    """One list of [name, value] FormData entries per submit that got through."""
    return page.evaluate("() => window.submits")


def _submit(page: Page) -> None:
    page.locator("#go").click()


def _valid(page: Page) -> bool:
    """The form's checkValidity(), which also fires invalid on each failing control."""
    return page.evaluate("() => document.getElementById('f').checkValidity()")


def _validity(page: Page, picker_id: str = "p") -> str:
    return page.evaluate(
        "id => document.querySelector(`#${id} > .pjx-roster-picker__validity`).value",
        picker_id,
    )


def _cue(page: Page, picker_id: str = "p") -> tuple[str | None, bool]:
    """The search input's aria-invalid and whether the picker has the invalid class."""
    attr, marked = page.evaluate(
        """id => [
            document.querySelector(`#${id} .pjx-roster-picker__input`).getAttribute('aria-invalid'),
            document.getElementById(id).classList.contains('pjx-roster-picker--invalid'),
        ]""",
        picker_id,
    )
    return attr, marked


def test_picks_write_the_chipped_values_into_the_validity_input(
    page: Page, session: RenderSession, page_errors: list[str]
):
    _serve(page, session, _form(_picker(session, required=True)))
    _open(page)

    _pick(page, "v0").click()
    # A pick closes the list; the box already has focus, so a click reopens it.
    _input(page).click()
    _pick(page, "v1").click()

    assert _validity(page) == "v0,v1"
    assert _valid(page) is True
    assert page_errors == []


def test_a_single_item_swap_leaves_only_the_new_value(
    page: Page, session: RenderSession, page_errors: list[str]
):
    picker = _picker(session, required=True, max_items=1, items=[_item("v0")])
    _serve(page, session, _form(picker))
    _open(page)

    _pick(page, "v1").click()

    assert _validity(page) == "v1"
    assert page_errors == []


def test_removing_the_last_chip_empties_the_validity_input(
    page: Page, session: RenderSession, page_errors: list[str]
):
    _serve(page, session, _form(_picker(session, required=True, items=[_item("a")])))

    _remove(page, "a").click()

    assert _validity(page) == ""
    # Before _valid, whose own invalid event is allowed to set the cue.
    assert _cue(page) == (None, False)
    assert _valid(page) is False
    assert page_errors == []


def test_the_validity_value_is_current_inside_the_change_event(
    page: Page, session: RenderSession, page_errors: list[str]
):
    _serve(page, session, _form(_picker(session, required=True)))
    _open(page)
    page.evaluate(RECORD_VALID_AT_CHANGE)

    _pick(page, "v0").click()

    assert page.evaluate("() => window.validAtChange") == [True]
    assert page_errors == []


def test_a_picker_rendered_with_items_starts_valid_and_posts_them(
    page: Page, session: RenderSession, page_errors: list[str]
):
    picker = _picker(session, required=True, items=[_item("a"), _item("b")])
    _serve(page, session, _form(picker))
    _record_submits(page)

    assert _valid(page) is True
    _submit(page)

    assert _submits(page) == [[["members", "a"], ["members", "b"]]]
    assert _cue(page) == (None, False)
    assert page_errors == []


def test_a_disabled_picker_still_posts_its_hidden_inputs(
    page: Page, session: RenderSession, page_errors: list[str]
):
    picker = _picker(
        session, required=True, disabled=True, items=[_item("a"), _item("b")]
    )
    _serve(page, session, _form(picker))
    _record_submits(page)

    _submit(page)

    assert _submits(page) == [[["members", "a"], ["members", "b"]]]
    assert page_errors == []


def test_an_empty_disabled_required_picker_never_blocks_submit(
    page: Page, session: RenderSession, page_errors: list[str]
):
    _serve(page, session, _form(_picker(session, required=True, disabled=True)))
    _record_submits(page)

    _submit(page)

    assert _submits(page) == [[]]
    assert page_errors == []


def test_search_text_never_posts(
    page: Page, session: RenderSession, page_errors: list[str]
):
    _serve(page, session, _form(_picker(session, required=True, items=[_item("a")])))
    _record_submits(page)
    _input(page).click()
    page.keyboard.type("Pe")
    _wait_last_query(page, "Pe")

    # The open list may cover the button, so submit the way a script would.
    page.evaluate("() => document.getElementById('f').requestSubmit()")

    assert _submits(page) == [[["members", "a"]]]
    assert page_errors == []


def test_a_non_required_picker_has_no_validity_input_and_submits(
    page: Page, session: RenderSession, page_errors: list[str]
):
    _serve(page, session, _form(_picker(session)))
    _record_submits(page)
    _open(page)
    _pick(page, "v0").click()
    _remove(page, "v0").click()

    _submit(page)

    assert page.locator("#p > .pjx-roster-picker__validity").count() == 0
    assert _submits(page) == [[]]
    assert _cue(page) == (None, False)
    assert page_errors == []


def test_an_empty_required_picker_blocks_submit_and_focuses_the_box(
    page: Page, session: RenderSession, page_errors: list[str]
):
    requests = _serve(page, session, _form(_picker(session, required=True)))
    _record_submits(page)

    _submit(page)
    # Past the 300 ms debounce, so a reopen's search would have been sent.
    page.wait_for_timeout(500)

    assert _submits(page) == []
    assert _has_focus(_input(page))
    assert _cue(page) == ("true", True)
    assert _state(page) == CLOSED
    assert requests == []
    assert page_errors == []


def test_a_second_submit_leaves_the_same_cue(
    page: Page, session: RenderSession, page_errors: list[str]
):
    requests = _serve(page, session, _form(_picker(session, required=True)))
    _record_submits(page)

    _submit(page)
    _submit(page)
    page.wait_for_timeout(500)

    assert _submits(page) == []
    assert _has_focus(_input(page))
    assert _cue(page) == ("true", True)
    assert (
        page.evaluate("() => document.getElementById('p').className")
        == "pjx-roster-picker pjx-roster-picker--invalid"
    )
    assert _state(page) == CLOSED
    assert requests == []
    assert page_errors == []


def test_check_validity_cues_every_empty_required_picker(
    page: Page, session: RenderSession, page_errors: list[str]
):
    body = _picker(session, "p", required=True) + _picker(session, "q", required=True)
    _serve(page, session, _form(body))

    assert _valid(page) is False

    assert _cue(page, "p") == ("true", True)
    assert _cue(page, "q") == ("true", True)
    assert _state(page, "p") == CLOSED
    assert _state(page, "q") == CLOSED
    assert page_errors == []


def test_an_unrelated_invalid_control_leaves_the_picker_alone(
    page: Page, session: RenderSession, page_errors: list[str]
):
    picker = _picker(session, required=True, items=[_item("a")])
    _serve(page, session, _form(f'<input id="title" required>{picker}'))
    _record_submits(page)

    _submit(page)
    _settle(page)

    assert _submits(page) == []
    assert _cue(page) == (None, False)
    assert _has_focus(page.locator("#title"))
    assert page_errors == []
