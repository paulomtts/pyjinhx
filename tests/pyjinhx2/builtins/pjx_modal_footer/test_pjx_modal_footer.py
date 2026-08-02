"""PJXModalFooter renders a single-root modal region (port of v0.x pyjinhx/builtins/ui/pjx_modal_footer)."""

import pytest

from pyjinhx2.builtins.ui.pjx_divider import PJXDivider
from pyjinhx2.builtins.ui.pjx_modal_footer import PJXModalFooter
from pyjinhx2.render import render
from pyjinhx2.session import RenderSession


@pytest.fixture
def modal_footer_session():
    """Loader rooted at "/" so absolute descriptor template paths resolve."""
    return RenderSession(template_dir="/")


def _html(session, **kw) -> str:
    return render(PJXModalFooter(id="f", **kw), session)


def test_default_render_is_single_empty_footer(modal_footer_session):
    assert (
        _html(modal_footer_session)
        == '<footer id="f" class="pjx-modal__footer"></footer>'
    )


def test_class_name_appended_to_root(modal_footer_session):
    assert 'class="pjx-modal__footer right"' in _html(
        modal_footer_session, class_name="right"
    )


def test_empty_class_name_adds_nothing(modal_footer_session):
    assert 'class="pjx-modal__footer"' in _html(modal_footer_session, class_name="")


def test_component_content_renders_nested(modal_footer_session):
    html = _html(modal_footer_session, content=PJXDivider(id="d"))
    assert html.count("<footer") == 1
    assert '<hr id="d"' in html


def test_string_content_renders_escaped_inside_root(modal_footer_session):
    html = _html(modal_footer_session, content="<p>hi</p>")
    assert html.count("<footer") == 1
    assert "&lt;p&gt;hi&lt;/p&gt;" in html
    assert "<p>hi</p>" not in html
