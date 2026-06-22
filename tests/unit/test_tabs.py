"""PJXTab / PJXTabList / PJXTabPanel — compound tab parts."""
import pytest

from pyjinhx import Renderer
from pyjinhx.builtins import PJXTab, PJXTabList, PJXTabPanel


@pytest.fixture(autouse=True)
def _env(tmp_path):
    Renderer.set_default_environment(str(tmp_path))


def test_tablist_role_and_label():
    html = str(PJXTabList(id="l", label="Project tabs", content="x").render())
    assert 'role="tablist"' in html
    assert 'aria-label="Project tabs"' in html
    assert 'aria-orientation="horizontal"' in html
    assert "pjx-tab-group__list" in html


def test_tab_basic_roving_and_label():
    html = str(PJXTab(id="t", content="Home").render())
    assert 'role="tab"' in html
    assert 'tabindex="-1"' in html
    assert 'aria-selected="false"' in html
    assert '<span class="pjx-tab__label">Home</span>' in html


def test_tab_selected_sets_roving_and_modifier():
    html = str(PJXTab(id="t", selected=True, content="Home").render())
    assert 'tabindex="0"' in html
    assert 'aria-selected="true"' in html
    assert "pjx-tab--selected" in html


def test_tab_panel_aria_controls_when_paired():
    html = str(PJXTab(id="t", panel="p1", content="Home").render())
    assert 'aria-controls="p1"' in html


def test_tab_icon_renders_leading_icon():
    html = str(PJXTab(id="t", icon="file", content="Home").render())
    assert "pjx-icon" in html  # nested PJXIcon expanded
    assert "pjx-tab__icon" in html


def test_tab_closeable_renders_close_button():
    html = str(PJXTab(id="t", closeable=True, content="Doc").render())
    assert "pjx-tab--closeable" in html
    assert "data-pjx-tab-close" in html
    assert 'aria-label="Close"' in html


def test_tab_pinned_has_no_close_button():
    html = str(PJXTab(id="t", closeable=True, pinned=True, content="Home").render())
    assert "pjx-tab--pinned" in html
    assert "data-pjx-tab-close" not in html  # pinned forces non-closeable


def test_tab_panel_hidden_region():
    html = str(PJXTabPanel(id="p", tab="t1", content="body").render())
    assert 'role="tabpanel"' in html
    assert "data-pjx-region" in html
    assert "hidden" in html
    assert 'aria-labelledby="t1"' in html
