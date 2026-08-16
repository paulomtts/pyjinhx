"""A tooltip inside a clipping ancestor flips and clamps against that ancestor.

Real viewport, real container rects, assertions on the tip's rendered box —
the runtime placement math that test_pjx_tooltip.py deliberately leaves alone
(that file owns the server-rendered HTML and the
`data-pjx-tooltip-placement` attribute, never the numbers `place()` writes).
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
    / "pjx_tooltip"
    / "pjx_tooltip.js"
)

STYLE = """
<style>
  body { margin: 0; }
  #box { position: absolute; left: 100px; top: 200px;
         width: 300px; height: 200px; overflow: OVERFLOW; }
  .pjx-tooltip { position: absolute; }
  .pjx-tooltip__trigger { display: block; width: 40px; height: 30px; }
  .pjx-tooltip__tip { position: fixed; left: 0; top: 0;
                      box-sizing: border-box; width: 120px; height: 40px; }
  .pjx-tooltip__tip[hidden] { display: block; visibility: hidden; }
</style>
"""

BOXED = (
    STYLE
    + """
<div id="box">
  <div id="root" class="pjx-tooltip" data-pjx-tooltip-placement="PLACEMENT"
       style="left: LEFTpx; top: TOPpx;">
    <button class="pjx-tooltip__trigger">t</button>
    <div id="tip" class="pjx-tooltip__tip" hidden>tip</div>
  </div>
  <div style="height: 700px;"></div>
</div>
"""
)

PLAIN = (
    STYLE
    + """
<div id="root" class="pjx-tooltip" data-pjx-tooltip-placement="PLACEMENT"
     style="left: LEFTpx; top: TOPpx;">
  <button class="pjx-tooltip__trigger">t</button>
  <div id="tip" class="pjx-tooltip__tip" hidden>tip</div>
</div>
"""
)

BOX = {"left": 100.0, "top": 200.0, "right": 400.0, "bottom": 400.0}

RECT = (
    "() => { const r = document.getElementById('tip').getBoundingClientRect();"
    " return {left: r.left, top: r.top, right: r.right, bottom: r.bottom}; }"
)


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


def _hover(
    page: Page,
    markup: str,
    *,
    placement: str,
    left: int,
    top: int,
    overflow: str = "hidden",
) -> dict[str, float]:
    """Position the trigger, hover it, return the tip's rendered box."""
    page.set_viewport_size({"width": 800, "height": 600})
    page.set_content(
        markup.replace("PLACEMENT", placement)
        .replace("LEFT", str(left))
        .replace("TOP", str(top))
        .replace("OVERFLOW", overflow)
    )
    page.add_script_tag(content=CONTROLLER.read_text())
    page.hover(".pjx-tooltip__trigger")
    page.wait_for_selector(".pjx-tooltip__tip--visible")
    return page.evaluate(RECT)


def test_tip_near_container_edge_stays_inside_the_container(page: Page):
    # Trigger at x=250 inside a container spanning 100..400: a 120px tip
    # centred on it would run to x=430 — inside the 800px viewport, outside
    # the container. The clamp must key off the container, not the viewport.
    box = _hover(page, BOXED, placement="top", left=250, top=100)
    assert box["right"] <= BOX["right"]
    assert box["left"] >= BOX["left"]
    assert box["left"] == 272  # container right (400) - tip (120) - padding (8)
    assert box["top"] == 254  # trigger top (300) - tip (40) - gap (6), unclamped


def test_placement_top_flips_to_bottom_inside_the_container(page: Page):
    # Trigger 10px below the container's top edge: placing above lands at
    # y=164, above the container's top (200), while below fits at 246..286.
    box = _hover(page, BOXED, placement="top", left=130, top=10)
    assert box["top"] == 246  # trigger bottom (240) + gap (6)
    assert box["bottom"] == 286
    assert box["top"] >= BOX["top"]
    assert box["bottom"] <= BOX["bottom"]


def test_placement_start_flips_to_end_inside_the_container(page: Page):
    # Trigger 10px inside the container's left edge: "start" lands at
    # x=-16, left of the container (100), while "end" fits at 156..276.
    box = _hover(page, BOXED, placement="start", left=10, top=80)
    assert box["left"] == 156  # trigger right (150) + gap (6)
    assert box["right"] == 276
    assert box["left"] >= BOX["left"]
    assert box["right"] <= BOX["right"]


def test_container_too_tight_clamps_to_padded_container_bounds(page: Page):
    # A 60px-tall container fits neither placement for a 40px tip plus gap,
    # so no flip helps and only the padded clamp keeps the tip inside.
    page.set_viewport_size({"width": 800, "height": 600})
    page.set_content(
        BOXED.replace("PLACEMENT", "top")
        .replace("LEFT", "130")
        .replace("TOP", "15")
        .replace("OVERFLOW", "hidden")
        .replace("height: 200px", "height: 60px")
    )
    page.add_script_tag(content=CONTROLLER.read_text())
    page.hover(".pjx-tooltip__trigger")
    page.wait_for_selector(".pjx-tooltip__tip--visible")
    box = page.evaluate(RECT)
    assert box["top"] == 208  # container top (200) + padding (8)
    assert box["bottom"] == 248  # still inside the container's bottom (260)
    assert box["left"] >= BOX["left"]
    assert box["right"] <= BOX["right"]


def test_no_clipping_ancestor_keeps_viewport_behavior(page: Page):
    # No overflow ancestor anywhere: the fallback bounds are the viewport, so
    # a trigger with room on every side lands on the plain default placement.
    box = _hover(page, PLAIN, placement="top", left=400, top=300)
    assert box["left"] == 360  # trigger centre (420) - half the tip (60)
    assert box["top"] == 254  # trigger top (300) - tip (40) - gap (6)
    assert page.evaluate("document.getElementById('tip').style.cssText") == (
        "left: 360px; top: 254px;"
    )


def test_scrolling_the_container_repositions_the_tip(page: Page):
    # The capturing scroll listener re-runs place() while the tip is open:
    # scrolling the trigger up toward the container's top edge must flip the
    # tip from above to below, still keyed off the container's rect.
    page.set_viewport_size({"width": 800, "height": 600})
    page.set_content(
        BOXED.replace("PLACEMENT", "top")
        .replace("LEFT", "130")
        .replace("TOP", "300")
        .replace("OVERFLOW", "auto")
    )
    page.add_script_tag(content=CONTROLLER.read_text())
    page.evaluate("document.getElementById('box').scrollTop = 160")
    page.hover(".pjx-tooltip__trigger")
    page.wait_for_selector(".pjx-tooltip__tip--visible")
    before = page.evaluate(RECT)
    assert before["top"] == 294  # trigger top (340) - tip (40) - gap (6)

    page.evaluate("document.getElementById('box').scrollTop = 280")
    page.wait_for_timeout(100)
    after = page.evaluate(RECT)
    assert after["top"] == 256  # trigger bottom (250) + gap (6), flipped below
    assert after["bottom"] <= BOX["bottom"]
