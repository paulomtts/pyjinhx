"""PJXChipInput: the stylesheet fallbacks and dark-mode theme, and chip building, in chromium.

The field and markup checks are in tests/unit/builtins/test_pjx_chip_input.py.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

import pytest

from pyjinhx.builtins.pjx_chip_input import PJXChipInput
from pyjinhx.client import read_pjx_theme_css

if TYPE_CHECKING:
    from playwright.sync_api import Page

CHIP_CSS = PJXChipInput.__pjx_descriptor__.css_paths[0].read_text(encoding="utf-8")


CHIP_MARKUP = (
    '<div id="root" class="pjx-chip-input">'
    '<span id="chip" class="pjx-chip-input__chip">'
    '<span class="pjx-chip-input__label">tag</span>'
    '<button class="pjx-chip-input__remove" type="button">x</button></span>'
    '<input id="field" class="pjx-chip-input__field">'
    "</div>"
)


def _chip_style(page, element_id: str, prop: str) -> str:
    return page.evaluate(
        f"getComputedStyle(document.getElementById('{element_id}'))"
        f".getPropertyValue('{prop}')"
    )


def test_chip_input_defaults_use_light_fallbacks(page):
    page.set_content(
        f"<html><head><style>{CHIP_CSS}</style></head><body>{CHIP_MARKUP}</body></html>"
    )
    assert _chip_style(page, "root", "border-top-left-radius") == "8px"
    # 0.375rem stays off the spacing scale; 8px is space-2.
    assert _chip_style(page, "root", "padding-top") == "6px"
    assert _chip_style(page, "root", "padding-left") == "8px"
    assert _chip_style(page, "root", "row-gap") == "6px"
    assert _chip_style(page, "root", "background-color") == "rgb(255, 255, 255)"
    assert _chip_style(page, "chip", "background-color") == "rgb(250, 250, 250)"
    assert _chip_style(page, "chip", "color") == "rgb(24, 24, 27)"
    assert _chip_style(page, "chip", "border-top-left-radius") == "9999px"
    assert _chip_style(page, "chip", "padding-top") == "2px"
    assert _chip_style(page, "chip", "padding-left") == "8px"
    assert _chip_style(page, "chip", "column-gap") == "4px"
    assert _chip_style(page, "field", "color") == "rgb(24, 24, 27)"


def test_chip_input_follows_theme_in_dark_mode(page):
    page.emulate_media(color_scheme="light")
    page.set_content(
        # Dark on <html>: component tokens are declared on :root, so their
        # var() resolves there and a dark subtree alone would not flip them.
        f'<html data-pjx-theme="dark"><head><style>{read_pjx_theme_css()}</style>'
        f"<style>{CHIP_CSS}</style></head>"
        f"<body>{CHIP_MARKUP}</body></html>"
    )
    assert _chip_style(page, "root", "background-color") == "rgb(24, 24, 27)"
    assert _chip_style(page, "chip", "background-color") == "rgb(9, 9, 11)"
    assert _chip_style(page, "chip", "color") == "rgb(244, 244, 245)"
    assert _chip_style(page, "chip", "border-top-color") == "rgb(63, 63, 70)"
    assert _chip_style(page, "field", "color") == "rgb(244, 244, 245)"


# window.pjx.buildChip(): the chip DOM builder, exposed for reuse.
#
# An app composing its own chip-shaped UI (e.g. an async ref picker) needs the
# same markup PJXChipInput builds internally. The function is DOM-bound, so the
# tests run the real file in real chromium rather than asserting on source
# strings — same approach as test_pjx_popover_position.py.


SOURCE = (
    Path(__file__).resolve().parents[3]
    / "pyjinhx"
    / "builtins"
    / "pjx_chip_input"
    / "pjx_chip_input.js"
)


@pytest.fixture(autouse=True)
def _require_chromium(request: pytest.FixtureRequest) -> None:
    if "chip_page" not in set(request.fixturenames):
        return
    pytest.importorskip("playwright")
    browser_type: Any = request.getfixturevalue("browser_type")
    if not Path(browser_type.executable_path).exists():
        pytest.skip(
            "chromium is not installed (run: uv run playwright install chromium)"
        )


@pytest.fixture
def chip_page(page: Page) -> Page:
    page.set_content('<body><div data-pjx-chip-input data-name="tags"></div></body>')
    page.add_script_tag(content=SOURCE.read_text())
    return page


def test_returns_a_chip_with_the_expected_shape(chip_page: Page):
    outer = chip_page.evaluate(
        "pjx.buildChip(document.querySelector('[data-pjx-chip-input]'), 'red').outerHTML"
    )
    assert 'data-pjx-chip=""' in outer
    assert 'class="pjx-chip-input__chip"' in outer
    assert '<span class="pjx-chip-input__label">red</span>' in outer
    assert '<input type="hidden" name="tags" value="red">' in outer
    assert 'data-pjx-chip-remove=""' in outer
    assert 'aria-label="Remove"' in outer


def test_honours_the_roots_remove_label(chip_page: Page):
    chip_page.evaluate(
        "document.querySelector('[data-pjx-chip-input]')"
        ".setAttribute('data-remove-label', 'Delete')"
    )
    outer = chip_page.evaluate(
        "pjx.buildChip(document.querySelector('[data-pjx-chip-input]'), 'x').outerHTML"
    )
    assert 'aria-label="Delete"' in outer


def test_appending_it_produces_a_working_chip_in_the_dom(chip_page: Page):
    chip_page.evaluate(
        "document.querySelector('[data-pjx-chip-input]')"
        ".appendChild(pjx.buildChip(document.querySelector('[data-pjx-chip-input]'), 'blue'))"
    )
    assert chip_page.query_selector("[data-pjx-chip]") is not None
    assert (
        chip_page.eval_on_selector('input[type="hidden"]', "el => el.value") == "blue"
    )
