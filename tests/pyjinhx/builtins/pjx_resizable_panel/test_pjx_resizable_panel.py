"""PJXResizablePanel — v0.x field/markup parity on the v2 engine.

Ported from v0.x tests/unit/test_resizable_parts.py (panel half). Slot strings
are escaped here, matching measured pjx_carousel_slide behavior -- a
pre-existing gap, not fixed by #535.
"""

import math
import re

import pytest
from pydantic import ValidationError

from pyjinhx.builtins.ui.pjx_resizable_panel import PJXResizablePanel
from pyjinhx.rendering import render
from pyjinhx.session import RenderSession


@pytest.fixture
def session():
    # template_dir="/" so the descriptor's absolute template path resolves,
    # same fixture shape as the sibling builtin tests.
    return RenderSession(template_dir="/")


def _html(session, **kwargs) -> str:
    base = {"id": "p"}
    base.update(kwargs)
    return render(PJXResizablePanel(**base), session)  # type: ignore[arg-type]


def _style(html: str) -> str:
    match = re.search(r'style="([^"]*)"', html)
    assert match is not None
    return match.group(1)


class TestFields:
    def test_defaults(self):
        panel = PJXResizablePanel(id="p")
        assert panel.size is None
        assert panel.min == 0.0
        assert panel.max == 100.0
        assert panel.class_name == ""
        assert panel.content == ""

    def test_content_is_the_children_field(self):
        assert PJXResizablePanel._pjx_children_field == "content"

    def test_undeclared_kwarg_raises(self):
        with pytest.raises(ValidationError):
            PJXResizablePanel(id="p", bogus="x")  # type: ignore[call-arg]

    def test_accepts_plain_numbers_and_numeric_strings(self):
        assert PJXResizablePanel(id="p", min=25).min == 25
        assert PJXResizablePanel(id="p", min=25.5).min == 25.5
        assert PJXResizablePanel(id="p", min="25").min == "25"

    def test_accepts_px_strings_on_both_bounds(self):
        assert PJXResizablePanel(id="p", min="120px").min == "120px"
        assert PJXResizablePanel(id="p", max="400px").max == "400px"

    def test_accepts_content_on_min_only(self):
        assert PJXResizablePanel(id="p", min="content").min == "content"
        with pytest.raises(ValidationError):
            PJXResizablePanel(id="p", max="content")

    def test_rejects_bad_unit(self):
        with pytest.raises(ValidationError):
            PJXResizablePanel(id="p", min="120em")

    def test_rejects_negative_nonfinite_and_scientific(self):
        for bad in (-5, -5.0, math.inf, float("nan"), "1e3", "1.5e20"):
            with pytest.raises(ValidationError):
                PJXResizablePanel(id="p", min=bad)  # type: ignore[arg-type]

    def test_error_message_names_the_field_and_the_accepted_forms(self):
        with pytest.raises(ValidationError) as excinfo:
            PJXResizablePanel(id="p", max="content")
        message = str(excinfo.value)
        assert "PJXResizablePanel.max must be a percentage number" in message
        assert "an '<n>px' string" in message
        assert "(min only) 'content'" in message


class TestComputedCss:
    def test_percentage_bounds_emit_no_css(self):
        panel = PJXResizablePanel(id="p", min=25, max=75)
        assert panel.min_css is None
        assert panel.max_css is None

    def test_px_bounds_pass_through(self):
        panel = PJXResizablePanel(id="p", min="120px", max="400px")
        assert panel.min_css == "120px"
        assert panel.max_css == "400px"

    def test_content_min_becomes_min_content(self):
        assert PJXResizablePanel(id="p", min="content").min_css == "min-content"


class TestRender:
    def test_renders_a_single_panel_div(self, session):
        html = _html(session, size=30, min=15, content="x")
        assert html.count("<div") == 1
        assert 'class="pjx-resizable-group__panel"' in html
        assert "data-pjx-resizable-panel" in html

    def test_size_and_bounds_land_on_data_attrs(self, session):
        html = _html(session, size=30, min=15)
        assert 'data-size="30' in html
        assert 'data-min="15' in html
        assert 'data-max="100' in html
        assert "flex-grow: 30" in _style(html)

    def test_without_size_grow_defaults_to_one_and_data_size_is_omitted(self, session):
        html = _html(session)
        assert "flex-grow: 1" in _style(html)
        assert "data-size" not in html

    def test_class_name_appends(self, session):
        assert 'class="pjx-resizable-group__panel lead"' in _html(
            session, class_name="lead"
        )

    def test_px_min_emits_the_css_var(self, session):
        html = _html(session, min="120px")
        assert 'data-min="120px"' in html
        assert "--pjx-resizable-min: 120px" in _style(html)

    def test_content_min_emits_min_content(self, session):
        html = _html(session, min="content")
        assert 'data-min="content"' in html
        assert "--pjx-resizable-min: min-content" in _style(html)

    def test_px_max_emits_the_css_var(self, session):
        html = _html(session, max="400px")
        assert 'data-max="400px"' in html
        assert "--pjx-resizable-max: 400px" in _style(html)

    def test_percentage_bounds_emit_no_inline_css_var(self, session):
        # percentages stay on the JS clamp path; only the CSS rules name the var
        style = _style(_html(session, min=25, max=75))
        assert "--pjx-resizable-min" not in style
        assert "--pjx-resizable-max" not in style

    def test_content_string_is_emitted_escaped(self, session):
        html = _html(session, content="<b>x</b>")
        assert "<b>x</b>" not in html
        assert "&lt;b&gt;" in html


class TestAssets:
    def test_stylesheet_is_frozen_on_the_descriptor(self):
        css = PJXResizablePanel.__pjx_descriptor__.css_paths
        assert len(css) == 1
        assert css[0].name == "pjx_resizable_panel.css"
        assert css[0].is_file()

    def test_stylesheet_consumes_the_min_and_max_custom_properties(self):
        source = PJXResizablePanel.__pjx_descriptor__.css_paths[0].read_text()
        assert "var(--pjx-resizable-min" in source
        assert "var(--pjx-resizable-max" in source

    def test_no_script_asset(self):
        assert PJXResizablePanel.__pjx_descriptor__.js_paths == ()
