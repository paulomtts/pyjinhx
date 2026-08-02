"""PJXCardHeader renders a single-root header with a title shortcut (port of v0.x pyjinhx/builtins/ui/pjx_card_header)."""

import pytest

from pyjinhx2.builtins.ui.pjx_card_header import PJXCardHeader
from pyjinhx2.builtins.ui.pjx_divider import PJXDivider
from pyjinhx2.render import render
from pyjinhx2.session import RenderSession


@pytest.fixture
def card_header_session():
    """Loader rooted at "/" so absolute descriptor template paths resolve."""
    return RenderSession(template_dir="/")


def _html(session, **kw) -> str:
    return render(PJXCardHeader(id="h", **kw), session)


def test_default_render_is_single_empty_header(card_header_session):
    assert _html(card_header_session) == '<header id="h" class="pjx-card__header"></header>'


def test_title_renders_styled_h3(card_header_session):
    html = _html(card_header_session, title="Q3 report")
    assert html.count("<header") == 1
    assert 'id="h"' in html
    assert 'class="pjx-card__header"' in html
    assert '<h3 class="pjx-card__title">Q3 report</h3>' in html


def test_content_used_when_no_title(card_header_session):
    html = _html(card_header_session, content=PJXDivider(id="d"))
    assert '<hr id="d"' in html
    assert '<h3 class="pjx-card__title">' not in html


def test_title_wins_over_content(card_header_session):
    html = _html(card_header_session, title="T", content="dropped")
    assert '<h3 class="pjx-card__title">T</h3>' in html
    assert "dropped" not in html


def test_title_renders_escaped(card_header_session):
    html = _html(card_header_session, title="<script>x</script>")
    assert "&lt;script&gt;x&lt;/script&gt;" in html
    assert "<script>" not in html


def test_class_name_appended_to_root(card_header_session):
    html = _html(card_header_session, class_name="lead", content="x")
    assert 'class="pjx-card__header lead"' in html
