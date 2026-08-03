"""PJXTab renders one tab trigger, optionally with an icon and a close button (port of v0.x pyjinhx/builtins/ui/pjx_tab)."""

import pytest

from pyjinhx import discovery
from pyjinhx.builtins.ui.pjx_icon import PJXIcon
from pyjinhx.builtins.ui.pjx_tab import PJXTab
from pyjinhx.render import render
from pyjinhx.session import RenderSession


@pytest.fixture
def tab_session():
    """Loader rooted at "/" so absolute descriptor template paths resolve."""
    return RenderSession(template_dir="/")


@pytest.fixture
def icon_registered():
    """Publish the ``pjx_icon`` tag for this test only.

    ``<PJXIcon/>`` in the tab template is resolved at render time through
    discovery's tag map, not through a Python import; an unclaimed tag is
    emitted verbatim instead. The map is process-global, so it is snapshotted
    and restored.
    """
    before = discovery._registry.mapping
    discovery.register_class("pjx_icon", PJXIcon)
    yield
    discovery._registry.mapping = before


def _html(session, **kw) -> str:
    return render(PJXTab(id="t", **kw), session)


def test_default_render_is_a_single_unselected_tab(tab_session, icon_registered):
    assert _html(tab_session) == (
        '<div id="t" role="tab" class="pjx-tab" tabindex="-1" aria-selected="false"'
        ' data-pjx-tab><span class="pjx-tab__label"></span></div>'
    )


def test_selected_sets_state_class_tabindex_and_aria(tab_session, icon_registered):
    html = _html(tab_session, selected=True)
    assert 'class="pjx-tab pjx-tab--selected"' in html
    assert 'tabindex="0"' in html
    assert 'aria-selected="true"' in html


def test_panel_renders_aria_controls(tab_session, icon_registered):
    assert 'aria-controls="p1"' in _html(tab_session, panel="p1")


def test_panel_default_omits_aria_controls(tab_session, icon_registered):
    assert "aria-controls" not in _html(tab_session)


def test_closeable_renders_the_close_button(tab_session, icon_registered):
    html = _html(tab_session, closeable=True)
    assert "pjx-tab--closeable" in html
    assert "data-pjx-tab-close" in html
    assert 'aria-label="Close"' in html


def test_close_label_overrides_the_button_aria_label(tab_session, icon_registered):
    assert 'aria-label="Dismiss"' in _html(
        tab_session, closeable=True, close_label="Dismiss"
    )


def test_pinned_suppresses_the_close_button(tab_session, icon_registered):
    """A pinned tab cannot be closed, so the closeable affordance is dropped entirely."""
    html = _html(tab_session, closeable=True, pinned=True)
    assert "data-pjx-tab-pinned" in html
    assert "pjx-tab--pinned" in html
    assert "data-pjx-tab-close" not in html
    assert "pjx-tab--closeable" not in html


def test_icon_tag_expands_to_svg_markup(tab_session, icon_registered):
    html = _html(tab_session, icon="x")
    assert "<PJXIcon" not in html
    assert "<svg" in html
    assert 'class="pjx-icon pjx-tab__icon"' in html


def test_icon_default_emits_no_icon(tab_session, icon_registered):
    assert "pjx-tab__icon" not in _html(tab_session)


def test_class_name_appended_to_root(tab_session, icon_registered):
    assert 'class="pjx-tab mine"' in _html(tab_session, class_name="mine")


def test_string_content_renders_escaped_inside_the_label(tab_session, icon_registered):
    """v2 narrowing of v0.x: a plain str in a Slot is escaped; only components emit markup."""
    html = _html(tab_session, content="<p>raw</p>")
    assert html.count('<div id="t"') == 1
    assert "&lt;p&gt;raw&lt;/p&gt;" in html
    assert "<p>raw</p>" not in html


def test_css_is_discovered_from_the_component_directory():
    assert any(p.name == "pjx_tab.css" for p in PJXTab.__pjx_descriptor__.css_paths)
