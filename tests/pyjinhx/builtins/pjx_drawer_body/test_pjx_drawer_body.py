"""PJXDrawerBody renders a single-root drawer region (port of v0.x pyjinhx/builtins/ui/pjx_drawer_body)."""

import pytest

from pyjinhx.builtins.ui.pjx_divider import PJXDivider
from pyjinhx.builtins.ui.pjx_drawer_body import PJXDrawerBody
from pyjinhx.rendering import render
from pyjinhx.session import RenderSession


@pytest.fixture
def drawer_body_session():
    """Loader rooted at "/" so absolute descriptor template paths resolve."""
    return RenderSession()


def _html(session, **kw) -> str:
    return render(PJXDrawerBody(id="b", **kw), session)


def test_default_render_is_single_empty_div(drawer_body_session):
    assert _html(drawer_body_session) == '<div id="b" class="pjx-drawer__body"></div>'


def test_id_is_stamped_on_the_root(drawer_body_session):
    assert 'id="body-main"' in render(
        PJXDrawerBody(id="body-main"), drawer_body_session
    )


def test_class_name_appended_to_root(drawer_body_session):
    assert 'class="pjx-drawer__body extra"' in _html(
        drawer_body_session, class_name="extra"
    )


def test_empty_class_name_adds_nothing(drawer_body_session):
    assert 'class="pjx-drawer__body"' in _html(drawer_body_session, class_name="")


def test_plain_text_content_renders(drawer_body_session):
    assert "Hello" in _html(drawer_body_session, content="Hello")


def test_component_content_renders_nested(drawer_body_session):
    html = _html(drawer_body_session, content=PJXDivider(id="d"))
    assert html.count("<div") == 1
    assert '<hr id="d"' in html


def test_string_content_renders_raw_inside_root(drawer_body_session):
    """ADR 0003: golden drawer_body.html's raw <p> markup stays raw (Slot exemption)."""
    html = _html(drawer_body_session, content="<p>Body content</p>")
    assert html.count("<div") == 1
    assert "<p>Body content</p>" in html
