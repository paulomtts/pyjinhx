"""PJXTabGroup renders the single-root group shell of the tab family (port of v0.x pyjinhx/builtins/ui/pjx_tab_group)."""

import pytest
from pydantic import ValidationError

from pyjinhx.builtins.pjx_icon import PJXIcon
from pyjinhx.builtins.pjx_tab import PJXTab
from pyjinhx.builtins.pjx_tab_group import PJXTabGroup
from pyjinhx.builtins.pjx_tab_list import PJXTabList
from pyjinhx.builtins.pjx_tab_panel import PJXTabPanel
from pyjinhx.components import discovery
from pyjinhx.rendering.pipeline import render
from pyjinhx.rendering.session import RenderSession


@pytest.fixture
def tab_group_session():
    """Loader rooted at "/" so absolute descriptor template paths resolve."""
    return RenderSession()


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


def test_extra_attrs_surface_on_the_root(tab_group_session):
    html = _html(tab_group_session, extra_attrs={"data-test": "1"})
    assert 'data-test="1"' in html
    assert html.count("<div") == 1


def test_string_content_renders_raw_inside_root(tab_group_session):
    """ADR 0003: a plain str in a Slot is authored markup, not escaped."""
    html = _html(tab_group_session, content="<p>raw</p>")
    assert html.count("<div") == 1
    assert "<p>raw</p>" in html


def test_undeclared_field_is_rejected(tab_group_session):
    """BaseComponent is strict: v0.x's **kwargs passthrough is gone."""
    with pytest.raises(ValidationError):
        PJXTabGroup(id="g", nope="x")  # pyright: ignore[reportCallIssue]


def test_assets_are_discovered_from_the_component_directory():
    """CSS/JS sit next to the module and are picked up by the descriptor, with no manual wiring."""
    descriptor = PJXTabGroup.__pjx_descriptor__
    assert any(p.name == "pjx_tab_group.js" for p in descriptor.js_paths)
    assert any(p.name == "pjx_tab_group.css" for p in descriptor.css_paths)


# A composed group renders the list/tab/panel wiring the JS expects to find (port of v0.x tests/reactivity/test_tabs.py and test_tab_reorder.py).


@pytest.fixture
def tabs_session():
    """Loader rooted at "/" so absolute descriptor template paths resolve."""
    return RenderSession()


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
