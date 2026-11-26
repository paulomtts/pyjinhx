"""PJXToggleSwitch: the stylesheet fallbacks and theme tokens, read from computed style in chromium.

The field and markup checks are in tests/unit/builtins/test_pjx_toggle_switch.py.
"""

from pyjinhx.builtins.pjx_toggle_switch import PJXToggleSwitch
from pyjinhx.client import read_pjx_theme_css

TOGGLE_CSS = PJXToggleSwitch.__pjx_descriptor__.css_paths[0].read_text(encoding="utf-8")


def _toggle_markup(checked: bool) -> str:
    state = " checked" if checked else ""
    return (
        '<label class="pjx-toggle-switch">'
        f'<input class="pjx-toggle-switch__input" type="checkbox"{state}>'
        '<span id="track" class="pjx-toggle-switch__track">'
        '<span id="thumb" class="pjx-toggle-switch__thumb"></span>'
        "</span></label>"
    )


def _background(page, element_id: str) -> str:
    return page.evaluate(
        f"getComputedStyle(document.getElementById('{element_id}')).backgroundColor"
    )


def test_toggle_switch_defaults_use_light_fallbacks(page):
    page.set_content(
        f"<html><head><style>{TOGGLE_CSS}</style></head>"
        f"<body>{_toggle_markup(checked=False)}</body></html>"
    )
    assert _background(page, "track") == "rgb(212, 212, 216)"
    assert _background(page, "thumb") == "rgb(255, 255, 255)"
    assert (
        page.evaluate(
            "getComputedStyle(document.getElementById('track')).transitionDuration"
        )
        == "0.15s"
    )


def test_toggle_switch_on_state_follows_theme_in_dark_mode(page):
    page.emulate_media(color_scheme="light")
    page.set_content(
        # Dark on <html>: component tokens are declared on :root, so their
        # var() resolves there and a dark subtree alone would not flip them.
        f'<html data-pjx-theme="dark"><head><style>{read_pjx_theme_css()}</style>'
        f"<style>{TOGGLE_CSS}</style></head>"
        f"<body>{_toggle_markup(checked=True)}</body></html>"
    )
    # The thumb takes on-brand so it stays visible on the light dark-mode track.
    assert _background(page, "track") == "rgb(228, 228, 231)"
    assert _background(page, "thumb") == "rgb(9, 9, 11)"


def test_toggle_switch_component_token_still_wins(page):
    page.set_content(
        f"<html><head><style>{read_pjx_theme_css()}</style>"
        f"<style>{TOGGLE_CSS}</style>"
        "<style>:root { --pjx-toggle-switch-track-on: rgb(1, 2, 3); }</style>"
        f"</head><body>{_toggle_markup(checked=True)}</body></html>"
    )
    assert _background(page, "track") == "rgb(1, 2, 3)"
