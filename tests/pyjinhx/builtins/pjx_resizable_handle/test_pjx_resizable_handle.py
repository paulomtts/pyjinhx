"""PJXResizableHandle — v0.x field/markup parity on the v2 engine.

Ported from v0.x tests/unit/test_resizable_parts.py (handle half).
"""

import pytest
from pydantic import ValidationError

from pyjinhx.builtins.ui.pjx_resizable_handle import PJXResizableHandle
from pyjinhx.rendering import render
from pyjinhx.session import RenderSession


@pytest.fixture
def session():
    # template_dir="/" so the descriptor's absolute template path resolves,
    # same fixture shape as the sibling builtin tests.
    return RenderSession()


def _html(session, **kwargs) -> str:
    base = {"id": "h"}
    base.update(kwargs)
    return render(PJXResizableHandle(**base), session)  # type: ignore[arg-type]


class TestFields:
    def test_defaults(self):
        handle = PJXResizableHandle(id="h")
        assert handle.label == "Resize"
        assert handle.class_name == ""

    def test_no_children_field(self):
        assert PJXResizableHandle._pjx_children_field is None

    def test_undeclared_kwarg_raises(self):
        with pytest.raises(ValidationError):
            PJXResizableHandle(id="h", bogus="x")  # type: ignore[call-arg]


class TestRender:
    def test_renders_a_single_separator_div(self, session):
        html = _html(session)
        assert html.count("<div") == 1
        assert 'role="separator"' in html
        assert 'class="pjx-resizable-group__handle"' in html

    def test_marker_and_tabindex(self, session):
        html = _html(session)
        assert "data-pjx-resizable-handle" in html
        assert 'tabindex="0"' in html

    def test_default_label(self, session):
        assert 'aria-label="Resize"' in _html(session)

    def test_custom_label(self, session):
        assert 'aria-label="Resize sidebar"' in _html(session, label="Resize sidebar")

    def test_aria_value_bounds(self, session):
        html = _html(session)
        assert 'aria-valuemin="0"' in html
        assert 'aria-valuemax="100"' in html

    def test_class_name_appends(self, session):
        assert 'class="pjx-resizable-group__handle grip"' in _html(
            session, class_name="grip"
        )


class TestAssets:
    def test_stylesheet_is_frozen_on_the_descriptor(self):
        css = PJXResizableHandle.__pjx_descriptor__.css_paths
        assert len(css) == 1
        assert css[0].name == "pjx_resizable_handle.css"
        assert css[0].is_file()

    def test_no_script_asset(self):
        assert PJXResizableHandle.__pjx_descriptor__.js_paths == ()
