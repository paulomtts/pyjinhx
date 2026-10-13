"""window.pjx.rosterPicker's values, open and close, in real chromium with the vendored htmx.

Every page loads the committed pjx_roster_picker.js, so these tests exercise
the asset that ships. An init script counts roster-picker-open and logs each
pjx:roster-picker:change. A thrown error is caught in the page, so it never
becomes a page error. A negative is proven by letting a beat pass and
checking nothing changed.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

import pytest

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
MESSAGE = (
    "pjx.rosterPicker.{name}: expected a roster picker root ([data-pjx-roster-picker])"
)

# Each a JS expression evaluated in the page.
NON_PICKER_ROOTS = ["null", "undefined", "'p'", "document", "document.body"]
INSIDE_ROOTS = [
    "document.querySelector('#p .pjx-roster-picker__input')",
    "document.querySelector('#p [data-pjx-roster-chip]')",
    "document.getElementById('p-results')",
]

# roster-picker-open does not bubble, so only a capturing listener on document
# hears it.
RECORDER = """
window.opens = 0;
window.changes = [];
document.addEventListener('roster-picker-open', () => { window.opens += 1; }, true);
document.addEventListener('pjx:roster-picker:change', (event) => {
    window.changes.push(event.detail.values);
});
"""


def _picker(session: RenderSession, picker_id: str = "p", **kwargs: Any) -> str:
    return render(
        PJXRosterPicker(
            id=picker_id, name="members", candidates_url=CANDIDATES_URL, **kwargs
        ),
        session,
    )


def _item(value: str) -> PJXRosterItem:
    return PJXRosterItem(value=value, label=f"Person {value}")


def _serve(
    page: Page,
    session: RenderSession,
    body: str,
    scripts: str = HTMX_TAG + ASSET_TAG,
) -> list[str]:
    """Load body with the CSS and scripts, answer candidates with rows v0-v2, return the request log."""
    items = [_item(f"v{index}") for index in range(3)]
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
    """Let two animation frames and a beat past the 300 ms debounce pass."""
    page.evaluate(
        "() => new Promise((done) => requestAnimationFrame(() => requestAnimationFrame(done)))"
    )
    # There is no event for "did not fire", so proving a negative needs a beat.
    page.wait_for_timeout(500)


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


def _api(page: Page, name: str, picker_id: str = "p") -> Any:
    """Call pjx.rosterPicker.<name> on the picker root and return its result."""
    return page.evaluate(
        f"id => window.pjx.rosterPicker.{name}(document.getElementById(id))",
        picker_id,
    )


def _opens(page: Page) -> int:
    return page.evaluate("() => window.opens")


def _changes(page: Page) -> list[list[str]]:
    return page.evaluate("() => window.changes")


def _wait_rows(page: Page, picker_id: str = "p") -> None:
    """Wait until the first search's rows are in. Attached: a chipped row is hidden."""
    page.wait_for_selector(
        f"#{picker_id}-results [data-pjx-roster-pick]", state="attached", timeout=5000
    )


def _wait_last_query(page: Page, value: str, picker_id: str = "p") -> None:
    """Wait until the box has recorded a successful search for value."""
    page.wait_for_function(
        "([id, value]) => document.querySelector(`#${id} .pjx-roster-picker__input`)"
        ".getAttribute('data-last-query') === value",
        arg=[picker_id, value],
        timeout=5000,
    )


def _thrown(page: Page, name: str, root_js: str) -> list[Any] | None:
    """[is an Error, message] for what pjx.rosterPicker.<name>(root) threw, or None."""
    return page.evaluate(
        f"""() => {{
            try {{
                window.pjx.rosterPicker.{name}({root_js});
            }} catch (error) {{
                return [error instanceof Error, error.message];
            }}
            return null;
        }}"""
    )


def _pick_by_click(page: Page, value: str, picker_id: str = "p") -> None:
    """Open the list with a click on the box and click value's row."""
    _input(page, picker_id).click()
    page.locator(
        f'#{picker_id}-results [data-pjx-roster-pick][data-value="{value}"]'
    ).click()


def test_values_is_empty_for_an_empty_picker(
    page: Page, session: RenderSession, page_errors: list[str]
):
    _serve(page, session, _picker(session))

    assert _api(page, "values") == []
    assert page_errors == []


def test_values_lists_preselected_chips_in_rendered_order(
    page: Page, session: RenderSession, page_errors: list[str]
):
    _serve(page, session, _picker(session, items=[_item("v2"), _item("v0")]))

    assert _api(page, "values") == ["v2", "v0"]
    assert page_errors == []


def test_values_follows_pick_order(
    page: Page, session: RenderSession, page_errors: list[str]
):
    _serve(page, session, _picker(session))

    _pick_by_click(page, "v2")
    _pick_by_click(page, "v0")

    assert _api(page, "values") == ["v2", "v0"]
    assert _changes(page)[-1] == ["v2", "v0"]
    assert page_errors == []


def test_values_drops_a_removed_chip_and_keeps_order(
    page: Page, session: RenderSession, page_errors: list[str]
):
    items = [_item("v0"), _item("v1"), _item("v2")]
    _serve(page, session, _picker(session, items=items))

    page.locator(
        "#p .pjx-roster-picker__chips > [data-pjx-roster-chip]"
        ':has(> input[value="v1"]) [data-pjx-roster-remove]'
    ).click()

    assert _api(page, "values") == ["v0", "v2"]
    assert page_errors == []


def test_values_holds_only_the_latest_pick_with_max_items_one(
    page: Page, session: RenderSession, page_errors: list[str]
):
    _serve(page, session, _picker(session, max_items=1))

    _pick_by_click(page, "v0")
    _pick_by_click(page, "v1")

    assert _api(page, "values") == ["v1"]
    assert page_errors == []


def test_values_reports_a_disabled_pickers_chips(
    page: Page, session: RenderSession, page_errors: list[str]
):
    items = [_item("v1"), _item("v0")]
    _serve(page, session, _picker(session, disabled=True, items=items))

    assert _api(page, "values") == ["v1", "v0"]
    assert page_errors == []


def test_values_returns_a_copy(
    page: Page, session: RenderSession, page_errors: list[str]
):
    _serve(page, session, _picker(session, items=[_item("v0")]))

    again = page.evaluate(
        """() => {
            const root = document.getElementById('p');
            window.pjx.rosterPicker.values(root).push('intruder');
            return window.pjx.rosterPicker.values(root);
        }"""
    )

    assert again == ["v0"]
    assert page_errors == []


def test_values_skips_a_slot_control_sharing_the_chip_input_class(
    page: Page, session: RenderSession, page_errors: list[str]
):
    _serve(page, session, _picker(session, items=[_item("v0")]))
    page.evaluate(
        """() => {
            const nested = document.createElement('input');
            nested.className = 'pjx-roster-picker__chip-input';
            nested.value = 'nested';
            document
                .querySelector('#p [data-pjx-roster-chip] .pjx-roster-picker__chip-row')
                .append(nested);
        }"""
    )

    assert _api(page, "values") == ["v0"]
    assert page_errors == []


def test_values_skips_template_chips_in_result_rows(
    page: Page, session: RenderSession, page_errors: list[str]
):
    _serve(page, session, _picker(session, items=[_item("v0")]))

    _input(page).click()
    _wait_rows(page)

    assert _api(page, "values") == ["v0"]
    assert page_errors == []


def test_values_does_not_open_focus_or_announce(
    page: Page, session: RenderSession, page_errors: list[str]
):
    requests = _serve(page, session, _picker(session, items=[_item("v0")]))

    _api(page, "values")
    _settle(page)

    assert _state(page) == CLOSED
    assert page.evaluate("() => document.activeElement === document.body")
    assert _opens(page) == 0
    assert _changes(page) == []
    assert requests == []
    assert page_errors == []


@pytest.mark.parametrize("name", ["values"])
@pytest.mark.parametrize("root_js", NON_PICKER_ROOTS)
def test_api_throws_for_a_non_picker_root(
    page: Page, session: RenderSession, page_errors: list[str], name: str, root_js: str
):
    _serve(page, session, _picker(session))

    assert _thrown(page, name, root_js) == [True, MESSAGE.format(name=name)]
    assert page_errors == []


@pytest.mark.parametrize("name", ["values"])
@pytest.mark.parametrize("root_js", INSIDE_ROOTS)
def test_api_throws_for_an_element_inside_a_picker(
    page: Page, session: RenderSession, page_errors: list[str], name: str, root_js: str
):
    requests = _serve(page, session, _picker(session, items=[_item("v0")]))

    assert _thrown(page, name, root_js) == [True, MESSAGE.format(name=name)]
    _settle(page)
    # Nothing changed before the throw: the list is still closed and unasked.
    assert _state(page) == CLOSED
    assert requests == []
    assert page_errors == []
