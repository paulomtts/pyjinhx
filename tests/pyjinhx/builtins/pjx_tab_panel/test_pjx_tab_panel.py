"""PJXTabPanel renders the hidden-by-default panel a tab reveals (port of v0.x pyjinhx/builtins/ui/pjx_tab_panel)."""

import pytest

from pyjinhx.builtins.ui.pjx_tab_panel import PJXTabPanel
from pyjinhx.rendering import render
from pyjinhx.session import RenderSession


@pytest.fixture
def tab_panel_session():
    """Loader rooted at "/" so absolute descriptor template paths resolve."""
    return RenderSession(template_dir="/")


def _html(session, **kw) -> str:
    return render(PJXTabPanel(id="p", **kw), session)


def test_default_render_is_a_single_hidden_region(tab_panel_session):
    assert _html(tab_panel_session) == (
        '<div id="p" role="tabpanel" class="pjx-tab-group__panel"'
        " data-pjx-region hidden></div>"
    )


def test_tab_renders_aria_labelledby(tab_panel_session):
    """The panel points back at the tab that controls it, closing the a11y loop."""
    assert 'aria-labelledby="t1"' in _html(tab_panel_session, tab="t1")


def test_tab_default_omits_aria_labelledby(tab_panel_session):
    assert "aria-labelledby" not in _html(tab_panel_session)


def test_class_name_appended_to_root(tab_panel_session):
    assert 'class="pjx-tab-group__panel mine"' in _html(
        tab_panel_session, class_name="mine"
    )


def test_string_content_renders_escaped_inside_root(tab_panel_session):
    """v2 narrowing of v0.x: a plain str in a Slot is escaped; only components emit markup."""
    html = _html(tab_panel_session, content="<p>raw</p>")
    assert html.count("<div") == 1
    assert "&lt;p&gt;raw&lt;/p&gt;" in html
    assert "<p>raw</p>" not in html


def test_css_is_discovered_from_the_component_directory():
    assert any(
        p.name == "pjx_tab_panel.css" for p in PJXTabPanel.__pjx_descriptor__.css_paths
    )
