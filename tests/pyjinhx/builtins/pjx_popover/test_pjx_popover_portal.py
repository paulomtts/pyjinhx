"""PJXPopover(portal=True) reparents the panel to document.body while open.

Mirrors tooltip's portal mechanism (tests/pyjinhx/builtins/pjx_tooltip/
test_pjx_tooltip_collision.py) but for popover's click-toggle lifecycle:
rootOf()/triggerFor()/panelForToggle() must keep resolving correctly once
the panel alone has moved, and the app-level hazards described in #1053
(scroll-close, an outside-click false positive from the panel itself, a
host removed while portalled) must be handled generically here instead.
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

# Bare data-pjx-toggle (no explicit panel id), the shape PJXPopoverTrigger
# renders: panelForToggle() must resolve it via root -> panel, which is the
# lookup portal breaks if the panel is simply moved without bookkeeping.
PAGE = """
<style>
  body { margin: 0; }
  .pjx-popover { position: relative; display: inline-block; }
  .pjx-popover__panel { position: absolute; top: calc(100% + 4px); left: 0;
                        width: 200px; height: 150px; }
  .pjx-popover__panel[hidden] { display: none !important; }
</style>
<div id="host">
  <div id="root" class="pjx-popover" data-pjx-popover data-pjx-popover-portal
       style="position: absolute; left: 10px; top: 10px;">
    <button data-pjx-toggle style="width: 100px; height: 30px;">t</button>
    <div id="panel" class="pjx-popover__panel" data-pjx-popover-panel hidden>
      <div id="panel-inner" style="height: 400px; overflow-y: auto;">
        <div style="height: 1000px;">p</div>
      </div>
    </div>
  </div>
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


def _load(page: Page) -> None:
    page.set_viewport_size({"width": 400, "height": 400})
    page.set_content(PAGE)
    page.add_script_tag(content=CONTROLLER.read_text())


def _panel_parent_id(page: Page) -> str | None:
    return page.evaluate(
        "document.getElementById('panel').parentElement"
        " && document.getElementById('panel').parentElement.id"
    )


def test_portal_reparents_the_panel_to_document_body_on_open(page: Page):
    _load(page)
    page.click("[data-pjx-toggle]")
    assert page.evaluate(
        "document.getElementById('panel').parentElement === document.body"
    )


def test_portal_restores_the_panel_to_its_original_parent_on_close(page: Page):
    _load(page)
    page.click("[data-pjx-toggle]")
    page.click("[data-pjx-toggle]")  # close
    assert _panel_parent_id(page) == "root"


def test_bare_toggle_still_finds_the_panel_after_a_portal_round_trip(page: Page):
    # Regression guard: panelForToggle() walks root.querySelector(), which
    # can no longer see a panel moved out to document.body. A second toggle
    # click must still reopen it rather than silently doing nothing.
    _load(page)
    page.click("[data-pjx-toggle]")  # open, portals
    page.click("[data-pjx-toggle]")  # close, restores
    page.click("[data-pjx-toggle]")  # reopen
    assert page.evaluate("document.getElementById('panel').hidden") is False
    assert page.evaluate(
        "document.getElementById('panel').parentElement === document.body"
    )


def test_outside_click_closes_and_restores_a_portalled_popover(page: Page):
    _load(page)
    page.click("[data-pjx-toggle]")
    page.mouse.click(390, 390)  # far corner, outside root and outside panel
    assert page.evaluate("document.getElementById('panel').hidden") is True
    assert _panel_parent_id(page) == "root"


def test_click_inside_the_portalled_panel_does_not_close_it(page: Page):
    # Once portalled the panel is no longer a DOM descendant of root, so the
    # naive `rootOf(panel).contains(click target)` outside-check would see
    # this click as outside and close the popover on itself.
    _load(page)
    page.click("[data-pjx-toggle]")
    page.click("#panel-inner")
    assert page.evaluate("document.getElementById('panel').hidden") is False


def test_escape_closes_and_restores_a_portalled_popover(page: Page):
    _load(page)
    page.click("[data-pjx-toggle]")
    page.keyboard.press("Escape")
    assert page.evaluate("document.getElementById('panel').hidden") is True
    assert _panel_parent_id(page) == "root"


def test_scroll_closes_an_open_portalled_popover(page: Page):
    # A portalled trigger's row can scroll out from under a panel fixed at
    # its old measured position; there is no reposition-on-scroll for
    # popovers (unlike tooltip), so the fix is to close instead.
    _load(page)
    page.click("[data-pjx-toggle]")
    page.evaluate("window.scrollTo(0, 1)")
    page.wait_for_timeout(50)
    assert page.evaluate("document.getElementById('panel').hidden") is True
    assert _panel_parent_id(page) == "root"


def test_scroll_inside_the_portalled_panel_does_not_close_it(page: Page):
    _load(page)
    page.click("[data-pjx-toggle]")
    page.evaluate("document.getElementById('panel-inner').scrollTop = 50")
    page.wait_for_timeout(50)
    assert page.evaluate("document.getElementById('panel').hidden") is False


def test_removing_the_host_while_portalled_drops_the_orphaned_panel_on_close(
    page: Page,
):
    _load(page)
    page.click("[data-pjx-toggle]")
    assert page.evaluate(
        "document.getElementById('panel').parentElement === document.body"
    )
    page.evaluate("document.getElementById('root').remove()")
    page.keyboard.press("Escape")
    # No parent left to restore into: the panel is dropped rather than kept
    # dangling, attached to a detached tree nobody can see or reach again.
    assert page.evaluate("document.getElementById('panel')") is None


def test_no_portal_leaves_the_panel_in_place(page: Page):
    _load(page)
    page.evaluate(
        "document.getElementById('root').removeAttribute('data-pjx-popover-portal')"
    )
    page.click("[data-pjx-toggle]")
    assert _panel_parent_id(page) == "root"
