"""PJXSelect — keyboard navigation of the option panel.

The classes above pin the invariants as source-shape guards (see the module
docstring history); the classes below are the promised exhaustive key-by-mode
matrix, driven through real DOM/Playwright the way test_pjx_select_collision.py
drives positioning: arrow nav, type-ahead, Enter, and Escape, in both single-
and multi-select mode.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

import pytest

if TYPE_CHECKING:
    from playwright.sync_api import Page

UI = Path(__file__).resolve().parents[4] / "pyjinhx" / "builtins" / "ui"
CONTROLLER = UI / "pjx_select" / "pjx_select.js"


def source() -> str:
    return CONTROLLER.read_text()


def body_of(name: str) -> str:
    """Text of the named top-level function, from its `function` line to its close."""
    src = source()
    start = src.index(f"function {name}(")
    return src[start : src.index("\n    }", start)]


class TestWiring:
    def test_a_keydown_listener_is_wired(self):
        assert "addEventListener('keydown'" in source()

    def test_the_listener_ignores_targets_outside_a_select_root(self):
        # Chip-input convention: bail before touching the root at all.
        handler = source()[source().index("addEventListener('keydown'") :]
        assert "rootOf(" in handler
        assert "if (!root" in handler

    def test_disabled_roots_are_inert(self):
        handler = source()[source().index("addEventListener('keydown'") :]
        assert "data-disabled" in handler


class TestVisibleOptions:
    def test_the_option_list_skips_hidden_options(self):
        assert "[data-pjx-select-option]:not([hidden])" in body_of("visibleOptions")

    def test_the_option_list_skips_disabled_options(self):
        assert ":not([disabled])" in body_of("visibleOptions")


class TestArrowNavigation:
    def test_arrows_home_and_end_are_all_handled(self):
        handler = source()[source().index("addEventListener('keydown'") :]
        for key in ("'ArrowDown'", "'ArrowUp'", "'Home'", "'End'"):
            assert key in handler

    def test_movement_wraps_at_both_ends(self):
        body = body_of("moveFocus")
        assert "% options.length" in body
        assert "+ options.length" in body

    def test_movement_is_a_no_op_on_an_empty_list(self):
        assert "if (!options.length) return" in body_of("moveFocus")

    def test_movement_preventsdefault_and_focuses(self):
        handler = source()[source().index("addEventListener('keydown'") :]
        assert "e.preventDefault()" in handler
        assert ".focus()" in handler


class TestOpeningFromTheTrigger:
    def test_the_trigger_opens_on_arrow_enter_and_space(self):
        body = body_of("onTriggerKey")
        assert "open(root)" in body
        assert "'Enter'" in body
        assert "' '" in body

    def test_arrowup_enters_at_the_last_option(self):
        assert "options.length - 1" in body_of("onTriggerKey")


class TestTypeAhead:
    def test_the_buffer_resets_after_an_idle_window(self):
        body = body_of("pushTypeAhead")
        assert "500" in body
        assert "setTimeout" in body

    def test_matching_is_case_insensitive_and_prefix_based(self):
        body = body_of("typeAheadTarget")
        assert "toLowerCase()" in body
        assert "indexOf(" in body and "=== 0" in body

    def test_type_ahead_wraps_past_the_focused_option(self):
        assert "% options.length" in body_of("typeAheadTarget")

    def test_the_filter_input_keeps_ownership_of_its_own_typing(self):
        # Type-ahead only fires when focus is on an option button, never while
        # the search box has it — otherwise every keystroke would do both.
        handler = source()[source().index("addEventListener('keydown'") :]
        assert "data-pjx-select-filter" in handler

    def test_only_single_printing_characters_start_a_buffer(self):
        handler = source()[source().index("addEventListener('keydown'") :]
        assert "e.key.length === 1" in handler
        assert "e.ctrlKey" in handler and "e.metaKey" in handler


class TestCommitAndDismiss:
    def test_enter_branches_on_mode(self):
        body = body_of("commitOption")
        assert "isMultiple(root)" in body
        assert "toggle(root, option)" in body
        assert "select(root, option.getAttribute('data-value'))" in body

    def test_single_select_closes_and_returns_focus_to_the_trigger(self):
        # commitOption delegates to dismiss() for the close+refocus half;
        # dismiss's own body is pinned separately below.
        assert "dismiss(root)" in body_of("commitOption")

    def test_escape_closes_and_returns_focus_to_the_trigger(self):
        body = body_of("dismiss")
        assert "close(root)" in body
        assert "trigger.focus()" in body

    def test_escape_is_scoped_to_select_roots(self):
        # pjx_popover.js also closes on Escape; scoping keeps the two handlers
        # from fighting over unrelated components.
        handler = source()[source().index("addEventListener('keydown'") :]
        assert "'Escape'" in handler


class TestUntouchedNeighbours:
    def test_the_position_primitive_is_still_verbatim(self):
        primitive = (UI / "pjx_popover" / "pjx_popover_position.js").read_text()
        assert primitive in source()

    def test_no_new_markup_hooks_were_invented(self):
        template = (UI / "pjx_select" / "pjx_select.pjx").read_text()
        assert "tabindex" not in template.replace('tabindex="-1"', "")


# --- real-DOM coverage -------------------------------------------------
#
# Mirrors the shape pjx_select.pjx renders (see test_pjx_select_collision.py's
# STYLE/SINGLE/MULTIPLE for the same pattern): a synthetic page loads the
# controller unmodified and drives it with real keyboard events.

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


@pytest.fixture(autouse=True)
def _require_chromium(request: pytest.FixtureRequest) -> None:
    if "page" not in set(request.fixturenames):
        return
    pytest.importorskip("playwright")
    browser_type: Any = request.getfixturevalue("browser_type")
    if not Path(browser_type.executable_path).exists():
        pytest.skip(
            "chromium is not installed (run: uv run playwright install chromium)"
        )


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
        _load(page, SINGLE)
        page.keyboard.press("ArrowDown")
        assert page.evaluate("document.getElementById('panel').hidden") is False
        assert _active_value(page) == "a"

    def test_arrowup_on_the_trigger_opens_at_the_last_option(self, page: Page):
        _load(page, SINGLE)
        page.keyboard.press("ArrowUp")
        assert _active_value(page) == "c"

    def test_arrowdown_moves_focus_forward_and_wraps(self, page: Page):
        _load(page, SINGLE)
        page.keyboard.press("ArrowDown")  # opens on "a"
        page.keyboard.press("ArrowDown")  # -> b
        page.keyboard.press("ArrowDown")  # -> c
        page.keyboard.press("ArrowDown")  # wraps -> a
        assert _active_value(page) == "a"

    def test_home_and_end_jump_to_the_edges(self, page: Page):
        _load(page, SINGLE)
        page.keyboard.press("ArrowDown")  # opens on "a"
        page.keyboard.press("End")
        assert _active_value(page) == "c"
        page.keyboard.press("Home")
        assert _active_value(page) == "a"


class TestTypeAheadRealDom:
    def test_typing_a_letter_jumps_to_the_matching_option(self, page: Page):
        _load(page, SINGLE)
        page.keyboard.press("ArrowDown")  # opens on "a" (Apple)
        page.keyboard.press("c")
        assert _active_value(page) == "c"

    def test_type_ahead_is_case_insensitive(self, page: Page):
        _load(page, SINGLE)
        page.keyboard.press("ArrowDown")
        page.keyboard.press("B")
        assert _active_value(page) == "b"

    def test_type_ahead_with_no_match_is_a_no_op_and_does_not_throw(self, page: Page):
        errors: list[str] = []
        page.on("pageerror", lambda exc: errors.append(str(exc)))
        _load(page, SINGLE)
        page.keyboard.press("ArrowDown")  # opens on "a"
        page.keyboard.press("z")
        assert _active_value(page) == "a"  # focus unchanged
        assert errors == []


class TestCommitRealDom:
    def test_enter_selects_the_focused_option_and_closes_in_single_mode(
        self, page: Page
    ):
        _load(page, SINGLE)
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
