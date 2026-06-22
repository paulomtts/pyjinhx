"""PJXTab / PJXTabList / PJXTabPanel — compound tab parts."""
import re

import pytest

from pyjinhx import Renderer
from pyjinhx.builtins import PJXTab, PJXTabList, PJXTabPanel


@pytest.fixture(autouse=True)
def _env(tmp_path):
    Renderer.set_default_environment(str(tmp_path))


from pathlib import Path  # noqa: E402

_UI = Path(__file__).resolve().parents[2] / "pyjinhx" / "builtins" / "ui"
_TAB_CSS = {
    "group": _UI / "pjx_tab_group" / "pjx-tab-group.css",
    "tab": _UI / "pjx_tab" / "pjx-tab.css",
    "list": _UI / "pjx_tab_list" / "pjx-tab-list.css",
    "panel": _UI / "pjx_tab_panel" / "pjx-tab-panel.css",
}


def test_tab_group_fills_width_so_it_does_not_jump():
    # Without an explicit width the group shrink-wraps to content and visibly
    # resizes/shifts when a tab is closed or a different panel is shown (#bug).
    assert "width: 100%" in _TAB_CSS["group"].read_text()


def test_tab_css_is_consolidated_no_duplicate_or_dead_rules():
    texts = {k: p.read_text() for k, p in _TAB_CSS.items()}
    # the dict-era `.pjx-tab-group__tab` selector is dead (tabs are `.pjx-tab`)
    for k, t in texts.items():
        assert ".pjx-tab-group__tab" not in t, f"dead selector left in {k} css"
    # each shared selector is owned by exactly one file (no conflicting dupes)
    for sel in (".pjx-tab-group__list {", ".pjx-tab-group__panel {"):
        owners = [k for k, t in texts.items() if sel in t]
        assert len(owners) == 1, f"{sel} defined in {owners}, expected one owner"


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


def test_tab_css_strip_look_is_scoped_to_the_tablist():
    css = _TAB_CSS["tab"].read_text()
    # the base .pjx-tab rule must NOT carry the strip underline track...
    base = re.search(r"^\.pjx-tab \{(.*?)\}", css, re.S | re.M)
    assert base and "border-bottom" not in base.group(1), "base .pjx-tab must be neutral"
    # ...the underline lives under the tablist scope only
    assert ".pjx-tab-group__list .pjx-tab" in css
    assert ".pjx-tab-group__list .pjx-tab--selected" in css
    # standalone active styling keys off aria-current (the non-tablist discriminator)
    assert '.pjx-tab[aria-current="true"]' in css
