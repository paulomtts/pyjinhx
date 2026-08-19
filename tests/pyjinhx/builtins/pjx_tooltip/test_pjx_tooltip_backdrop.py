"""The dimming backdrop opens and closes on the tip's own show/hide lifecycle.

Real hover and focus events against the shipped controller: the server-rendered
markup lives in test_pjx_tooltip.py, the placement math in
test_pjx_tooltip_collision.py, and this file owns only the backdrop's visibility.
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

MARKUP = """
<style>
  body { margin: 0; }
  .pjx-tooltip__tip { position: fixed; width: 120px; height: 40px; }
  .pjx-tooltip__tip[hidden] { display: block; visibility: hidden; }
  .pjx-tooltip__backdrop { position: fixed; inset: 0; pointer-events: none; }
  .pjx-tooltip__backdrop[hidden] { display: block; visibility: hidden; }
</style>
<span id="root" class="pjx-tooltip" data-pjx-tooltip-placement="top"
      style="position: absolute; left: 300px; top: 300px;">
  <span class="pjx-tooltip__backdrop" data-pjx-tooltip-backdrop hidden></span>
  <button class="pjx-tooltip__trigger">t</button>
  <span id="tip" class="pjx-tooltip__tip" hidden>tip</span>
</span>
<span id="plain" class="pjx-tooltip" data-pjx-tooltip-placement="top"
      style="position: absolute; left: 40px; top: 40px;">
  <button id="plain-trigger" class="pjx-tooltip__trigger">p</button>
  <span id="plain-tip" class="pjx-tooltip__tip" hidden>plain</span>
</span>
"""

VISIBLE = (
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


@pytest.fixture
def wired(page: Page) -> Page:
    page.set_viewport_size({"width": 800, "height": 600})
    page.set_content(MARKUP)
    page.add_script_tag(content=CONTROLLER.read_text())
    return page


def test_backdrop_opens_with_the_tip_on_hover(wired: Page):
    wired.hover("#root .pjx-tooltip__trigger")
    wired.wait_for_selector(".pjx-tooltip__backdrop--visible")
    assert wired.evaluate(VISIBLE) == {"shown": True, "hidden": False}


def test_backdrop_closes_with_the_tip_on_mouse_out(wired: Page):
    wired.hover("#root .pjx-tooltip__trigger")
    wired.wait_for_selector(".pjx-tooltip__backdrop--visible")
    wired.mouse.move(700, 550)
    wired.wait_for_selector(".pjx-tooltip__tip--visible", state="detached")
    assert wired.evaluate(VISIBLE) == {"shown": False, "hidden": True}


def test_backdrop_opens_and_closes_with_keyboard_focus(wired: Page):
    wired.focus("#root .pjx-tooltip__trigger")
    wired.wait_for_selector(".pjx-tooltip__backdrop--visible")
    assert wired.evaluate(VISIBLE)["shown"] is True

    wired.focus("#plain-trigger")
    wired.wait_for_selector(".pjx-tooltip__backdrop--visible", state="detached")
    assert wired.evaluate(VISIBLE) == {"shown": False, "hidden": True}


def test_moving_to_a_backdropless_tooltip_drops_the_open_backdrop(wired: Page):
    """Switching tooltips closes the previous one's backdrop, not just its tip."""
    wired.hover("#root .pjx-tooltip__trigger")
    wired.wait_for_selector(".pjx-tooltip__backdrop--visible")
    wired.hover("#plain-trigger")
    wired.wait_for_selector("#plain-tip.pjx-tooltip__tip--visible")
    assert wired.evaluate(VISIBLE) == {"shown": False, "hidden": True}
