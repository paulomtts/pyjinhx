"""PJXSelect multi-select mode (#866) — checkboxes, chip trigger summary, native multi.

Single-select behaviour lives in test_pjx_select.py. Search (#867), keyboard nav
(#868) and the exhaustive cross-cutting suite (#869) are separate subtasks;
nothing here anticipates their markup.
"""

import pytest
from pydantic import ValidationError

from pyjinhx.builtins.ui.pjx_select import PJXSelect, SelectOption
from pyjinhx.rendering import render
from pyjinhx.session import RenderSession

OPTIONS = [
    SelectOption(value="a", label="Apple"),
    SelectOption(value="b", label="Banana"),
    SelectOption(value="c", label="Cherry"),
]


class TestMultipleFields:
    def test_multiple_defaults_to_false(self):
        assert PJXSelect(id="s", name="fruit", options=OPTIONS).multiple is False

    def test_multi_mode_accepts_a_list_value(self):
        sel = PJXSelect(
            id="s", name="fruit", options=OPTIONS, multiple=True, value=["a", "b"]
        )
        assert sel.value == ["a", "b"]

    def test_multi_mode_accepts_none(self):
        sel = PJXSelect(id="s", name="fruit", options=OPTIONS, multiple=True)
        assert sel.value is None

    def test_multiple_value_type_mismatch_raises(self):
        with pytest.raises(ValidationError):
            PJXSelect(id="s", name="fruit", options=OPTIONS, multiple=True, value="a")
        with pytest.raises(ValidationError):
            PJXSelect(id="s", name="fruit", options=OPTIONS, value=["a"])


@pytest.fixture
def session():
    """Loader rooted at "/" so absolute descriptor template paths resolve.

    Same fixture shape as the sibling builtin tests.
    """
    return RenderSession()


def _html(session, **kwargs) -> str:
    base = {"id": "s", "name": "fruit", "options": OPTIONS}
    base.update(kwargs)
    return render(PJXSelect(**base), session)  # type: ignore[arg-type]


class TestMultipleMarkup:
    def test_multiple_renders_checkboxes(self, session):
        html = _html(session, multiple=True)
        assert html.count('type="checkbox"') == 3
        assert 'type="checkbox"' not in _html(session)

    def test_multiple_native_select_has_multiple_attr(self, session):
        assert '<select name="fruit" multiple hidden>' in _html(session, multiple=True)
        assert "multiple" not in _html(session)

    def test_multiple_root_carries_the_multiple_hook(self, session):
        head = _html(session, multiple=True)
        head = head[: head.index(">")]
        assert "data-multiple" in head
        assert 'data-placeholder="Select…"' in head

    def test_multiple_checked_state_follows_the_value_list(self, session):
        html = _html(session, multiple=True, value=["a", "c"])
        assert html.count('checkbox" checked') == 2
        assert html.count('<option value="a" selected>') == 1
        assert html.count('<option value="c" selected>') == 1
        assert '<option value="b">' in html
        assert html.count('aria-selected="true"') == 2

    def test_multiple_unknown_value_dropped(self, session):
        html = _html(session, multiple=True, value=["a", "zzz"])
        assert html.count('aria-selected="true"') == 1
        assert html.count('checkbox" checked') == 1
        assert "zzz" not in html

    def test_multiple_disabled_checkboxes_present_but_inert(self, session):
        html = _html(session, multiple=True, disabled=True)
        assert html.count('type="checkbox"') == 3
        assert html.count('type="checkbox" disabled') == 3
        assert "data-disabled" in html[: html.index(">")]


def _trigger(html: str) -> str:
    start = html.index("data-pjx-select-trigger")
    return html[start : html.index("</button>", start)]


class TestChipSummary:
    def test_multiple_two_plus_selected_renders_chips(self, session):
        trigger = _trigger(_html(session, multiple=True, value=["a", "c"]))
        assert trigger.count('class="pjx-chip-input__chip"') == 2
        assert trigger.count('class="pjx-chip-input__label"') == 2
        assert 'class="pjx-select__chips"' in trigger
        assert "Apple" in trigger
        assert "Cherry" in trigger
        assert "Banana" not in trigger

    def test_trigger_chips_carry_no_remove_button(self, session):
        trigger = _trigger(_html(session, multiple=True, value=["a", "c"]))
        assert "pjx-chip-input__remove" not in trigger
        assert "&#x2715;" not in trigger

    def test_multiple_zero_or_one_selected_renders_plain_label(self, session):
        none_selected = _trigger(_html(session, multiple=True))
        assert "pjx-chip-input__chip" not in none_selected
        assert "Select…" in none_selected

        one_selected = _trigger(_html(session, multiple=True, value=["b"]))
        assert "pjx-chip-input__chip" not in one_selected
        assert "Banana" in one_selected

    def test_multiple_chip_label_escaped(self, session):
        options = [
            SelectOption(value="a", label="<b>Ampersand & co</b>"),
            SelectOption(value="b", label="Banana"),
        ]
        trigger = _trigger(
            _html(session, options=options, multiple=True, value=["a", "b"])
        )
        assert "&lt;b&gt;Ampersand &amp; co&lt;/b&gt;" in trigger
        assert "<b>Ampersand" not in trigger

    def test_label_span_is_still_the_single_trigger_hook(self, session):
        html = _html(session, multiple=True, value=["a", "c"])
        assert html.count('class="pjx-select__label"') == 1


class TestStylesheet:
    """The chip summary must borrow PJXChipInput's tokens, not fork them."""

    def test_chip_layout_rules_exist_and_reuse_chip_input_tokens(self):
        from pathlib import Path

        css = (
            Path(__file__).resolve().parents[4]
            / "pyjinhx"
            / "builtins"
            / "ui"
            / "pjx_select"
            / "pjx_select.css"
        ).read_text()
        assert ".pjx-select__chips" in css
        assert ".pjx-select__checkbox" in css
        assert "var(--pjx-chip-input-gap)" in css
        assert "--pjx-select-chip-" not in css


class TestController:
    """The controller is asserted structurally — there is no JS runtime in this suite.

    These checks pin the contract the markup and the script share (hook names,
    escaping discipline) so a rename on either side fails loudly.
    """

    @staticmethod
    def _js() -> str:
        from pathlib import Path

        return (
            Path(__file__).resolve().parents[4]
            / "pyjinhx"
            / "builtins"
            / "ui"
            / "pjx_select"
            / "pjx_select.js"
        ).read_text()

    def test_controller_branches_on_the_multiple_hook(self):
        js = self._js()
        assert "data-multiple" in js
        assert "data-placeholder" in js

    def test_controller_builds_chips_without_innerhtml(self):
        js = self._js()
        assert "pjx-chip-input__chip" in js
        assert "pjx-chip-input__label" in js
        assert "innerHTML =" not in js

    def test_controller_keeps_no_search_or_keyboard_handling(self):
        js = self._js()
        assert "keydown" not in js
        assert 'type="search"' not in js
