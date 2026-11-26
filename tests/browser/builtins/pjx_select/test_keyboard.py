"""PJXSelect — keyboard navigation of the option panel.

The classes above pin the invariants as source-shape guards (see the module
docstring history); the classes below are the promised exhaustive key-by-mode
matrix, driven through real DOM/Playwright the way test_pjx_select_collision.py
drives positioning: arrow nav, type-ahead, Enter, and Escape, in both single-
and multi-select mode.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from playwright.sync_api import Page


UI = Path(__file__).resolve().parents[4] / "pyjinhx" / "builtins"


CONTROLLER = UI / "pjx_select" / "pjx_select.js"


STYLE = """
<style>
  .pjx-select { position: relative; display: inline-block; }
  .pjx-select__panel[hidden] { display: none !important; }
</style>
"""


SINGLE = """
<div id="root" class="pjx-select" data-pjx-select data-name="fruit">
  <select name="fruit" hidden>
    <option value="a">Apple</option>
    <option value="b">Banana</option>
    <option value="c">Cherry</option>
  </select>
  <button type="button" class="pjx-select__trigger" data-pjx-select-trigger
          aria-haspopup="listbox" aria-expanded="false">
    <span class="pjx-select__label">Select…</span>
  </button>
  <div id="panel" class="pjx-select__panel" data-pjx-select-panel hidden role="listbox">
    <input type="search" class="pjx-select__filter" data-pjx-select-filter placeholder="Search…">
    <button type="button" class="pjx-select__option" data-pjx-select-option
            data-value="a" aria-selected="false" role="option">Apple</button>
    <button type="button" class="pjx-select__option" data-pjx-select-option
            data-value="b" aria-selected="false" role="option">Banana</button>
    <button type="button" class="pjx-select__option" data-pjx-select-option
            data-value="c" aria-selected="false" role="option">Cherry</button>
  </div>
</div>
"""


# Same options as SINGLE but with no filter box, so opening still lands
# keyboard focus on the first/last *option* — the pre-autofocus behavior,
# still correct for panels short enough to skip the search input.
SINGLE_NO_FILTER = SINGLE.replace(
    '    <input type="search" class="pjx-select__filter" data-pjx-select-filter placeholder="Search…">\n',
    "",
)


MULTIPLE = """
<div id="root" class="pjx-select" data-pjx-select data-name="fruit" data-multiple
     data-placeholder="Select…">
  <select name="fruit" multiple hidden>
    <option value="a">Apple</option>
    <option value="b">Banana</option>
    <option value="c">Cherry</option>
  </select>
  <button type="button" class="pjx-select__trigger" data-pjx-select-trigger
          aria-haspopup="listbox" aria-expanded="false">
    <span class="pjx-select__label">Select…</span>
  </button>
  <div id="panel" class="pjx-select__panel" data-pjx-select-panel hidden role="listbox">
    <button type="button" class="pjx-select__option" data-pjx-select-option
            data-value="a" aria-selected="false" role="option">
      <input type="checkbox" class="pjx-select__checkbox" tabindex="-1" aria-hidden="true">Apple</button>
    <button type="button" class="pjx-select__option" data-pjx-select-option
            data-value="b" aria-selected="false" role="option">
      <input type="checkbox" class="pjx-select__checkbox" tabindex="-1" aria-hidden="true">Banana</button>
    <button type="button" class="pjx-select__option" data-pjx-select-option
            data-value="c" aria-selected="false" role="option">
      <input type="checkbox" class="pjx-select__checkbox" tabindex="-1" aria-hidden="true">Cherry</button>
  </div>
</div>
"""


def _load(page: Page, markup: str) -> None:
    page.set_content(STYLE + markup)
    page.add_script_tag(content=CONTROLLER.read_text())
    page.focus("[data-pjx-select-trigger]")


def _active_value(page: Page) -> str | None:
    return page.evaluate("() => document.activeElement.getAttribute('data-value')")


class TestArrowNavigationRealDom:
    def test_arrowdown_on_the_trigger_opens_the_panel_and_focuses_the_first_option(
        self, page: Page
    ):
        _load(page, SINGLE_NO_FILTER)
        page.keyboard.press("ArrowDown")
        assert page.evaluate("document.getElementById('panel').hidden") is False
        assert _active_value(page) == "a"

    def test_arrowup_on_the_trigger_opens_at_the_last_option(self, page: Page):
        _load(page, SINGLE_NO_FILTER)
        page.keyboard.press("ArrowUp")
        assert _active_value(page) == "c"

    def test_arrowdown_moves_focus_forward_and_wraps(self, page: Page):
        _load(page, SINGLE_NO_FILTER)
        page.keyboard.press("ArrowDown")  # opens on "a"
        page.keyboard.press("ArrowDown")  # -> b
        page.keyboard.press("ArrowDown")  # -> c
        page.keyboard.press("ArrowDown")  # wraps -> a
        assert _active_value(page) == "a"

    def test_home_and_end_jump_to_the_edges(self, page: Page):
        _load(page, SINGLE_NO_FILTER)
        page.keyboard.press("ArrowDown")  # opens on "a"
        page.keyboard.press("End")
        assert _active_value(page) == "c"
        page.keyboard.press("Home")
        assert _active_value(page) == "a"


class TestTypeAheadRealDom:
    def test_typing_a_letter_jumps_to_the_matching_option(self, page: Page):
        _load(page, SINGLE_NO_FILTER)
        page.keyboard.press("ArrowDown")  # opens on "a" (Apple)
        page.keyboard.press("c")
        assert _active_value(page) == "c"

    def test_type_ahead_is_case_insensitive(self, page: Page):
        _load(page, SINGLE_NO_FILTER)
        page.keyboard.press("ArrowDown")
        page.keyboard.press("B")
        assert _active_value(page) == "b"

    def test_type_ahead_with_no_match_is_a_no_op_and_does_not_throw(self, page: Page):
        errors: list[str] = []
        page.on("pageerror", lambda exc: errors.append(str(exc)))
        _load(page, SINGLE_NO_FILTER)
        page.keyboard.press("ArrowDown")  # opens on "a"
        page.keyboard.press("z")
        assert _active_value(page) == "a"  # focus unchanged
        assert errors == []


class TestCommitRealDom:
    def test_enter_selects_the_focused_option_and_closes_in_single_mode(
        self, page: Page
    ):
        _load(page, SINGLE_NO_FILTER)
        page.keyboard.press("ArrowDown")  # opens on "a"
        page.keyboard.press("ArrowDown")  # -> b
        page.keyboard.press("Enter")
        assert page.evaluate("document.getElementById('panel').hidden") is True
        assert (
            page.evaluate(
                "document.querySelector('[data-value=\"b\"]').getAttribute('aria-selected')"
            )
            == "true"
        )
        assert page.evaluate(
            "document.activeElement.hasAttribute('data-pjx-select-trigger')"
        )

    def test_enter_toggles_the_focused_option_and_stays_open_in_multiple_mode(
        self, page: Page
    ):
        _load(page, MULTIPLE)
        page.keyboard.press("ArrowDown")  # opens on "a"
        page.keyboard.press("Enter")
        assert page.evaluate("document.getElementById('panel').hidden") is False
        assert (
            page.evaluate(
                "document.querySelector('[data-value=\"a\"]').getAttribute('aria-selected')"
            )
            == "true"
        )


class TestFilterAutofocusRealDom:
    def test_arrowdown_on_the_trigger_focuses_the_filter_when_present(self, page: Page):
        _load(page, SINGLE)
        page.keyboard.press("ArrowDown")
        assert page.evaluate("document.getElementById('panel').hidden") is False
        assert page.evaluate(
            "document.activeElement.hasAttribute('data-pjx-select-filter')"
        )

    def test_arrowup_on_the_trigger_also_focuses_the_filter(self, page: Page):
        _load(page, SINGLE)
        page.keyboard.press("ArrowUp")
        assert page.evaluate(
            "document.activeElement.hasAttribute('data-pjx-select-filter')"
        )

    def test_clicking_the_trigger_focuses_the_filter(self, page: Page):
        _load(page, SINGLE)
        page.click("[data-pjx-select-trigger]")
        assert page.evaluate(
            "document.activeElement.hasAttribute('data-pjx-select-filter')"
        )

    def test_arrowdown_from_the_filter_still_reaches_the_first_option(self, page: Page):
        # Filter takes the initial focus, but its own ArrowDown handling
        # (unchanged by this fix) still hands off into the option list.
        _load(page, SINGLE)
        page.keyboard.press("ArrowDown")  # focuses the filter
        page.keyboard.press("ArrowDown")  # -> first option
        assert _active_value(page) == "a"

    def test_no_filter_falls_back_to_focusing_the_first_option(self, page: Page):
        _load(page, SINGLE_NO_FILTER)
        page.keyboard.press("ArrowDown")
        assert _active_value(page) == "a"


class TestEscapeRealDom:
    def test_escape_closes_the_panel_and_returns_focus_to_the_trigger(self, page: Page):
        _load(page, SINGLE)
        page.keyboard.press("ArrowDown")
        page.keyboard.press("Escape")
        assert page.evaluate("document.getElementById('panel').hidden") is True
        assert page.evaluate(
            "document.activeElement.hasAttribute('data-pjx-select-trigger')"
        )

    def test_escape_while_the_filter_input_has_focus_still_closes_the_panel(
        self, page: Page
    ):
        _load(page, SINGLE)
        page.keyboard.press("ArrowDown")
        page.focus("[data-pjx-select-filter]")
        page.keyboard.press("Escape")
        assert page.evaluate("document.getElementById('panel').hidden") is True
