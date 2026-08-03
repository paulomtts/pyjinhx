"""PJXCardBody renders a single-root card region (port of v0.x pyjinhx/builtins/ui/pjx_card_body)."""

import pytest

from pyjinhx.builtins.ui.pjx_card_body import PJXCardBody
from pyjinhx.builtins.ui.pjx_divider import PJXDivider
from pyjinhx.rendering import render
from pyjinhx.session import RenderSession


@pytest.fixture
def card_body_session():
    """Loader rooted at "/" so absolute descriptor template paths resolve.

    ClassDescriptor.template_path is absolute and render() feeds it straight to
    the session's FileSystemLoader; Jinja only resolves an absolute path when
    the loader root is "/". Same fixture shape as tests/pyjinhx/builtins/pjx_empty_state.
    """
    return RenderSession(template_dir="/")


def _html(session, **kw) -> str:
    return render(PJXCardBody(id="b", **kw), session)


def test_default_render_is_single_empty_div(card_body_session):
    assert _html(card_body_session) == '<div id="b" class="pjx-card__body"></div>'


def test_string_content_renders_escaped_inside_root(card_body_session):
    html = _html(card_body_session, content="<p>hi</p>")
    assert html.count("<div") == 1
    assert "&lt;p&gt;hi&lt;/p&gt;" in html
    assert "<p>hi</p>" not in html


def test_component_content_renders_nested(card_body_session):
    html = _html(card_body_session, content=PJXDivider(id="d"))
    assert html.count("<div") == 1
    assert '<hr id="d"' in html


def test_class_name_appended_to_root(card_body_session):
    assert 'class="pjx-card__body tall"' in _html(card_body_session, class_name="tall")


def test_empty_class_name_adds_nothing(card_body_session):
    assert 'class="pjx-card__body"' in _html(card_body_session, class_name="")
