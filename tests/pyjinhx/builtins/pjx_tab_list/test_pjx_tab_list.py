"""PJXTabList renders the role="tablist" row of a tab group (port of v0.x pyjinhx/builtins/ui/pjx_tab_list)."""

import pytest

from pyjinhx.builtins.ui.pjx_tab_list import PJXTabList
from pyjinhx.rendering import render
from pyjinhx.session import RenderSession


@pytest.fixture
def tab_list_session():
    """Loader rooted at "/" so absolute descriptor template paths resolve."""
    return RenderSession(template_dir="/")


def _html(session, **kw) -> str:
    return render(PJXTabList(id="l", **kw), session)


def test_default_render_is_a_single_horizontal_tablist(tab_list_session):
    assert _html(tab_list_session) == (
        '<div id="l" role="tablist" aria-label="Tabs" aria-orientation="horizontal"'
        ' class="pjx-tab-group__list"></div>'
    )


def test_label_overrides_the_aria_label(tab_list_session):
    assert 'aria-label="Files"' in _html(tab_list_session, label="Files")


def test_reorderable_emits_the_reorder_hook_attribute(tab_list_session):
    """The group JS only makes tabs draggable inside a tablist carrying this attribute."""
    assert "data-pjx-tab-reorderable" in _html(tab_list_session, reorderable=True)


def test_reorderable_default_omits_the_hook_attribute(tab_list_session):
    assert "data-pjx-tab-reorderable" not in _html(tab_list_session, reorderable=False)


def test_class_name_appended_to_root(tab_list_session):
    assert 'class="pjx-tab-group__list mine"' in _html(
        tab_list_session, class_name="mine"
    )


def test_string_content_renders_escaped_inside_root(tab_list_session):
    """v2 narrowing of v0.x: a plain str in a Slot is escaped; only components emit markup."""
    html = _html(tab_list_session, content="<p>raw</p>")
    assert html.count("<div") == 1
    assert "&lt;p&gt;raw&lt;/p&gt;" in html
    assert "<p>raw</p>" not in html


def test_css_is_discovered_from_the_component_directory():
    assert any(
        p.name == "pjx_tab_list.css" for p in PJXTabList.__pjx_descriptor__.css_paths
    )
