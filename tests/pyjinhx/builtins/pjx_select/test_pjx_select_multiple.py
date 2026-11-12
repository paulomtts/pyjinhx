"""PJXSelect multi-select mode (#866) — checkboxes, chip trigger summary, native multi.

Single-select behaviour lives in test_pjx_select.py. Search (#867), keyboard nav
(#868) and the exhaustive cross-cutting suite (#869) are separate subtasks;
nothing here anticipates their markup.
"""

import re
from pathlib import Path

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
    """The chip summary borrows PJXChipInput's tokens when available, but pyjinhx's
    asset walk resolves CSS per-class with no cross-component dependency: a page
    that renders PJXSelect(multiple=True) without ever rendering PJXChipInput only
    ships pjx_select.css. So pjx_select.css must carry its own fallback values for
    every PJXChipInput token it references, and the actual chip visuals (not just
    layout), rather than assuming pjx_chip_input.css is also on the page.
    """

    @staticmethod
    def _css() -> str:
        from pathlib import Path

        return (
            Path(__file__).resolve().parents[4]
            / "pyjinhx"
            / "builtins"
            / "ui"
            / "pjx_select"
            / "pjx_select.css"
        ).read_text()

    def test_chip_layout_rules_exist_and_reuse_chip_input_tokens(self):
        css = self._css()
        assert ".pjx-select__chips" in css
        assert ".pjx-select__checkbox" in css
        assert "var(--pjx-chip-input-gap" in css
        assert "--pjx-select-chip-" not in css

    def test_chip_tokens_have_standalone_fallbacks(self):
        """Every --pjx-chip-input-* var() reference needs a fallback value so
        chips still render (with the right colours, not just layout) when
        pjx_chip_input.css never ships on the page."""
        css = self._css()
        import re

        refs = re.findall(r"var\(--pjx-chip-input-[\w-]+([^)]*)\)", css)
        assert refs, "expected at least one --pjx-chip-input-* var() reference"
        assert all("," in ref for ref in refs), (
            "every --pjx-chip-input-* reference needs a fallback: "
            f"{[r for r in refs if ',' not in r]}"
        )

    def test_chip_visuals_are_embedded_not_just_layout(self):
        """The chip's own background/border/radius/font-size must be embedded
        in pjx_select.css, not left to pjx_chip_input.css to supply."""
        css = self._css()
        chip_rule_start = css.index(".pjx-select__chips .pjx-chip-input__chip")
        chip_rule = css[chip_rule_start : css.index("}", chip_rule_start)]
        assert "background" in chip_rule
        assert "border-radius" in chip_rule
        assert "font-size" in chip_rule

    @staticmethod
    def _chip_input_css() -> str:
        return (
            Path(__file__).resolve().parents[4]
            / "pyjinhx"
            / "builtins"
            / "ui"
            / "pjx_chip_input"
            / "pjx_chip_input.css"
        ).read_text()

    @staticmethod
    def _chip_input_fallbacks(css: str) -> list[tuple[str, str]]:
        """Return (name, squashed fallback) for each var(--pjx-chip-input-<name>, …).

        The fallback runs from the first top-level comma to the matching ")".
        """
        found = []
        for match in re.finditer(r"var\(\s*--pjx-chip-input-([\w-]+)\s*,", css):
            depth = 0
            end = len(css)
            for index in range(match.end(), len(css)):
                if css[index] == "(":
                    depth += 1
                elif css[index] == ")":
                    if depth == 0:
                        end = index
                        break
                    depth -= 1
            found.append((match.group(1), " ".join(css[match.end() : end].split())))
        return found

    @staticmethod
    def _rule_declarations(css: str, selector: str) -> dict[str, str]:
        """Return the squashed property: value pairs of the rule for selector."""
        start = css.index(selector + " {") + len(selector) + 2
        rule = css[start : css.index("}", start)]
        body = re.sub(r"/\*.*?\*/", "", rule, flags=re.DOTALL)
        return {
            name: " ".join(value.split())
            for name, value in re.findall(r"([\w-]+)\s*:\s*([^;]+);", body)
        }

    def test_select_chip_fallbacks_match_chip_input_defaults(self):
        """S1: pjx_select.css carries the exact defaults pjx_chip_input.css
        declares, so a page without PJXChipInput still gets the same chip."""
        declared = {
            name: " ".join(value.split())
            for name, value in re.findall(
                r"--pjx-chip-input-([\w-]+):\s*([^;]+);", self._chip_input_css()
            )
        }
        fallbacks = self._chip_input_fallbacks(self._css())
        assert len({name for name, _ in fallbacks}) >= 4
        drift = [
            f"--pjx-chip-input-{name}: select falls back to {fallback!r}, "
            f"chip input declares {declared.get(name)!r}"
            for name, fallback in fallbacks
            if declared.get(name) != fallback
        ]
        assert not drift, "; ".join(drift)

    def test_select_summary_chip_geometry_matches_chip_input(self):
        """The summary chip embeds the chip-input chip's geometry verbatim."""
        summary = self._rule_declarations(
            self._css(), ".pjx-select__chips .pjx-chip-input__chip"
        )
        chip = self._rule_declarations(self._chip_input_css(), ".pjx-chip-input__chip")
        for prop in ("gap", "padding", "font-size", "line-height"):
            assert summary[prop] == chip[prop], (
                f"{prop}: select {summary[prop]!r} vs chip input {chip[prop]!r}"
            )


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

    def test_controller_never_builds_the_search_markup(self):
        js = self._js()
        assert 'type="search"' not in js
