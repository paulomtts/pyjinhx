"""PJXCardFooter renders a single-root card footer (port of v0.x pyjinhx/builtins/ui/pjx_card_footer)."""

import pytest

from pyjinhx2.builtins.ui.pjx_card_footer import PJXCardFooter
from pyjinhx2.render import render
from pyjinhx2.session import RenderSession


@pytest.fixture
def card_footer_session():
    """Loader rooted at "/" so absolute descriptor template paths resolve."""
    return RenderSession(template_dir="/")


def _html(session, **kw) -> str:
    return render(PJXCardFooter(id="f", **kw), session)


def test_default_render_is_single_empty_footer(card_footer_session):
    assert (
        _html(card_footer_session)
        == '<footer id="f" class="pjx-card__footer"></footer>'
    )


def test_text_content_renders_inside_root(card_footer_session):
    html = _html(card_footer_session, content="Updated")
    assert html.count("<footer") == 1
    assert "Updated" in html


def test_string_content_renders_escaped(card_footer_session):
    html = _html(card_footer_session, content="<b>x</b>")
    assert "&lt;b&gt;x&lt;/b&gt;" in html
    assert "<b>x</b>" not in html


def test_class_name_appended_to_root(card_footer_session):
    assert 'class="pjx-card__footer bar"' in _html(
        card_footer_session, class_name="bar"
    )
