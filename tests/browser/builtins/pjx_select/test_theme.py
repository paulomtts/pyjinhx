"""PJXSelect — single-choice base: fields, markup, and no-JS form fallback.

Multi-select (#866), search (#867) and keyboard nav (#868) are separate
subtasks; nothing here anticipates their markup. The exhaustive suite is #869's.
"""

from pyjinhx.builtins.pjx_select import PJXSelect
from pyjinhx.client import read_pjx_theme_css

SELECT_CSS = PJXSelect.__pjx_descriptor__.css_paths[0].read_text(encoding="utf-8")


SELECT_MARKUP = (
    '<div class="pjx-select">'
    '<button id="trigger" class="pjx-select__trigger" type="button">'
    "<span>Pick</span><span>v</span></button>"
    '<div id="panel" class="pjx-select__panel">'
    '<div class="pjx-select__options">'
    '<button id="plain" class="pjx-select__option" aria-selected="false">A</button>'
    '<button id="picked" class="pjx-select__option" aria-selected="true">B</button>'
    "</div></div></div>"
)


CHECKBOX_MARKUP = (
    '<div class="pjx-select__option">'
    '<input id="box" class="pjx-select__checkbox" type="checkbox" checked>A</div>'
)


def _select_page(page, body: str, *, head: str = "", html_attrs: str = "") -> None:
    page.set_content(
        f"<html{html_attrs}><head>{head}<style>{SELECT_CSS}</style></head>"
        f"<body>{body}</body></html>"
    )


def _select_style(page, element_id: str, prop: str) -> str:
    return page.evaluate(
        f"getComputedStyle(document.getElementById('{element_id}'))"
        f".getPropertyValue('{prop}')"
    )


def test_select_defaults_use_light_fallbacks(page):
    _select_page(page, SELECT_MARKUP)
    assert _select_style(page, "trigger", "background-color") == "rgb(255, 255, 255)"
    assert _select_style(page, "trigger", "color") == "rgb(24, 24, 27)"
    assert _select_style(page, "trigger", "border-top-color") == "rgb(228, 228, 231)"
    assert _select_style(page, "trigger", "border-top-left-radius") == "8px"
    # 0.375rem stays off the spacing scale; 8px is space-2.
    assert _select_style(page, "trigger", "padding-top") == "6px"
    assert _select_style(page, "trigger", "padding-left") == "8px"
    assert _select_style(page, "trigger", "column-gap") == "8px"
    assert _select_style(page, "panel", "z-index") == "300"
    assert _select_style(page, "panel", "background-color") == "rgb(250, 250, 250)"
    assert _select_style(page, "picked", "background-color") == "rgb(212, 212, 216)"


def test_select_panel_layer_follows_popover_token(page):
    _select_page(
        page,
        SELECT_MARKUP,
        head="<style>:root { --pjx-z-popover: 310; }</style>",
    )
    assert _select_style(page, "panel", "z-index") == "310"
    _select_page(
        page,
        SELECT_MARKUP,
        head=(
            "<style>:root { --pjx-z-popover: 310; }</style>"
            "<style>:root { --pjx-select-panel-z: 275; }</style>"
        ),
    )
    assert _select_style(page, "panel", "z-index") == "275"


def test_select_checkbox_accent_follows_brand(page):
    _select_page(page, CHECKBOX_MARKUP)
    assert _select_style(page, "box", "accent-color") == "rgb(39, 39, 42)"
    page.emulate_media(color_scheme="light")
    _select_page(
        page,
        CHECKBOX_MARKUP,
        head=f"<style>{read_pjx_theme_css()}</style>",
        html_attrs=' data-pjx-theme="dark"',
    )
    assert _select_style(page, "box", "accent-color") == "rgb(228, 228, 231)"


def test_select_selected_option_stays_visible_in_dark_mode(page):
    page.emulate_media(color_scheme="light")
    # Dark on <html>: component tokens resolve on :root.
    _select_page(
        page,
        SELECT_MARKUP,
        head=f"<style>{read_pjx_theme_css()}</style>",
        html_attrs=' data-pjx-theme="dark"',
    )
    assert _select_style(page, "panel", "background-color") == "rgb(9, 9, 11)"
    assert _select_style(page, "picked", "background-color") == "rgb(63, 63, 70)"
    assert _select_style(page, "trigger", "background-color") == "rgb(24, 24, 27)"
    assert _select_style(page, "trigger", "color") == "rgb(244, 244, 245)"
