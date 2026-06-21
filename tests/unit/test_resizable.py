"""PJXResizableGroup: the split-pane container that composes panels + handles."""
import pytest

from pyjinhx import Renderer
from pyjinhx.builtins import PJXResizableGroup, PJXResizableHandle, PJXResizablePanel


@pytest.fixture(autouse=True)
def _env(tmp_path):
    Renderer.set_default_environment(str(tmp_path))


def _group(**kw):
    kw.setdefault(
        "content",
        PJXResizablePanel(id="l", size=40, content="left").render()
        + PJXResizableHandle(id="h").render()
        + PJXResizablePanel(id="r", size=60, content="right").render(),
    )
    return str(PJXResizableGroup(id="g", **kw).render())


def test_group_single_root_with_role_and_direction():
    html = _group()
    assert html.count("<div") >= 1
    assert 'role="group"' in html
    assert "pjx-resizable-group--row" in html
    assert 'data-pjx-resizable-group' in html
    assert 'data-direction="row"' in html


def test_direction_column():
    html = _group(direction="column")
    assert "pjx-resizable-group--column" in html
    assert 'data-direction="column"' in html


def test_composition_order_panel_handle_panel():
    html = _group()
    assert html.index("data-pjx-resizable-panel") < html.index("data-pjx-resizable-handle") < html.rindex("data-pjx-resizable-panel")
    assert "left" in html and "right" in html


def test_class_name_appends():
    assert "pjx-resizable-group mine" in _group(class_name="mine")
