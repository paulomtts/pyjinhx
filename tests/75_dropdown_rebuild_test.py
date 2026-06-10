import os
import re

import pyjinhx.builtins.ui.dropdown as dropdown_pkg
from pyjinhx.builtins import Dropdown


def _root_tag(html: str) -> str:
    """Extract just the opening tag of the outer <div class="px-dropdown"> element."""
    m = re.search(r'(<div[^>]*class="px-dropdown[^"]*"[^>]*>)', html)
    return m.group(1) if m else html


def test_dropdown_renders_items_and_wiring():
    html = str(Dropdown(
        id="dd", trigger="Menu",
        items=["<a role='menuitem' href='/a'>A</a>", "<a role='menuitem' href='/b'>B</a>"],
        menu_label="Ações",
    ).render())
    assert 'data-px-toggle="dd-menu"' in html
    assert "data-px-popover-panel" in html
    assert 'aria-label="Ações"' in html
    assert "/a" in html and "/b" in html
    assert "hidden" in html
    assert "onclick" not in html


def test_dropdown_align_end():
    html = str(Dropdown(id="dd", trigger="t", items=[], align="end").render())
    assert 'data-px-align="end"' in html


def test_dropdown_headless_mode():
    html = str(Dropdown(id="dd", trigger="t", items=[], behavior=False).render())
    root = _root_tag(html)
    # Root div should NOT carry data-px-popover when behavior=False
    assert " data-px-popover" not in root
    # Button should NOT carry data-px-toggle when behavior=False
    assert 'data-px-toggle=' not in html


def test_dropdown_ships_no_js():
    folder = os.path.dirname(dropdown_pkg.__file__)
    assert not [f for f in os.listdir(folder) if f.endswith(".js")]
