"""Dropdown menu items and popover panels carry sensible default styling."""
import pytest

from pyjinhx import Renderer
from pyjinhx.builtins import PJXDropdown, PJXPopover, PJXPopoverPanel, PJXPopoverTrigger


@pytest.fixture(autouse=True)
def _env(tmp_path):
    Renderer.set_default_environment(str(tmp_path))


def test_dropdown_inlines_menu_item_styling():
    html = str(PJXDropdown(trigger="Actions", items=["<button>Edit</button>"]).render())
    assert ".pjx-dropdown__menu button" in html  # default item rule is shipped + inlined


def test_popover_panel_has_padding_token():
    html = str(
        PJXPopover(
            id="p",
            content=PJXPopoverPanel(id="p-p", content="x").render(),
        ).render()
    )
    assert "--pjx-popover-padding" in html
