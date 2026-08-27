"""A tooltip nested inside an open `<dialog>` still shows its tip.

Real Chromium, a real `showModal()` dialog, the real shipped controller: the
server-rendered markup lives in test_pjx_tooltip.py, the clamp/flip math in
test_pjx_tooltip_collision.py and the backdrop's lifecycle in
test_pjx_tooltip_backdrop.py — this file owns only what changes when the
trigger's ancestor chain passes through a dialog.
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

# The tip declarations mirror pjx_tooltip.css so the computed-style
# assertions below exercise the same visibility/opacity transition the shipped
# stylesheet ships, without pulling the whole token-dependent file in.
STYLE = """
<style>
  body { margin: 0; }
  dialog#host { margin: 0; padding: 0; border: none;
                width: 400px; height: 300px; overflow: clip;
                transform: translateX(0); }
  .pjx-tooltip { position: absolute; left: 120px; top: 140px; }
  .pjx-tooltip__trigger { display: block; width: 40px; height: 30px; }
  .pjx-tooltip__tip { position: fixed; left: 0; top: 0; box-sizing: border-box;
                      width: 120px; height: 40px;
                      visibility: hidden; opacity: 0;
                      transition: opacity 0.12s ease, visibility 0.12s; }
  .pjx-tooltip__tip.pjx-tooltip__tip--visible { visibility: visible; opacity: 1; }
  .pjx-tooltip__tip[hidden] { display: block; }
</style>
"""

DIALOG = (
    STYLE
    + """
<dialog id="host">
  <div id="root" class="pjx-tooltip" data-pjx-tooltip-placement="top">
    <button class="pjx-tooltip__trigger">t</button>
    <div id="tip" class="pjx-tooltip__tip" hidden>tip</div>
  </div>
</dialog>
"""
)

COMPUTED = (
    "() => { const cs = getComputedStyle(document.getElementById('tip'));"
    " return {visibility: cs.visibility, opacity: cs.opacity}; }"
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


def _open_modal(page: Page, markup: str) -> None:
    """Load the markup, wire the real controller, open the dialog modally."""
    page.set_viewport_size({"width": 800, "height": 600})
    page.set_content(markup)
    page.add_script_tag(content=CONTROLLER.read_text())
    page.evaluate("document.getElementById('host').showModal()")
    # showModal() autofocuses the dialog's first focusable descendant, which in
    # every fixture here is the tooltip trigger itself: that autofocus fires
    # 'focusin' and calls show() before the test's own hover/focus ever runs,
    # racing the test's explicit trigger of show() and making outcomes
    # order-dependent (confirmed empirically: without this, the forced-throw
    # regression test below passes nondeterministically on unfixed code).
    # Blur it and let hide()'s timers settle so the explicit action below is
    # what actually exercises show().
    page.evaluate("document.activeElement && document.activeElement.blur()")
    page.wait_for_timeout(150)


def test_hovering_a_trigger_inside_a_modal_dialog_shows_the_tip(page: Page):
    _open_modal(page, DIALOG)
    page.hover(".pjx-tooltip__trigger")
    page.wait_for_selector(".pjx-tooltip__tip--visible")
    assert page.evaluate(
        "document.getElementById('tip')"
        ".classList.contains('pjx-tooltip__tip--visible')"
    )


def test_the_tip_inside_a_modal_dialog_actually_paints(page: Page):
    # The class alone proves nothing: pjx_tooltip.css keeps the tip at
    # visibility: hidden; opacity: 0 until the visible class wins, so assert
    # the settled computed style rather than the class a second time.
    _open_modal(page, DIALOG)
    page.hover(".pjx-tooltip__trigger")
    page.wait_for_selector(".pjx-tooltip__tip--visible")
    page.wait_for_timeout(200)
    assert page.evaluate(COMPUTED) == {"visibility": "visible", "opacity": "1"}


def test_focusing_a_trigger_inside_a_modal_dialog_shows_the_tip(page: Page):
    _open_modal(page, DIALOG)
    page.focus(".pjx-tooltip__trigger")
    page.wait_for_selector(".pjx-tooltip__tip--visible")
    assert page.evaluate(
        "document.getElementById('tip')"
        ".classList.contains('pjx-tooltip__tip--visible')"
    )


def test_a_measurement_failure_degrades_position_not_visibility(page: Page):
    # place() runs in the same rAF callback that adds the visible class, and a
    # throw in a rAF callback is swallowed by the browser: whatever a dialog
    # does to measurement, it must never be able to leave the tip hidden with
    # its hidden attribute already removed.
    _open_modal(page, DIALOG)
    page.evaluate(
        "() => { const t = document.querySelector('.pjx-tooltip__trigger');"
        " t.getBoundingClientRect = () => { throw new Error('measurement'); }; }"
    )
    page.evaluate(
        "() => document.querySelector('.pjx-tooltip__trigger')"
        ".dispatchEvent(new MouseEvent('mouseover', {bubbles: true}))"
    )
    page.wait_for_selector(".pjx-tooltip__tip--visible")
    assert page.evaluate("!document.getElementById('tip').hasAttribute('hidden')")
