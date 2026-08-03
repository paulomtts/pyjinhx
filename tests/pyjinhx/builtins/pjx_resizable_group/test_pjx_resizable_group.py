"""PJXResizableGroup — v0.x field/markup parity on the v2 engine.

Ported from v0.x tests/unit/test_resizable.py. The v0.x browser suite
(tests/reactivity/test_resizable.py) drives a Playwright sink page that has no
v2 counterpart; its contract is covered here by asserting the shipped
controller still carries the markers and handlers those tests depend on.
"""

import pytest
from pydantic import ValidationError

from pyjinhx.builtins.ui.pjx_resizable_group import PJXResizableGroup
from pyjinhx.builtins.ui.pjx_resizable_handle import PJXResizableHandle
from pyjinhx.builtins.ui.pjx_resizable_panel import PJXResizablePanel
from pyjinhx.render import render
from pyjinhx.session import RenderSession


@pytest.fixture
def session():
    # template_dir="/" so the descriptor's absolute template path resolves,
    # same fixture shape as the sibling builtin tests.
    return RenderSession(template_dir="/")


def _html(session, **kwargs) -> str:
    base = {"id": "g"}
    base.update(kwargs)
    return render(PJXResizableGroup(**base), session)  # type: ignore[arg-type]


def _split(session, **kwargs) -> str:
    return _html(
        session,
        content=[
            PJXResizablePanel(id="l", size=40, content="left"),
            PJXResizableHandle(id="h"),
            PJXResizablePanel(id="r", size=60, content="right"),
        ],
        **kwargs,
    )


class TestFields:
    def test_defaults(self):
        group = PJXResizableGroup(id="g")
        assert group.direction == "row"
        assert group.class_name == ""
        assert group.content == ""

    def test_content_is_the_children_field(self):
        assert PJXResizableGroup._pjx_children_field == "content"

    def test_direction_accepts_column(self):
        assert PJXResizableGroup(id="g", direction="column").direction == "column"

    def test_direction_rejects_anything_else(self):
        with pytest.raises(ValidationError):
            PJXResizableGroup(id="g", direction="diagonal")  # type: ignore[arg-type]

    def test_undeclared_kwarg_raises(self):
        with pytest.raises(ValidationError):
            PJXResizableGroup(id="g", bogus="x")  # type: ignore[call-arg]


class TestRender:
    def test_single_root_with_role_and_direction(self, session):
        html = _split(session)
        assert html.startswith('<div id="g"')
        assert 'role="group"' in html
        assert "pjx-resizable-group--row" in html
        assert "data-pjx-resizable-group" in html
        assert 'data-direction="row"' in html
        assert html.rstrip().endswith("</div>")

    def test_direction_column(self, session):
        html = _split(session, direction="column")
        assert "pjx-resizable-group--column" in html
        assert 'data-direction="column"' in html

    def test_composition_order_panel_handle_panel(self, session):
        html = _split(session)
        assert (
            html.index("data-pjx-resizable-panel")
            < html.index("data-pjx-resizable-handle")
            < html.rindex("data-pjx-resizable-panel")
        )
        assert "left" in html and "right" in html

    def test_class_name_appends(self, session):
        assert "pjx-resizable-group--row mine" in _split(session, class_name="mine")

    def test_empty_content_still_renders_the_shell(self, session):
        html = _html(session)
        assert "data-pjx-resizable-group" in html


class TestAssets:
    def test_stylesheet_is_frozen_on_the_descriptor(self):
        css = PJXResizableGroup.__pjx_descriptor__.css_paths
        assert len(css) == 1
        assert css[0].name == "pjx_resizable_group.css"
        assert css[0].is_file()

    def test_script_is_frozen_on_the_descriptor(self):
        js = PJXResizableGroup.__pjx_descriptor__.js_paths
        assert len(js) == 1
        assert js[0].name == "pjx_resizable_group.js"
        assert js[0].is_file()

    def test_script_drives_off_the_resizable_markers(self):
        source = PJXResizableGroup.__pjx_descriptor__.js_paths[0].read_text()
        assert "data-pjx-resizable-group" in source
        assert "data-pjx-resizable-panel" in source
        assert "data-pjx-resizable-handle" in source

    def test_script_binds_once_and_reinits_after_settle(self):
        source = PJXResizableGroup.__pjx_descriptor__.js_paths[0].read_text()
        assert "pjxResizableBound" in source
        assert "htmx:afterSettle" in source

    def test_script_keeps_the_drag_keyboard_and_touch_contracts(self):
        source = PJXResizableGroup.__pjx_descriptor__.js_paths[0].read_text()
        for handler in ("mousedown", "mousemove", "mouseup", "touchstart", "keydown"):
            assert f'"{handler}"' in source
        assert "pjx:resize" in source
        assert "pjx-resizable-group--dragging" in source

    def test_render_accumulates_both_assets_into_the_session(self, session):
        from pyjinhx.session import accumulate_assets

        session.on_rendered.append(accumulate_assets)
        _html(session)
        assert {p.name for p in session.css_assets} == {"pjx_resizable_group.css"}
        assert {p.name for p in session.js_assets} == {"pjx_resizable_group.js"}
