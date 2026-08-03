"""PJXModalBody renders a single-root modal region (port of v0.x pyjinhx/builtins/ui/pjx_modal_body)."""

import pytest

from pyjinhx.builtins.ui.pjx_divider import PJXDivider
from pyjinhx.builtins.ui.pjx_modal_body import PJXModalBody
from pyjinhx.render import render
from pyjinhx.session import RenderSession


@pytest.fixture
def modal_body_session():
    """Loader rooted at "/" so absolute descriptor template paths resolve."""
    return RenderSession(template_dir="/")


def _html(session, **kw) -> str:
    return render(PJXModalBody(id="b", **kw), session)


def test_default_render_is_single_empty_div(modal_body_session):
    assert _html(modal_body_session) == '<div id="b" class="pjx-modal__body"></div>'


def test_class_name_appended_to_root(modal_body_session):
    assert 'class="pjx-modal__body tall"' in _html(
        modal_body_session, class_name="tall"
    )


def test_empty_class_name_adds_nothing(modal_body_session):
    assert 'class="pjx-modal__body"' in _html(modal_body_session, class_name="")


def test_component_content_renders_nested(modal_body_session):
    html = _html(modal_body_session, content=PJXDivider(id="d"))
    assert html.count("<div") == 1
    assert '<hr id="d"' in html


def test_string_content_renders_escaped_inside_root(modal_body_session):
    html = _html(modal_body_session, content="<p>hi</p>")
    assert html.count("<div") == 1
    assert "&lt;p&gt;hi&lt;/p&gt;" in html
    assert "<p>hi</p>" not in html
