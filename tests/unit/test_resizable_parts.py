"""PJXResizablePanel / PJXResizableHandle: the leaf parts of the split pane."""
import pytest

from pyjinhx import Renderer
from pyjinhx.builtins import PJXResizableHandle, PJXResizablePanel


@pytest.fixture(autouse=True)
def _env(tmp_path):
    Renderer.set_default_environment(str(tmp_path))


def test_panel_renders_with_size_and_constraints():
    html = str(PJXResizablePanel(id="p", size=30, min=15, content="<b>x</b>").render())
    assert html.count("<div") == 1
    assert 'class="pjx-resizable-group__panel"' in html
    assert "data-pjx-resizable-panel" in html
    assert 'data-size="30' in html
    assert 'data-min="15' in html
    assert 'data-max="100' in html
    assert "flex-grow: 30" in html
    assert "<b>x</b>" in html


def test_panel_without_size_defaults_grow_one():
    html = str(PJXResizablePanel(id="p", content="x").render())
    assert "flex-grow: 1" in html
    assert "data-size" not in html  # omitted when size is None


def test_panel_class_name_appends():
    html = str(PJXResizablePanel(id="p", class_name="lead", content="x").render())
    assert 'class="pjx-resizable-group__panel lead"' in html


def test_handle_renders_separator():
    html = str(PJXResizableHandle(id="h", label="Resize sidebar").render())
    assert html.count("<div") == 1
    assert 'role="separator"' in html
    assert 'class="pjx-resizable-group__handle"' in html
    assert "data-pjx-resizable-handle" in html
    assert 'tabindex="0"' in html
    assert 'aria-label="Resize sidebar"' in html


import pytest as _pytest


def test_panel_px_min_emits_data_and_css_var():
    html = str(PJXResizablePanel(id="p", min="120px").render())
    assert 'data-min="120px"' in html
    assert "--pjx-resizable-min: 120px" in html


def test_panel_content_min_emits_min_content_var():
    html = str(PJXResizablePanel(id="p", min="content").render())
    assert 'data-min="content"' in html
    assert "--pjx-resizable-min: min-content" in html


def test_panel_px_max_emits_max_var():
    html = str(PJXResizablePanel(id="p", max="400px").render())
    assert 'data-max="400px"' in html
    assert "--pjx-resizable-max: 400px" in html


def test_panel_percentage_min_emits_no_css_var():
    html = str(PJXResizablePanel(id="p", min=25).render())
    assert 'data-min="25' in html
    # percentages stay on the JS clamp path; no inline CSS var, only CSS rules reference the var name
    import re as _re
    style_attr = _re.search(r'style="([^"]*)"', html)
    assert style_attr is not None
    assert "--pjx-resizable-min" not in style_attr.group(1)


def test_panel_rejects_content_max():
    with _pytest.raises(ValueError):
        PJXResizablePanel(id="p", max="content")


def test_panel_rejects_bad_unit():
    with _pytest.raises(ValueError):
        PJXResizablePanel(id="p", min="120em")
