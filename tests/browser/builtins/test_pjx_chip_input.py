"""PJXChipInput — v0.x field/markup parity on the v2 engine.

Port of tests/unit/test_chip_input.py. v0.x's golden snapshot
(tests/unit/golden/chip_input.html) does not carry over: v2 builtins assert on
rendered substrings, like every sibling port. The template composes no child
component tags — only div/span/input/button — so there is no child-tag render
coverage here and no registry fixture, unlike PJXButton's region-loader leg.
"""

from pyjinhx.builtins.pjx_chip_input import PJXChipInput
from pyjinhx.client import read_pjx_theme_css

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
