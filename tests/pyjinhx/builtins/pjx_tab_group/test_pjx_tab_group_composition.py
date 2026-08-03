"""A composed group renders the list/tab/panel wiring the JS expects to find (port of v0.x tests/reactivity/test_tabs.py and test_tab_reorder.py)."""

import pytest

from pyjinhx import discovery
from pyjinhx.builtins.ui.pjx_icon import PJXIcon
from pyjinhx.builtins.ui.pjx_tab import PJXTab
from pyjinhx.builtins.ui.pjx_tab_group import PJXTabGroup
from pyjinhx.builtins.ui.pjx_tab_list import PJXTabList
from pyjinhx.builtins.ui.pjx_tab_panel import PJXTabPanel
from pyjinhx.render import render
from pyjinhx.session import RenderSession


@pytest.fixture
def tabs_session():
    """Loader rooted at "/" so absolute descriptor template paths resolve."""
    return RenderSession(template_dir="/")


@pytest.fixture
def icon_registered():
    """Publish the ``pjx_icon`` tag for this test only; the map is process-global."""
    before = discovery._registry.mapping
    discovery.register_class("pjx_icon", PJXIcon)
    yield
    discovery._registry.mapping = before


def _group(**tab_kw) -> PJXTabGroup:
    return PJXTabGroup(
        id="g",
        content=PJXTabList(
            id="l",
            reorderable=tab_kw.pop("reorderable", False),
            content=PJXTab(id="t1", panel="p1", selected=True, content="One", **tab_kw),
        ),
    )


def test_group_wraps_list_and_tab_in_one_root(tabs_session, icon_registered):
    html = render(_group(), tabs_session)
    assert html.startswith('<div id="g" class="pjx-tab-group" data-pjx-tab-group>')
    assert html.endswith("</div>")
    assert html.index('id="l"') < html.index('id="t1"')


def test_tab_and_panel_reference_each_other(tabs_session, icon_registered):
    tab_html = render(PJXTab(id="t1", panel="p1", content="One"), tabs_session)
    panel_html = render(PJXTabPanel(id="p1", tab="t1", content="Body"), tabs_session)
    assert 'aria-controls="p1"' in tab_html
    assert 'aria-labelledby="t1"' in panel_html


def test_reorderable_group_marks_only_the_tablist(tabs_session, icon_registered):
    html = render(_group(reorderable=True), tabs_session)
    assert html.count("data-pjx-tab-reorderable") == 1
    assert 'role="tablist"' in html


def test_closeable_tab_inside_a_group_renders_its_close_hook(
    tabs_session, icon_registered
):
    html = render(_group(closeable=True), tabs_session)
    assert "data-pjx-tab-close" in html
    assert "pjx-tab--closeable" in html
