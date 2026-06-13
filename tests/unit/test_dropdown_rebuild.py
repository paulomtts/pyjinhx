import os
import re

import pyjinhx.builtins.ui.pjx_dropdown as dropdown_pkg
from pyjinhx.builtins import PJXDropdown


def _root_tag(html: str) -> str:
    """Extract just the opening tag of the outer <div class="pjx-dropdown"> element."""
    m = re.search(r'(<div[^>]*class="pjx-dropdown[^"]*"[^>]*>)', html)
    return m.group(1) if m else html


def test_dropdown_renders_items_and_wiring():
    html = str(PJXDropdown(
        id="dd", trigger="Menu",
        items=["<a role='menuitem' href='/a'>A</a>", "<a role='menuitem' href='/b'>B</a>"],
        menu_label="Ações",
    ).render())
    assert 'data-pjx-toggle="dd-menu"' in html
    assert "data-pjx-popover-panel" in html
    assert 'aria-label="Ações"' in html
    assert "/a" in html and "/b" in html
    assert "hidden" in html
    assert "onclick" not in html


def test_dropdown_align_end():
    html = str(PJXDropdown(id="dd", trigger="t", items=[], align="end").render())
    # align uses class modifier, not a data attribute
    assert 'pjx-dropdown--align-end' in html
    assert 'data-pjx-align' not in html


def test_dropdown_headless_mode():
    html = str(PJXDropdown(id="dd", trigger="t", items=[], behavior=False).render())
    root = _root_tag(html)
    # Root div should NOT carry data-pjx-popover when behavior=False
    assert " data-pjx-popover" not in root
    # Button should NOT carry data-pjx-toggle when behavior=False
    assert 'data-pjx-toggle=' not in html
    # Menu div should NOT carry data-pjx-popover-panel when behavior=False.
    # Search only the opening tag of the menu div; the inlined JS also
    # contains the string as a selector, so a full-html check would false-positive.
    menu_div = re.search(r'<div[^>]*pjx-dropdown__menu[^>]*>', html)
    assert menu_div and 'data-pjx-popover-panel' not in menu_div.group(0)


def test_nested_dropdown_ships_popover_js():
    # Regression: extra-asset JS must be collected for nested components,
    # not only for the outermost root (fix to apply_component_render_assets).
    from pyjinhx.builtins import PJXCard
    html = str(PJXCard(id="c", body=PJXDropdown(id="dd", trigger="t", items=["x"])).render())
    assert "pjx.popover" in html  # the extra-asset JS arrived despite nesting


def test_dropdown_ships_no_js():
    folder = os.path.dirname(dropdown_pkg.__file__)
    assert not [f for f in os.listdir(folder) if f.endswith(".js")]
