"""PJXRosterPicker — the picker shell: search combobox, chips, cap hint, validity input and CSS."""

from pathlib import Path

from pyjinhx.client import read_pjx_theme_css

PACKAGE_DIR = (
    Path(__file__).resolve().parents[4] / "pyjinhx" / "builtins" / "pjx_roster_picker"
)


CSS_PATH = PACKAGE_DIR / "pjx_roster_picker.css"


PICKER_MARKUP = (
    '<div class="pjx-roster-picker">'
    '<div class="pjx-roster-picker__search">'
    '<input id="input" class="pjx-roster-picker__input">'
    '<div id="results" class="pjx-roster-picker__results">'
    '<button id="pick" class="pjx-roster-picker__pick" type="button">Ada</button>'
    "</div></div>"
    '<div class="pjx-roster-picker__chips">'
    '<span id="chip" class="pjx-roster-picker__chip">Ada</span>'
    "</div>"
    '<p id="hint" class="pjx-roster-picker__hint">Limit reached</p>'
    "</div>"
    '<div class="pjx-roster-picker pjx-roster-picker--invalid">'
    '<div class="pjx-roster-picker__search">'
    '<input id="invalid" class="pjx-roster-picker__input">'
    "</div></div>"
)


# What the portal leaves behind: the list moved to <body>, outside any picker root.
PORTALLED_MARKUP = '<div id="results" class="pjx-roster-picker__results"></div>'


def _picker_page(page, body: str, *, head: str = "", html_attrs: str = "") -> None:
    css = CSS_PATH.read_text(encoding="utf-8")
    page.set_content(
        f"<html{html_attrs}><head>{head}<style>{css}</style></head>"
        f"<body>{body}</body></html>"
    )


def _picker_style(page, element_id: str, prop: str) -> str:
    return page.evaluate(
        f"getComputedStyle(document.getElementById('{element_id}'))"
        f".getPropertyValue('{prop}')"
    )


def _root_token(page, name: str) -> str:
    return page.evaluate(
        f"getComputedStyle(document.documentElement).getPropertyValue('{name}').trim()"
    )


def test_roster_picker_defaults_use_light_fallbacks(page):
    _picker_page(page, PICKER_MARKUP)
    assert _picker_style(page, "input", "background-color") == "rgb(255, 255, 255)"
    assert _picker_style(page, "input", "color") == "rgb(24, 24, 27)"
    assert _picker_style(page, "input", "border-top-color") == "rgb(228, 228, 231)"
    assert _picker_style(page, "input", "border-top-left-radius") == "8px"
    # 0.375rem stays off the spacing scale; 8px is space-2.
    assert _picker_style(page, "input", "padding-top") == "6px"
    assert _picker_style(page, "input", "padding-left") == "8px"
    assert _picker_style(page, "input", "transition-duration") == "0.15s"
    assert _picker_style(page, "results", "z-index") == "300"
    assert _picker_style(page, "results", "background-color") == "rgb(250, 250, 250)"
    assert _picker_style(page, "chip", "padding-top") == "4px"
    assert _picker_style(page, "chip", "padding-left") == "8px"
    assert _picker_style(page, "chip", "column-gap") == "4px"
    assert _picker_style(page, "pick", "column-gap") == "8px"
    assert _picker_style(page, "hint", "color") == "rgb(82, 82, 91)"
    assert _picker_style(page, "invalid", "border-top-color") == "rgb(220, 38, 38)"


def test_roster_picker_results_layer_follows_popover_token(page):
    _picker_page(
        page,
        PICKER_MARKUP,
        head="<style>:root { --pjx-z-popover: 310; }</style>",
    )
    assert _picker_style(page, "results", "z-index") == "310"
    _picker_page(
        page,
        PICKER_MARKUP,
        head=(
            "<style>:root { --pjx-z-popover: 310; }</style>"
            "<style>:root { --pjx-roster-picker-z: 275; }</style>"
        ),
    )
    assert _picker_style(page, "results", "z-index") == "275"
    # The component token still wins with the theme sheet loaded.
    _picker_page(
        page,
        PICKER_MARKUP,
        head=(
            f"<style>{read_pjx_theme_css()}</style>"
            "<style>:root { --pjx-roster-picker-z: 275; }</style>"
        ),
    )
    assert _picker_style(page, "results", "z-index") == "275"


def test_roster_picker_follows_dark_theme(page):
    page.emulate_media(color_scheme="light")
    _picker_page(
        page,
        PICKER_MARKUP,
        head=f"<style>{read_pjx_theme_css()}</style>",
        html_attrs=' data-pjx-theme="dark"',
    )
    assert _picker_style(page, "results", "background-color") == "rgb(9, 9, 11)"
    assert _root_token(page, "--pjx-roster-picker-row-active") == "#3f3f46"
    assert _picker_style(page, "input", "background-color") == "rgb(24, 24, 27)"
    assert _picker_style(page, "input", "color") == "rgb(244, 244, 245)"


def test_roster_picker_follows_os_dark_preference(page):
    page.emulate_media(color_scheme="dark")
    _picker_page(page, PICKER_MARKUP, head=f"<style>{read_pjx_theme_css()}</style>")
    assert _picker_style(page, "results", "background-color") == "rgb(9, 9, 11)"
    assert _picker_style(page, "input", "background-color") == "rgb(24, 24, 27)"


def test_roster_picker_portalled_results_keep_their_layer(page):
    _picker_page(page, PORTALLED_MARKUP)
    assert _picker_style(page, "results", "z-index") == "300"
    assert _picker_style(page, "results", "background-color") == "rgb(250, 250, 250)"


def test_roster_picker_reduced_motion_drops_transitions(page):
    page.emulate_media(reduced_motion="reduce")
    _picker_page(page, PICKER_MARKUP)
    assert _picker_style(page, "input", "transition-duration") == "0s"
    assert _picker_style(page, "pick", "transition-duration") == "0s"
