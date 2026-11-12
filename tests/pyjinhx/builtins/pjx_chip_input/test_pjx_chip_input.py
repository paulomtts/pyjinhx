"""PJXChipInput — v0.x field/markup parity on the v2 engine.

Port of tests/unit/test_chip_input.py. v0.x's golden snapshot
(tests/unit/golden/chip_input.html) does not carry over: v2 builtins assert on
rendered substrings, like every sibling port. The template composes no child
component tags — only div/span/input/button — so there is no child-tag render
coverage here and no registry fixture, unlike PJXButton's region-loader leg.
"""

import pytest
from pydantic import ValidationError

from pyjinhx.builtins.ui.pjx_chip_input import PJXChipInput
from pyjinhx.client import read_pjx_theme_css


class TestFields:
    def test_defaults(self):
        chips = PJXChipInput(id="c", name="tags")
        assert chips.values == []
        assert chips.placeholder == "Add…"
        assert chips.remove_label == "Remove"
        assert chips.disabled is False
        assert chips.class_name == ""
        assert chips.extra_attrs == {}

    def test_name_is_required(self):
        with pytest.raises(ValidationError):
            PJXChipInput(id="c")  # type: ignore[call-arg]

    def test_undeclared_kwarg_raises(self):
        with pytest.raises(ValidationError):
            PJXChipInput(id="c", name="tags", bogus="x")  # type: ignore[call-arg]

    def test_inline_attr_kwargs_no_longer_pass_through(self):
        """v0.x accepted ``PJXChipInput(id="c", **{"data-test": "yes"})``.

        v2 core is strict (extra="forbid"), so a bare inline attr kwarg is now a
        ValidationError. The behavior it replaces is not dropped: pass-through
        moved to the declared ``extra_attrs`` mapping, covered by
        TestRender.test_extra_attrs_surface_on_the_root.
        """
        with pytest.raises(ValidationError):
            PJXChipInput(id="c", name="tags", **{"data-test": "yes"})  # type: ignore[arg-type]


from pyjinhx.rendering import render
from pyjinhx.session import RenderSession


@pytest.fixture
def session():
    """Loader rooted at "/" so absolute descriptor template paths resolve.

    ClassDescriptor.template_path is absolute and render() feeds it straight to
    the session's FileSystemLoader; Jinja only resolves an absolute path when
    the loader root is "/". Same fixture shape as the sibling builtin tests.
    """
    return RenderSession()


def _html(session, **kwargs) -> str:
    base = {"id": "c", "name": "tags"}
    base.update(kwargs)
    return render(PJXChipInput(**base), session)  # type: ignore[arg-type]


class TestRender:
    def test_single_root_div(self, session):
        html = _html(session, values=["a"]).strip()
        assert html.count("data-pjx-chip-input") == 1
        assert html.startswith('<div id="c"')
        assert html.endswith("</div>")

    def test_one_chip_and_one_hidden_input_per_value_in_order(self, session):
        html = _html(session, values=["c", "a", "b"])
        assert html.count("data-pjx-chip>") == 3
        assert html.count('<input type="hidden"') == 3
        positions = [html.find(f'value="{v}"') for v in ("c", "a", "b")]
        assert positions == sorted(positions)

    def test_hidden_input_name_matches_the_name_field(self, session):
        html = _html(session, name="keywords", values=["x", "y"])
        assert html.count('<input type="hidden" name="keywords"') == 2

    def test_remove_buttons_carry_the_remove_label(self, session):
        html = _html(session, values=["x", "y"], remove_label="Remove chip")
        assert html.count('aria-label="Remove chip"') == 2
        assert html.count("data-pjx-chip-remove") == 2

    def test_disabled_drops_the_text_field_and_remove_buttons(self, session):
        html = _html(session, values=["x"], disabled=True)
        assert 'type="text"' not in html
        assert "data-pjx-chip-remove" not in html

    def test_disabled_keeps_the_hidden_inputs(self, session):
        html = _html(session, values=["x", "y"], disabled=True)
        assert html.count('<input type="hidden" name="tags"') == 2

    def test_root_data_attrs(self, session):
        head = _html(session, name="skills", remove_label="Delete")
        head = head[: head.index(">")]
        assert 'data-name="skills"' in head
        assert 'data-remove-label="Delete"' in head

    def test_data_disabled_only_when_disabled(self, session):
        assert "data-disabled" not in _html(session)[: _html(session).index(">")]
        head = _html(session, disabled=True)
        assert "data-disabled" in head[: head.index(">")]

    def test_class_name_is_appended_without_clobbering_base_classes(self, session):
        assert 'class="pjx-chip-input my-chips"' in _html(
            session, class_name="my-chips"
        )

    def test_empty_class_name_adds_nothing(self, session):
        assert 'class="pjx-chip-input"' in _html(session)

    def test_extra_attrs_surface_on_the_root(self, session):
        html = _html(session, extra_attrs={"data-test": "yes"})
        assert 'data-test="yes"' in html[: html.index(">")]

    def test_placeholder_renders_on_the_text_field(self, session):
        html = _html(session, placeholder="Type here…")
        assert 'placeholder="Type here…"' in html
        assert 'type="text"' in html

    def test_chip_value_is_escaped(self, session):
        html = _html(session, values=["<script>x</script>"])
        assert "&lt;script&gt;x&lt;/script&gt;" in html
        assert "<script>" not in html


class TestAssets:
    def test_stylesheet_is_frozen_on_the_descriptor(self):
        css = PJXChipInput.__pjx_descriptor__.css_paths
        assert len(css) == 1
        assert css[0].name == "pjx_chip_input.css"
        assert css[0].is_file()

    def test_script_is_frozen_on_the_descriptor(self):
        js = PJXChipInput.__pjx_descriptor__.js_paths
        assert len(js) == 1
        assert js[0].name == "pjx_chip_input.js"
        assert js[0].is_file()


CHIP_CSS = PJXChipInput.__pjx_descriptor__.css_paths[0].read_text(encoding="utf-8")

CHIP_MARKUP = (
    '<div id="root" class="pjx-chip-input">'
    '<span id="chip" class="pjx-chip-input__chip">'
    '<span class="pjx-chip-input__label">tag</span>'
    '<button class="pjx-chip-input__remove" type="button">x</button></span>'
    '<input id="field" class="pjx-chip-input__field">'
    "</div>"
)


def _chip_style(page, element_id: str, prop: str) -> str:
    return page.evaluate(
        f"getComputedStyle(document.getElementById('{element_id}'))"
        f".getPropertyValue('{prop}')"
    )


def test_chip_input_defaults_use_light_fallbacks(page):
    page.set_content(
        f"<html><head><style>{CHIP_CSS}</style></head><body>{CHIP_MARKUP}</body></html>"
    )
    assert _chip_style(page, "root", "border-top-left-radius") == "8px"
    # 0.375rem stays off the spacing scale; 8px is space-2.
    assert _chip_style(page, "root", "padding-top") == "6px"
    assert _chip_style(page, "root", "padding-left") == "8px"
    assert _chip_style(page, "root", "row-gap") == "6px"
    assert _chip_style(page, "root", "background-color") == "rgb(255, 255, 255)"
    assert _chip_style(page, "chip", "background-color") == "rgb(250, 250, 250)"
    assert _chip_style(page, "chip", "color") == "rgb(24, 24, 27)"
    assert _chip_style(page, "chip", "border-top-left-radius") == "9999px"
    assert _chip_style(page, "chip", "padding-top") == "2px"
    assert _chip_style(page, "chip", "padding-left") == "8px"
    assert _chip_style(page, "chip", "column-gap") == "4px"
    assert _chip_style(page, "field", "color") == "rgb(24, 24, 27)"


def test_chip_input_follows_theme_in_dark_mode(page):
    page.emulate_media(color_scheme="light")
    page.set_content(
        # Dark on <html>: component tokens are declared on :root, so their
        # var() resolves there and a dark subtree alone would not flip them.
        f'<html data-pjx-theme="dark"><head><style>{read_pjx_theme_css()}</style>'
        f"<style>{CHIP_CSS}</style></head>"
        f"<body>{CHIP_MARKUP}</body></html>"
    )
    assert _chip_style(page, "root", "background-color") == "rgb(24, 24, 27)"
    assert _chip_style(page, "chip", "background-color") == "rgb(9, 9, 11)"
    assert _chip_style(page, "chip", "color") == "rgb(244, 244, 245)"
    assert _chip_style(page, "chip", "border-top-color") == "rgb(63, 63, 70)"
    assert _chip_style(page, "field", "color") == "rgb(244, 244, 245)"
