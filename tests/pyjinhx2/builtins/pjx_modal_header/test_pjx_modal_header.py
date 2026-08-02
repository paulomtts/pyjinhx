"""PJXModalHeader renders a single-root modal region with a close affordance (port of v0.x pyjinhx/builtins/ui/pjx_modal_header)."""

import pytest

from pyjinhx2.builtins.ui.pjx_divider import PJXDivider
from pyjinhx2.builtins.ui.pjx_modal_header import PJXModalHeader
from pyjinhx2.render import render
from pyjinhx2.session import RenderSession


@pytest.fixture
def modal_header_session():
    """Loader rooted at "/" so absolute descriptor template paths resolve."""
    return RenderSession(template_dir="/")


def _html(session, **kw) -> str:
    return render(PJXModalHeader(id="h", **kw), session)


def test_default_render_is_single_header_with_close_button(modal_header_session):
    html = _html(modal_header_session)
    assert html.count("<header") == 1
    assert 'id="h"' in html
    assert 'class="pjx-modal__header"' in html
    assert 'class="pjx-modal__close"' in html
    assert "data-pjx-close" in html
    assert 'type="button"' in html


def test_class_name_appended_to_root(modal_header_session):
    assert 'class="pjx-modal__header wide"' in _html(
        modal_header_session, class_name="wide"
    )


def test_title_renders_the_title_span(modal_header_session):
    html = _html(modal_header_session, title="Hello")
    assert '<span id="h-title" class="pjx-modal__title">Hello</span>' in html


def test_content_renders_when_title_is_empty(modal_header_session):
    html = _html(modal_header_session, content=PJXDivider(id="d"))
    assert '<hr id="d"' in html
    assert "pjx-modal__title" not in html


def test_title_wins_over_content(modal_header_session):
    html = _html(modal_header_session, title="Hello", content=PJXDivider(id="d"))
    assert "pjx-modal__title" in html
    assert '<hr id="d"' not in html


def test_close_label_defaults_to_close(modal_header_session):
    assert 'aria-label="Close"' in _html(modal_header_session)


def test_close_label_is_overridable(modal_header_session):
    assert 'aria-label="Fechar"' in _html(modal_header_session, close_label="Fechar")


def test_close_content_defaults_to_the_glyph(modal_header_session):
    assert ">✕</button>" in _html(modal_header_session)


def test_close_content_accepts_a_component(modal_header_session):
    """v2 narrowing of v0.x: raw-HTML strings are escaped, so markup arrives as a component."""
    html = _html(modal_header_session, close_content=PJXDivider(id="glyph"))
    assert '<hr id="glyph"' in html
    assert "✕" not in html
