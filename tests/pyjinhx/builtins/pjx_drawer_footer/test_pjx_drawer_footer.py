"""PJXDrawerFooter renders a single-root drawer region (port of v0.x pyjinhx/builtins/ui/pjx_drawer_footer)."""

import pytest

from pyjinhx.builtins.ui.pjx_divider import PJXDivider
from pyjinhx.builtins.ui.pjx_drawer_footer import PJXDrawerFooter
from pyjinhx.rendering import render
from pyjinhx.session import RenderSession


@pytest.fixture
def drawer_footer_session():
    """Loader rooted at "/" so absolute descriptor template paths resolve."""
    return RenderSession(template_dir="/")


def _html(session, **kw) -> str:
    return render(PJXDrawerFooter(id="f", **kw), session)


def test_default_render_is_single_empty_footer(drawer_footer_session):
    assert (
        _html(drawer_footer_session)
        == '<footer id="f" class="pjx-drawer__footer"></footer>'
    )


def test_id_is_stamped_on_the_root(drawer_footer_session):
    assert 'id="footer-main"' in render(
        PJXDrawerFooter(id="footer-main"), drawer_footer_session
    )


def test_class_name_appended_to_root(drawer_footer_session):
    assert 'class="pjx-drawer__footer sticky"' in _html(
        drawer_footer_session, class_name="sticky"
    )


def test_empty_class_name_adds_nothing(drawer_footer_session):
    assert 'class="pjx-drawer__footer"' in _html(drawer_footer_session, class_name="")


def test_plain_text_content_renders(drawer_footer_session):
    assert "Save" in _html(drawer_footer_session, content="Save")


def test_component_content_renders_nested(drawer_footer_session):
    html = _html(drawer_footer_session, content=PJXDivider(id="d"))
    assert html.count("<footer") == 1
    assert '<hr id="d"' in html


def test_string_content_renders_escaped_inside_root(drawer_footer_session):
    """Golden drawer_footer.html's raw <button> markup now arrives escaped."""
    html = _html(drawer_footer_session, content="<button>Save</button>")
    assert html.count("<footer") == 1
    assert "&lt;button&gt;Save&lt;/button&gt;" in html
    assert "<button>Save</button>" not in html
