"""PJXSelect — keyboard navigation of the option panel.

There is no JS harness in this repo (see test_pjx_select_filter.py), so the
browser behavior is pinned by source-shape guards over pjx_select.js: each
test names one invariant that is cheap to break and expensive to notice.
The exhaustive key-by-mode matrix belongs to the PJXSelect test/docs subtask.
"""

from pathlib import Path

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
