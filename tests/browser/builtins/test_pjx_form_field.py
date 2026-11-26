"""PJXFormField — v0.x field/markup parity on the v2 engine.

Port of the v0.x suite's test_form_field.py. v0.x's golden snapshot
(the v0.x suite's golden/form_field.html) does not carry over: v2 builtins assert on
rendered substrings, like every sibling port. The template composes no child
component tags, so ``content`` is exercised as a plain Slot — a string leg and
a nested-component leg — with no registry fixture, unlike PJXButton's
region-loader leg.
"""

from pyjinhx.builtins.pjx_form_field import PJXFormField
from pyjinhx.client import read_pjx_theme_css

FORM_FIELD_CSS = PJXFormField.__pjx_descriptor__.css_paths[0].read_text(
    encoding="utf-8"
)


FORM_FIELD_MARKUP = (
    '<div class="pjx-form-field">'
    '<label id="label" class="pjx-form-field__label">Name</label>'
    '<p id="help" class="pjx-form-field__help">Help</p>'
    '<p id="error" class="pjx-form-field__error">Required</p>'
    "</div>"
)


def _color(page, element_id: str) -> str:
    return page.evaluate(
        f"getComputedStyle(document.getElementById('{element_id}')).color"
    )


def test_form_field_colors_use_light_fallbacks_and_flip_in_dark(page):
    page.emulate_media(color_scheme="light")
    page.set_content(
        f"<html><head><style>{FORM_FIELD_CSS}</style></head>"
        f"<body>{FORM_FIELD_MARKUP}</body></html>"
    )
    # No theme loaded: light fallbacks.
    assert _color(page, "label") == "rgb(24, 24, 27)"
    assert _color(page, "help") == "rgb(82, 82, 91)"
    assert _color(page, "error") == "rgb(220, 38, 38)"

    page.set_content(
        # Dark on <html>: component tokens are declared on :root, so their
        # var() resolves there and a dark subtree alone would not flip them.
        f'<html data-pjx-theme="dark"><head><style>{read_pjx_theme_css()}</style>'
        f"<style>{FORM_FIELD_CSS}</style></head>"
        f"<body>{FORM_FIELD_MARKUP}</body></html>"
    )
    assert _color(page, "error") == "rgb(248, 113, 113)"
