"""PJXSelect — required/invalid affordance (#1065).

The native ``<select>`` stays ``hidden`` throughout, so the browser has
nothing visible to anchor its own validation bubble to. Instead the JS
listens for the native element's ``invalid`` event (fired on a failed
constraint check, e.g. ``form.reportValidity()``), mirrors the failure onto
the visible trigger (``aria-invalid`` + a ``pjx-select--invalid`` class) and
focuses it, then clears both as soon as a real selection is made.
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

# Mirrors what pjx_select.pjx renders for required=True with no matching
# value: the native <select> carries `required` plus the #1066 synthetic
# empty placeholder option, so its .value is honestly "" and constraint
# validation actually fails.
REQUIRED_UNSELECTED = """
<form id="form">
  <div id="root" class="pjx-select" data-pjx-select data-name="fruit">
    <select name="fruit" hidden required>
      <option value="" selected disabled hidden></option>
      <option value="a">Apple</option>
      <option value="b">Banana</option>
    </select>
    <button type="button" class="pjx-select__trigger" data-pjx-select-trigger
            aria-haspopup="listbox" aria-expanded="false" aria-required="true">
      <span class="pjx-select__label">Select…</span>
    </button>
    <div id="panel" class="pjx-select__panel" data-pjx-select-panel hidden role="listbox">
      <button type="button" class="pjx-select__option" data-pjx-select-option
              data-value="a" aria-selected="false" role="option">Apple</button>
      <button type="button" class="pjx-select__option" data-pjx-select-option
              data-value="b" aria-selected="false" role="option">Banana</button>
    </div>
  </div>
</form>
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


def _trigger_invalid(page: Page) -> None:
    page.evaluate("document.querySelector('form').reportValidity()")


def test_failed_validation_marks_the_trigger_invalid(page: Page):
    _load(page, REQUIRED_UNSELECTED)
    _trigger_invalid(page)
    trigger = page.query_selector("[data-pjx-select-trigger]")
    assert trigger.get_attribute("aria-invalid") == "true"
    assert "pjx-select--invalid" in trigger.get_attribute("class")


def test_failed_validation_focuses_the_trigger(page: Page):
    _load(page, REQUIRED_UNSELECTED)
    _trigger_invalid(page)
    assert page.evaluate(
        "document.activeElement === document.querySelector('[data-pjx-select-trigger]')"
    )


def test_selecting_an_option_clears_the_invalid_state(page: Page):
    _load(page, REQUIRED_UNSELECTED)
    _trigger_invalid(page)
    page.click("[data-pjx-select-trigger]")
    page.click('[data-pjx-select-option][data-value="a"]')
    trigger = page.query_selector("[data-pjx-select-trigger]")
    assert trigger.get_attribute("aria-invalid") is None
    assert "pjx-select--invalid" not in (trigger.get_attribute("class") or "")


def test_valid_select_never_gets_marked_invalid(page: Page):
    _load(page, REQUIRED_UNSELECTED)
    page.click("[data-pjx-select-trigger]")
    page.click('[data-pjx-select-option][data-value="b"]')
    # A subsequent reportValidity() (e.g. a second submit attempt) must stay
    # quiet once a real value is present — nothing should re-flag it.
    _trigger_invalid(page)
    trigger = page.query_selector("[data-pjx-select-trigger]")
    assert trigger.get_attribute("aria-invalid") is None
