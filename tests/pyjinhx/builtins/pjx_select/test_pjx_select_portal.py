"""PJXSelect — ``portal`` reparents the whole root to escape a clipping ancestor.

Unlike PJXTooltip's tip (a sibling of its trigger), the select's panel is a
*child* of its root, so moving the whole root — not just the panel — keeps
the panel's absolute positioning relative to it unchanged and every
``.closest('[data-pjx-select]')`` lookup resolving wherever it lands.
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
    / "pjx_select"
    / "pjx_select.js"
)

STYLE = """
<style>
  body { margin: 0; }
  .pjx-select { position: relative; display: inline-block; }
  .pjx-select__panel { position: absolute; top: calc(100% + 4px); left: 0; }
  .pjx-select__panel[hidden] { display: none !important; }
</style>
"""

# A narrow, clipping ancestor around the select: the #1054 scenario (a drawer,
# a scrollable list, a modal) that clips an unportalled panel.
BOXED = """
<div id="box" style="position: relative; width: 60px; height: 60px; overflow: hidden;">
  <div id="root" class="pjx-select" data-pjx-select data-name="fruit" PORTAL>
    <select name="fruit" hidden>
      <option value="a">Apple</option>
      <option value="b">Banana</option>
    </select>
    <button type="button" class="pjx-select__trigger" data-pjx-select-trigger
            aria-haspopup="listbox" aria-expanded="false">
      <span class="pjx-select__label">Select…</span>
    </button>
    <div id="panel" class="pjx-select__panel" data-pjx-select-panel hidden role="listbox">
      <button type="button" class="pjx-select__option" data-pjx-select-option
              data-value="a" aria-selected="false" role="option">Apple</button>
      <button type="button" class="pjx-select__option" data-pjx-select-option
              data-value="b" aria-selected="false" role="option">Banana</button>
    </div>
  </div>
</div>
"""

PORTAL = BOXED.replace("PORTAL", "data-pjx-select-portal")
NO_PORTAL = BOXED.replace(" PORTAL", "")


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


def _load(page: Page, markup: str) -> None:
    page.set_content(STYLE + markup)
    page.add_script_tag(content=CONTROLLER.read_text())


def test_without_portal_the_root_stays_put_while_open(page: Page):
    _load(page, NO_PORTAL)
    page.click("[data-pjx-select-trigger]")
    assert page.evaluate(
        "document.getElementById('root').parentElement === document.getElementById('box')"
    )


def test_portal_reparents_the_whole_root_to_document_body_while_open(page: Page):
    _load(page, PORTAL)
    page.click("[data-pjx-select-trigger]")
    assert page.evaluate(
        "document.getElementById('root').parentElement === document.body"
    )


def test_portal_restores_the_root_to_its_original_parent_on_close(page: Page):
    _load(page, PORTAL)
    page.click("[data-pjx-select-trigger]")
    page.click("body")  # clicking outside closes the select
    assert page.evaluate(
        "document.getElementById('root').parentElement === document.getElementById('box')"
    )


def test_portal_keeps_the_trigger_visually_in_place(page: Page):
    _load(page, PORTAL)
    before = page.evaluate(
        "document.querySelector('[data-pjx-select-trigger]').getBoundingClientRect().toJSON()"
    )
    page.click("[data-pjx-select-trigger]")
    after = page.evaluate(
        "document.querySelector('[data-pjx-select-trigger]').getBoundingClientRect().toJSON()"
    )
    assert after["left"] == before["left"]
    assert after["top"] == before["top"]


def test_clicking_an_option_still_selects_it_after_reparenting(page: Page):
    # Regression guard for the live-DOM-containment lookups (rootOf/partsOf):
    # they must still resolve correctly once the root is no longer a
    # descendant of its original parent.
    _load(page, PORTAL)
    page.click("[data-pjx-select-trigger]")
    page.click('[data-pjx-select-option][data-value="b"]')
    assert (
        page.evaluate(
            "document.querySelector('[data-value=\"b\"]').getAttribute('aria-selected')"
        )
        == "true"
    )
    assert page.evaluate("document.getElementById('panel').hidden") is True
    # And it closed back into its original parent, not stranded on body.
    assert page.evaluate(
        "document.getElementById('root').parentElement === document.getElementById('box')"
    )
