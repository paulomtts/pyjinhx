"""PJXPopover ships one JS file, and that file carries the position primitive verbatim.

The asset walk resolves exactly one script per class by stem, so the shared
pjx_popover_position.js cannot ride along on its own; pjx_popover.js embeds a
byte-identical copy and this test is what keeps the two from drifting.
"""

from pathlib import Path

from pyjinhx.builtins.pjx_popover import PJXPopover
from pyjinhx.components.base import _resolve_asset_paths

ASSETS = Path(__file__).resolve().parents[3] / "pyjinhx" / "builtins" / "pjx_popover"
CONTROLLER = ASSETS / "pjx_popover.js"
PRIMITIVE = ASSETS / "pjx_popover_position.js"


def test_controller_embeds_the_primitive_verbatim():
    assert PRIMITIVE.read_text() in CONTROLLER.read_text()


def test_controller_calls_the_primitive():
    assert "pjx.popoverPosition(" in CONTROLLER.read_text()


def test_popover_still_resolves_exactly_one_script():
    _css, js = _resolve_asset_paths(PJXPopover)
    assert js == (CONTROLLER,)
