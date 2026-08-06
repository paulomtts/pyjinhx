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
