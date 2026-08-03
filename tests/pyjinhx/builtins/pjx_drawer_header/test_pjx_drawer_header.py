"""PJXDrawerHeader renders a single-root drawer region with a close affordance (port of v0.x pyjinhx/builtins/ui/pjx_drawer_header)."""

import pytest

from pyjinhx.builtins.ui.pjx_divider import PJXDivider
from pyjinhx.builtins.ui.pjx_drawer_header import PJXDrawerHeader
from pyjinhx.rendering import render
from pyjinhx.session import RenderSession


@pytest.fixture
def drawer_header_session():
    """Loader rooted at "/" so absolute descriptor template paths resolve."""
    return RenderSession()


def _html(session, **kw) -> str:
    return render(PJXDrawerHeader(id="h", **kw), session)


def test_default_render_is_single_header_with_close_button(drawer_header_session):
    html = _html(drawer_header_session)
    assert html.count("<header") == 1
    assert 'id="h"' in html
    assert 'class="pjx-drawer__header"' in html
    assert 'class="pjx-drawer__close"' in html
    assert "data-pjx-close" in html
    assert 'type="button"' in html


def test_class_name_appended_to_root(drawer_header_session):
    assert 'class="pjx-drawer__header sticky"' in _html(
        drawer_header_session, class_name="sticky"
    )


def test_empty_class_name_adds_nothing(drawer_header_session):
    assert 'class="pjx-drawer__header"' in _html(drawer_header_session, class_name="")


def test_title_renders_the_title_span(drawer_header_session):
    html = _html(drawer_header_session, title="Menu")
    assert '<span id="h-title" class="pjx-drawer__title">Menu</span>' in html


def test_title_golden_shape(drawer_header_session):
    """Exact markup, ported from tests/unit/golden/drawer_header_title.html."""
    html = render(PJXDrawerHeader(id="g", title="Settings"), drawer_header_session)
    assert html == (
        '<header id="g" class="pjx-drawer__header">'
        '<span id="g-title" class="pjx-drawer__title">Settings</span>'
        '<button type="button" class="pjx-drawer__close" data-pjx-close '
        'aria-label="Close">✕</button></header>'
    )


def test_content_renders_when_title_is_empty(drawer_header_session):
    html = _html(drawer_header_session, content=PJXDivider(id="d"))
    assert '<hr id="d"' in html
    assert "pjx-drawer__title" not in html


def test_title_wins_over_content(drawer_header_session):
    html = _html(drawer_header_session, title="Menu", content=PJXDivider(id="d"))
    assert "pjx-drawer__title" in html
    assert '<hr id="d"' not in html


def test_string_content_renders_raw(drawer_header_session):
    """ADR 0003: golden drawer_header_content.html's raw <strong> stays raw (Slot exemption)."""
    html = _html(drawer_header_session, content="<strong>Nav</strong>")
    assert "<strong>Nav</strong>" in html


def test_close_label_defaults_to_close(drawer_header_session):
    assert 'aria-label="Close"' in _html(drawer_header_session)


def test_close_label_is_overridable(drawer_header_session):
    assert 'aria-label="Fechar"' in _html(drawer_header_session, close_label="Fechar")


def test_close_content_defaults_to_the_glyph(drawer_header_session):
    assert ">✕</button>" in _html(drawer_header_session)


def test_close_content_accepts_a_component(drawer_header_session):
    """v2 narrowing of v0.x: raw-HTML strings are escaped, so markup arrives as a component."""
    html = _html(drawer_header_session, close_content=PJXDivider(id="glyph"))
    assert '<hr id="glyph"' in html
    assert "✕" not in html
