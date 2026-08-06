"""Opening a popover measures and positions it — the DOM half of #862's pure primitive.

Only the wiring is asserted here: that a roomy popover is left untouched, that a
colliding one gets the primitive's numbers written inline, and that the primitive
stays reachable as a global. The flip/clamp matrix itself is #864's.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

import pytest

if TYPE_CHECKING:
    from playwright.sync_api import Page

CONTROLLER = (
    Path(__file__).resolve().parents[4]
    / "pyjinhx"
    / "builtins"
    / "ui"
    / "pjx_popover"
    / "pjx_popover.js"
)

PAGE = """
<style>
  body { margin: 0; }
  .pjx-popover { position: relative; display: inline-block; }
  .pjx-popover__panel { position: absolute; top: calc(100% + 4px); left: 0;
                        width: 200px; height: 150px; }
  .pjx-popover--align-end .pjx-popover__panel { left: auto; right: 0; }
  .pjx-popover__panel[hidden] { display: none !important; }
</style>
<div id="root" class="pjx-popover" data-pjx-popover style="position: absolute; left: LEFTpx; top: 10px;">
  <button data-pjx-toggle="panel" style="width: 100px; height: 30px;">t</button>
  <div id="panel" class="pjx-popover__panel" data-pjx-popover-panel hidden>p</div>
</div>
"""


@pytest.fixture(autouse=True)
def _require_chromium(request: pytest.FixtureRequest) -> None:
    if "page" not in set(request.fixturenames):
        return
    pytest.importorskip("playwright")
    browser_type: Any = request.getfixturevalue("browser_type")
    if not Path(browser_type.executable_path).exists():
        pytest.skip(
            "chromium is not installed (run: uv run playwright install chromium)"
        )


def _load(page: Page, left: int) -> None:
    page.set_viewport_size({"width": 400, "height": 400})
    page.set_content(PAGE.replace("LEFT", str(left)))
    page.add_script_tag(content=CONTROLLER.read_text())


def test_a_popover_with_room_gets_no_inline_styles(page: Page):
    _load(page, left=10)
    page.click("[data-pjx-toggle]")
    assert (
        page.evaluate("document.getElementById('panel').getAttribute('style')") is None
    )


def test_a_colliding_popover_gets_the_primitive_s_numbers_inline(page: Page):
    _load(page, left=250)
    page.click("[data-pjx-toggle]")
    style = page.evaluate("document.getElementById('panel').style.cssText")
    assert "left:" in style
    assert "top:" in style
    assert "right: auto" in style


def test_the_primitive_stays_callable_standalone(page: Page):
    _load(page, left=10)
    result = page.evaluate(
        "pjx.popoverPosition({trigger:{top:0,left:0,width:10,height:10},"
        "panel:{width:20,height:20},viewport:{width:1000,height:1000},align:'start'})"
    )
    assert result == {
        "align": "start",
        "placement": "below",
        "left": 0,
        "top": 14,
        "adjusted": False,
    }
