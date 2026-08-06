"""Opening a PJXSelect near a viewport edge flips or clamps its panel on-screen.

pjx_select.js carries its own byte-identical copy of the popover positioning
primitive rather than importing pjx_popover_position.js, so the popover's
collision suite does not cover this path: these tests drive Select's own markup
(native ``<select>`` fallback, ``data-pjx-select`` root, ``data-pjx-select-panel``)
and assert on the panel's rendered box.
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

# Mirrors the shape pjx_select.pjx renders and the geometry pjx_select.css
# gives it (absolute panel, 4px gap, start alignment), with the panel's box
# pinned to fixed pixels so the expected coordinates are computable.
STYLE = """
<style>
  body { margin: 0; }
  .pjx-select { position: relative; display: inline-block; }
  .pjx-select__trigger { width: 100px; height: 30px; }
  .pjx-select__panel { position: absolute; top: calc(100% + 4px); left: 0;
                       width: 200px; height: 150px; }
  .pjx-select__panel[hidden] { display: none !important; }
</style>
"""

SINGLE = """
<div id="root" class="pjx-select" data-pjx-select data-name="fruit"
     style="position: absolute; left: LEFTpx; top: TOPpx;">
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
"""

MULTIPLE = """
<div id="root" class="pjx-select" data-pjx-select data-name="fruit" data-multiple
     data-placeholder="Select…" style="position: absolute; left: LEFTpx; top: TOPpx;">
  <select name="fruit" multiple hidden>
    <option value="a" selected>Apple</option>
    <option value="b" selected>Banana</option>
  </select>
  <button type="button" class="pjx-select__trigger" data-pjx-select-trigger
          aria-haspopup="listbox" aria-expanded="true">
    <span class="pjx-select__label"><span class="pjx-select__chips"
      ><span class="pjx-chip-input__chip"><span class="pjx-chip-input__label">Apple</span></span
      ><span class="pjx-chip-input__chip"><span class="pjx-chip-input__label">Banana</span></span
    ></span></span>
  </button>
  <div id="panel" class="pjx-select__panel" data-pjx-select-panel hidden role="listbox">
    <button type="button" class="pjx-select__option" data-pjx-select-option
            data-value="a" aria-selected="true" role="option">
      <input type="checkbox" checked class="pjx-select__checkbox" tabindex="-1" aria-hidden="true">Apple</button>
    <button type="button" class="pjx-select__option" data-pjx-select-option
            data-value="b" aria-selected="true" role="option">
      <input type="checkbox" checked class="pjx-select__checkbox" tabindex="-1" aria-hidden="true">Banana</button>
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


def _open_at(
    page: Page,
    *,
    viewport: tuple[int, int],
    left: int,
    top: int,
    markup: str = SINGLE,
) -> dict[str, float]:
    """Place the trigger, open the select, return the panel's rendered box."""
    width, height = viewport
    page.set_viewport_size({"width": width, "height": height})
    page.set_content(STYLE + markup.replace("LEFT", str(left)).replace("TOP", str(top)))
    page.add_script_tag(content=CONTROLLER.read_text())
    page.click("[data-pjx-select-trigger]")
    return page.evaluate(
        "() => { const r = document.getElementById('panel').getBoundingClientRect();"
        " return {left: r.left, top: r.top, right: r.right, bottom: r.bottom}; }"
    )


def test_panel_flips_or_clamps_at_right_edge(page: Page):
    # Trigger at x=250 in a 400px viewport: a 200px panel aligned to the
    # trigger's left edge would end at 450, so it flips to end alignment.
    box = _open_at(page, viewport=(400, 400), left=250, top=10)
    assert page.evaluate("document.getElementById('panel').style.left") == "-100px"
    assert box["left"] == 150
    assert box["right"] == 350


def test_panel_flips_above_at_bottom_edge(page: Page):
    # Trigger at y=300 in a 400px viewport: 30px of trigger plus a 4px gap plus
    # a 150px panel reaches 484, so the panel goes above the trigger instead.
    box = _open_at(page, viewport=(400, 400), left=10, top=300)
    assert page.evaluate("document.getElementById('panel').style.top") == "-154px"
    assert box["top"] == 146
    assert box["bottom"] == 296
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
    # With room on every side the primitive lands on the CSS default, so the
    # controller writes nothing and the panel keeps the stylesheet's geometry.
    _open_at(page, viewport=(1000, 800), left=450, top=385)
    assert (
        page.evaluate("document.getElementById('panel').getAttribute('style')") is None
    )


def test_panel_position_unaffected_in_multiple_mode(page: Page):
    # The chip trigger is the same fixed box as the single-select one, so the
    # multi-select panel flips to exactly the same place at the right edge.
    box = _open_at(page, viewport=(400, 400), left=250, top=10, markup=MULTIPLE)
    assert box["right"] == 350
    assert box["right"] <= 400
