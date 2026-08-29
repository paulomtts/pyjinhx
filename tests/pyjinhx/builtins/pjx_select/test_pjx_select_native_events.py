"""PJXSelect — syncNative() bridges to real ``change``/``input`` events.

Setting an ``<option>``'s ``.selected`` IDL property, unlike a real user pick,
fires nothing — so anything downstream that listens for ``change``/``input``
"from:select" (htmx's ``hx-trigger``, a vanilla listener) needs the hidden
native ``<select>`` to dispatch those events itself once its options are
resynced.
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
  .pjx-select { position: relative; display: inline-block; }
  .pjx-select__panel[hidden] { display: none !important; }
</style>
"""

SINGLE = """
<div id="root" class="pjx-select" data-pjx-select data-name="fruit">
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
     data-placeholder="Select…">
  <select name="fruit" multiple hidden>
    <option value="a">Apple</option>
    <option value="b">Banana</option>
  </select>
  <button type="button" class="pjx-select__trigger" data-pjx-select-trigger
          aria-haspopup="listbox" aria-expanded="false">
    <span class="pjx-select__label">Select…</span>
  </button>
  <div id="panel" class="pjx-select__panel" data-pjx-select-panel hidden role="listbox">
    <button type="button" class="pjx-select__option" data-pjx-select-option
            data-value="a" aria-selected="false" role="option">
      <input type="checkbox" class="pjx-select__checkbox" tabindex="-1" aria-hidden="true">Apple</button>
    <button type="button" class="pjx-select__option" data-pjx-select-option
            data-value="b" aria-selected="false" role="option">
      <input type="checkbox" class="pjx-select__checkbox" tabindex="-1" aria-hidden="true">Banana</button>
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


def _load(page: Page, markup: str) -> None:
    page.set_content(STYLE + markup)
    page.add_script_tag(content=CONTROLLER.read_text())
    page.evaluate(
        """
        () => {
            window.__events = [];
            const native = document.querySelector('select');
            native.addEventListener('input', (e) => window.__events.push('input'));
            native.addEventListener('change', (e) => window.__events.push('change'));
        }
        """
    )


def test_selecting_an_option_dispatches_change_and_input_on_the_native_select(
    page: Page,
):
    _load(page, SINGLE)
    page.click("[data-pjx-select-trigger]")
    page.click('[data-pjx-select-option][data-value="b"]')
    assert page.evaluate("window.__events") == ["input", "change"]
    assert page.evaluate("document.querySelector('select').value") == "b"


def test_toggling_a_checkbox_in_multiple_mode_dispatches_the_events_too(page: Page):
    _load(page, MULTIPLE)
    page.click("[data-pjx-select-trigger]")
    page.click('[data-pjx-select-option][data-value="a"]')
    assert page.evaluate("window.__events") == ["input", "change"]


def test_each_pick_fires_its_own_pair_of_events(page: Page):
    _load(page, MULTIPLE)
    page.click("[data-pjx-select-trigger]")
    page.click('[data-pjx-select-option][data-value="a"]')
    page.click('[data-pjx-select-option][data-value="b"]')
    assert page.evaluate("window.__events") == ["input", "change", "input", "change"]
