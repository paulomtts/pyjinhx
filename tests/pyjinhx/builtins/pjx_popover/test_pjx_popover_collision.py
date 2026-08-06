"""Opening a popover near a viewport edge flips or clamps it back on-screen.

The flip/clamp matrix that test_pjx_popover_wiring.py deferred: real trigger
positions in a real viewport, asserted on the panel's rendered box rather than
on synthetic rects fed to the primitive (that is
test_pjx_popover_position.py's job).
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
<div id="root" class="pjx-popover" data-pjx-popover style="position: absolute; left: LEFTpx; top: TOPpx;">
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


def _open_at(
    page: Page, *, viewport: tuple[int, int], left: int, top: int
) -> dict[str, float]:
    """Place the trigger, open the popover, return the panel's rendered box."""
    width, height = viewport
    page.set_viewport_size({"width": width, "height": height})
    page.set_content(PAGE.replace("LEFT", str(left)).replace("TOP", str(top)))
    page.add_script_tag(content=CONTROLLER.read_text())
    page.click("[data-pjx-toggle]")
    return page.evaluate(
        "() => { const r = document.getElementById('panel').getBoundingClientRect();"
        " return {left: r.left, top: r.top, right: r.right, bottom: r.bottom}; }"
    )


def test_right_edge_trigger_flips_to_end_alignment(page: Page):
    # Trigger at x=250 in a 400px viewport: a 200px panel aligned to the
    # trigger's left edge would end at 450, so it flips to end alignment.
    box = _open_at(page, viewport=(400, 400), left=250, top=10)
    style = page.evaluate("document.getElementById('panel').style.cssText")
    assert "right: auto" in style
    assert "left: -100px" in style
    assert box["right"] == 350
    assert box["right"] <= 400


def test_bottom_edge_trigger_flips_above(page: Page):
    # Trigger at y=300 in a 400px viewport: 30px of trigger plus a 4px gap
    # plus a 150px panel reaches 484, so the panel goes above instead.
    box = _open_at(page, viewport=(400, 400), left=10, top=300)
    assert page.evaluate("document.getElementById('panel').style.top") == "-154px"
    assert box["top"] == 146
    assert box["bottom"] == 296  # trigger top (300) minus the 4px gap
    assert box["top"] >= 0


def test_a_viewport_too_tight_for_the_panel_clamps_within_bounds(page: Page):
    # 260x220 viewport: the 200x150 panel fits the viewport but not at the
    # trigger, and neither flip helps (end alignment lands at x=-20, above
    # lands at y=-54), so only the padded clamp keeps it fully on-screen.
    box = _open_at(page, viewport=(260, 220), left=80, top=100)
    assert box["left"] >= 0
    assert box["top"] >= 0
    assert box["right"] <= 260
    assert box["bottom"] <= 220
    assert (box["left"], box["top"]) == (52, 62)  # clamped to the 8px inset


def test_trigger_with_room_on_all_sides_gets_no_inline_styles(page: Page):
    # Centered in a large viewport with room on every side: the primitive
    # lands on the CSS default, so the controller writes nothing and the
    # rendered markup stays identical to a popover that never flips.
    _open_at(page, viewport=(1000, 800), left=450, top=385)
    assert (
        page.evaluate("document.getElementById('panel').getAttribute('style')")
        is None
    )
