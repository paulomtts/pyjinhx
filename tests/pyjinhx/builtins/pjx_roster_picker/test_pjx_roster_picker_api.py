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
from urllib.parse import parse_qs, urlsplit

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


@pytest.mark.parametrize("name", ["values", "open", "close"])
@pytest.mark.parametrize("root_js", NON_PICKER_ROOTS)
def test_api_throws_for_a_non_picker_root(
    page: Page, session: RenderSession, page_errors: list[str], name: str, root_js: str
):
    _serve(page, session, _picker(session))

    assert _thrown(page, name, root_js) == [True, MESSAGE.format(name=name)]
    assert page_errors == []


@pytest.mark.parametrize("name", ["values", "open", "close"])
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


def test_open_opens_the_list_and_searches(
    page: Page, session: RenderSession, page_errors: list[str]
):
    requests = _serve(page, session, _picker(session))
    page.evaluate(
        "() => { document.querySelector('#p .pjx-roster-picker__input').value = 'Per'; }"
    )

    with page.expect_request(CANDIDATES, timeout=5000) as request:
        assert _api(page, "open") is True
        assert _state(page) == OPEN
    _settle(page)

    query = parse_qs(urlsplit(request.value.url).query, keep_blank_values=True)
    assert query["q"] == ["Per"]
    assert len(requests) == 1
    assert _opens(page) == 1
    assert page_errors == []


def test_open_leaves_focus_where_it_was(
    page: Page, session: RenderSession, page_errors: list[str]
):
    body = '<button id="trigger" type="button">Add</button>' + _picker(session)
    _serve(page, session, body)
    page.focus("#trigger")

    assert _api(page, "open") is True
    _settle(page)

    assert page.evaluate("() => document.activeElement.id") == "trigger"
    assert _state(page) == OPEN
    assert page_errors == []


def test_open_on_an_open_list_returns_true_and_asks_nothing_more(
    page: Page, session: RenderSession, page_errors: list[str]
):
    requests = _serve(page, session, _picker(session))

    assert _api(page, "open") is True
    assert _api(page, "open") is True
    _settle(page)

    assert _state(page) == OPEN
    assert _opens(page) == 1
    assert len(requests) == 1
    assert page_errors == []


def test_open_after_close_does_not_search_again(
    page: Page, session: RenderSession, page_errors: list[str]
):
    requests = _serve(page, session, _picker(session))

    _api(page, "open")
    _wait_rows(page)
    _wait_last_query(page, "")
    assert _api(page, "close") is True
    assert _api(page, "open") is True
    _settle(page)

    assert _state(page) == OPEN
    assert len(requests) == 1
    assert page.locator("#p-results [data-pjx-roster-pick]").count() == 3
    assert page_errors == []


def test_close_closes_the_list_and_keeps_its_rows(
    page: Page, session: RenderSession, page_errors: list[str]
):
    _serve(page, session, _picker(session))

    _api(page, "open")
    _wait_rows(page)
    assert _api(page, "close") is True

    assert _state(page) == CLOSED
    assert page.locator("#p-results [data-pjx-roster-pick]").count() == 3
    assert page_errors == []


def test_close_on_a_closed_list_returns_true(
    page: Page, session: RenderSession, page_errors: list[str]
):
    requests = _serve(page, session, _picker(session))
    before = page.eval_on_selector("#p", "picker => picker.outerHTML")

    assert _api(page, "close") is True
    _settle(page)

    assert page.eval_on_selector("#p", "picker => picker.outerHTML") == before
    assert _state(page) == CLOSED
    assert requests == []
    assert page_errors == []


def test_open_and_close_move_a_portal_list_to_body_and_home(
    page: Page, session: RenderSession, page_errors: list[str]
):
    _serve(page, session, _picker(session, portal=True))
    where = """() => {
        const mount = document.getElementById('p-results');
        const search = document.querySelector('#p .pjx-roster-picker__search');
        return {
            onBody: mount.parentElement === document.body,
            home: mount.parentElement === search && search.lastElementChild === mount,
        };
    }"""

    assert _api(page, "open") is True
    assert page.evaluate(where) == {"onBody": True, "home": False}
    assert _api(page, "close") is True
    assert page.evaluate(where) == {"onBody": False, "home": True}
    assert _state(page) == CLOSED
    assert page_errors == []


def test_open_and_close_return_false_for_a_disabled_picker(
    page: Page, session: RenderSession, page_errors: list[str]
):
    requests = _serve(
        page, session, _picker(session, disabled=True, items=[_item("v0")])
    )
    before = page.eval_on_selector("#p", "picker => picker.outerHTML")

    assert _api(page, "open") is False
    assert _api(page, "close") is False
    _settle(page)

    assert page.eval_on_selector("#p", "picker => picker.outerHTML") == before
    assert _opens(page) == 0
    assert requests == []
    assert page_errors == []


def test_open_and_close_return_false_without_an_input(
    page: Page, session: RenderSession, page_errors: list[str]
):
    requests = _serve(page, session, _picker(session))
    page.evaluate(
        "() => document.querySelector('#p .pjx-roster-picker__input').remove()"
    )

    assert _api(page, "open") is False
    assert _api(page, "close") is False
    _settle(page)

    assert page.evaluate("() => document.getElementById('p-results').hidden") is True
    assert requests == []
    assert page_errors == []


def test_open_and_close_return_false_at_the_cap(
    page: Page, session: RenderSession, page_errors: list[str]
):
    items = [_item("v0"), _item("v1")]
    requests = _serve(page, session, _picker(session, max_items=2, items=items))

    assert _api(page, "open") is False
    assert _api(page, "close") is False
    _settle(page)

    assert _state(page) == CLOSED
    assert _opens(page) == 0
    assert requests == []
    assert page_errors == []


def test_close_before_the_search_answers_keeps_the_list_closed(
    page: Page, session: RenderSession, page_errors: list[str]
):
    _serve(page, session, _picker(session))

    # The debounced search was already asked for, so it still goes out; its
    # rows must land in the hidden list without opening it.
    with page.expect_request(CANDIDATES, timeout=5000):
        assert _api(page, "open") is True
        assert _api(page, "close") is True
    _wait_rows(page)
    _settle(page)

    assert _state(page) == CLOSED
    assert page_errors == []


def test_api_works_when_the_script_is_loaded_twice(
    page: Page, session: RenderSession, page_errors: list[str]
):
    scripts = HTMX_TAG + ASSET_TAG + ASSET_TAG
    requests = _serve(page, session, _picker(session, items=[_item("v0")]), scripts)

    assert _api(page, "values") == ["v0"]
    assert _api(page, "open") is True
    _settle(page)
    assert _state(page) == OPEN
    assert _opens(page) == 1
    assert len(requests) == 1
    assert _api(page, "close") is True
    assert _state(page) == CLOSED
    assert page_errors == []


@pytest.mark.parametrize("name", ["values", "open", "close"])
def test_api_throws_for_a_portaled_list_on_body(
    page: Page, session: RenderSession, page_errors: list[str], name: str
):
    _serve(page, session, _picker(session, portal=True))
    _api(page, "open")

    thrown = _thrown(page, name, "document.getElementById('p-results')")

    assert thrown == [True, MESSAGE.format(name=name)]
    # The list on body is still open and still on body: nothing ran.
    assert _state(page) == OPEN
    assert page.evaluate(
        "() => document.getElementById('p-results').parentElement === document.body"
    )
    assert page_errors == []
