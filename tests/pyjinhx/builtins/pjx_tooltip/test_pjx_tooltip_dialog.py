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

CLIPPED = (
    STYLE
    + """
<dialog id="host">
  <div id="box" style="position: absolute; left: 0; top: 0;
       width: 200px; height: 200px; overflow: hidden;">
    <div id="root" class="pjx-tooltip" data-pjx-tooltip-placement="top">
      <button class="pjx-tooltip__trigger">t</button>
      <div id="tip" class="pjx-tooltip__tip" hidden>tip</div>
    </div>
  </div>
</dialog>
"""
)

WITH_BACKDROP = (
    STYLE
    + """
<style>
  .pjx-tooltip__backdrop { position: fixed; inset: 0; pointer-events: none; }
  .pjx-tooltip__backdrop[hidden] { display: block; visibility: hidden; }
</style>
<dialog id="host">
  <div id="root" class="pjx-tooltip" data-pjx-tooltip-placement="top">
    <span class="pjx-tooltip__backdrop" data-pjx-tooltip-backdrop hidden></span>
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

RECT = (
    "() => { const r = document.getElementById('tip').getBoundingClientRect();"
    " return {left: r.left, top: r.top, right: r.right, bottom: r.bottom}; }"
)

BACKDROP = (
    "() => { const b = document.querySelector('.pjx-tooltip__backdrop');"
    " return {shown: b.classList.contains('pjx-tooltip__backdrop--visible'),"
    " hidden: b.hasAttribute('hidden')}; }"
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
        "document.getElementById('tip').classList.contains('pjx-tooltip__tip--visible')"
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
        "document.getElementById('tip').classList.contains('pjx-tooltip__tip--visible')"
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


def test_a_clipping_box_inside_the_dialog_still_bounds_the_tip(page: Page):
    # The drawer clips its own box (pjx_drawer.css), so the dialog case has to
    # keep honouring a clipping ancestor rather than escaping to the viewport:
    # the trigger sits at 120..160 x 140..170 inside a 200x200 clip box, and a
    # 120px tip centred on it would run to x=200 exactly at the box's edge.
    _open_modal(page, CLIPPED)
    page.hover(".pjx-tooltip__trigger")
    page.wait_for_selector(".pjx-tooltip__tip--visible")
    box = page.evaluate(RECT)
    assert box["left"] == 72  # box right (200) - tip (120) - padding (8)
    assert box["top"] == 94  # trigger top (140) - tip (40) - gap (6)
    assert box["right"] <= 200
    assert box["bottom"] <= 200


def test_a_non_modal_open_dialog_behaves_the_same(page: Page):
    # Nothing here may depend on the top layer: a plain `open` dialog is not in
    # it, and must show the tip exactly as showModal() does.
    page.set_viewport_size({"width": 800, "height": 600})
    page.set_content(DIALOG)
    page.add_script_tag(content=CONTROLLER.read_text())
    page.evaluate("document.getElementById('host').setAttribute('open', '')")
    page.hover(".pjx-tooltip__trigger")
    page.wait_for_selector(".pjx-tooltip__tip--visible")
    assert page.evaluate(
        "document.getElementById('tip').classList.contains('pjx-tooltip__tip--visible')"
    )


def test_the_tip_hides_and_reshows_inside_the_dialog(page: Page):
    _open_modal(page, DIALOG)
    page.hover(".pjx-tooltip__trigger")
    page.wait_for_selector(".pjx-tooltip__tip--visible")

    # Still inside the dialog (0..400 x 0..300), clear of the root — so the
    # mouseout is a real in-dialog move, not a jump onto the inert backdrop.
    page.mouse.move(380, 20)
    page.wait_for_selector(".pjx-tooltip__tip--visible", state="detached")
    assert page.evaluate("document.getElementById('tip').hasAttribute('hidden')")

    page.hover(".pjx-tooltip__trigger")
    page.wait_for_selector(".pjx-tooltip__tip--visible")
    assert page.evaluate("!document.getElementById('tip').hasAttribute('hidden')")


def test_closing_the_dialog_mid_show_does_not_block_the_next_tooltip(page: Page):
    # show() parks the open tip in activeTip/activeRoot/activeBackdrop. Closing
    # the dialog out from under a visible tip must not strand that state, or the
    # next tooltip on the page would be shown against a detached predecessor.
    page.set_viewport_size({"width": 800, "height": 600})
    page.set_content(
        DIALOG
        + """
<div id="outside" class="pjx-tooltip" data-pjx-tooltip-placement="top"
     style="left: 500px; top: 400px;">
  <button id="outside-trigger" class="pjx-tooltip__trigger">o</button>
  <div id="outside-tip" class="pjx-tooltip__tip" hidden>outside</div>
</div>
"""
    )
    page.add_script_tag(content=CONTROLLER.read_text())
    page.evaluate("document.getElementById('host').showModal()")
    page.hover("#root .pjx-tooltip__trigger")
    page.wait_for_selector("#tip.pjx-tooltip__tip--visible")

    page.evaluate("document.getElementById('host').close()")
    page.hover("#outside-trigger")
    page.wait_for_selector("#outside-tip.pjx-tooltip__tip--visible")
    assert page.evaluate(
        "!document.getElementById('outside-tip').hasAttribute('hidden')"
    )


def test_the_backdrop_opens_and_closes_with_the_tip_inside_the_dialog(page: Page):
    # The tip's visible class and the backdrop's are added in the same rAF
    # callback, so the dialog fix has to carry both or neither.
    _open_modal(page, WITH_BACKDROP)
    page.hover(".pjx-tooltip__trigger")
    page.wait_for_selector(".pjx-tooltip__backdrop--visible")
    assert page.evaluate(BACKDROP) == {"shown": True, "hidden": False}

    page.mouse.move(380, 20)
    page.wait_for_selector(".pjx-tooltip__tip--visible", state="detached")
    assert page.evaluate(BACKDROP) == {"shown": False, "hidden": True}
