"""PJXTabGroup renders the single-root group shell of the tab family (port of v0.x pyjinhx/builtins/ui/pjx_tab_group)."""

import pytest

from pyjinhx2.builtins.ui.pjx_tab_group import PJXTabGroup
from pyjinhx2.render import render
from pyjinhx2.session import RenderSession


@pytest.fixture
def tab_group_session():
    """Loader rooted at "/" so absolute descriptor template paths resolve."""
    return RenderSession(template_dir="/")


def _html(session, **kw) -> str:
    return render(PJXTabGroup(id="g", **kw), session)


def test_default_render_is_a_single_group_div(tab_group_session):
    assert (
        _html(tab_group_session)
        == '<div id="g" class="pjx-tab-group" data-pjx-tab-group></div>'
    )


def test_class_name_appended_to_root(tab_group_session):
    assert 'class="pjx-tab-group mine"' in _html(tab_group_session, class_name="mine")


def test_empty_class_name_adds_nothing(tab_group_session):
    assert 'class="pjx-tab-group"' in _html(tab_group_session, class_name="")


def test_string_content_renders_escaped_inside_root(tab_group_session):
    """v2 narrowing of v0.x: a plain str in a Slot is escaped; only components emit markup."""
    html = _html(tab_group_session, content="<p>raw</p>")
    assert html.count("<div") == 1
    assert "&lt;p&gt;raw&lt;/p&gt;" in html
    assert "<p>raw</p>" not in html


def test_undeclared_field_is_rejected(tab_group_session):
    """BaseComponent is strict: v0.x's **kwargs passthrough is gone."""
    with pytest.raises(Exception):
        PJXTabGroup(id="g", nope="x")


def test_assets_are_discovered_from_the_component_directory():
    """CSS/JS sit next to the module and are picked up by the descriptor, with no manual wiring."""
    descriptor = PJXTabGroup.__pjx_descriptor__
    assert any(p.name == "pjx_tab_group.js" for p in descriptor.js_paths)
    assert any(p.name == "pjx_tab_group.css" for p in descriptor.css_paths)
