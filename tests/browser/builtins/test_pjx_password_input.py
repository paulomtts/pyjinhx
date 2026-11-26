"""PJXPasswordInput: the stylesheet fallbacks and theme tokens, read from computed style in chromium.

The field and markup checks are in tests/unit/builtins/test_pjx_password_input.py.
"""

from pyjinhx.builtins.pjx_password_input import PJXPasswordInput
from pyjinhx.client import read_pjx_theme_css

PASSWORD_CSS = PJXPasswordInput.__pjx_descriptor__.css_paths[0].read_text(
    encoding="utf-8"
)


PASSWORD_MARKUP = (
    '<div id="root" class="pjx-password-input">'
    '<input id="field" class="pjx-password-input__field" type="password">'
    '<button id="toggle" class="pjx-password-input__toggle" type="button">'
    '<span class="pjx-password-input__eye"></span></button>'
    "</div>"
)


def _password_style(page, element_id: str, prop: str) -> str:
    return page.evaluate(
        f"getComputedStyle(document.getElementById('{element_id}'))"
        f".getPropertyValue('{prop}')"
    )


def test_password_input_defaults_use_light_fallbacks(page):
    page.set_content(
        f"<html><head><style>{PASSWORD_CSS}</style></head>"
        f"<body>{PASSWORD_MARKUP}</body></html>"
    )
    assert _password_style(page, "root", "border-top-color") == "rgb(228, 228, 231)"
    assert _password_style(page, "root", "border-top-left-radius") == "8px"
    assert _password_style(page, "root", "background-color") == "rgb(255, 255, 255)"
    assert _password_style(page, "field", "padding-top") == "8px"
    assert _password_style(page, "field", "padding-left") == "12px"
    # 2.75rem tracks the 2.5rem toggle, not the spacing scale.
    assert _password_style(page, "field", "padding-right") == "44px"
    assert _password_style(page, "field", "color") == "rgb(24, 24, 27)"
    assert _password_style(page, "toggle", "color") == "rgb(82, 82, 91)"
    assert _password_style(page, "toggle", "transition-duration") == "0.15s"


def test_password_input_focus_ring_uses_light_fallback(page):
    page.set_content(
        f"<html><head><style>{PASSWORD_CSS}</style></head>"
        f"<body>{PASSWORD_MARKUP}</body></html>"
    )
    page.focus("#field")
    assert _password_style(page, "root", "outline-style") == "solid"
    assert _password_style(page, "root", "outline-color") == "rgb(63, 63, 70)"


def test_password_input_component_token_still_wins(page):
    page.set_content(
        f"<html><head><style>{read_pjx_theme_css()}</style>"
        f"<style>{PASSWORD_CSS}</style>"
        "<style>:root { --pjx-password-input-border: rgb(1, 2, 3); }</style>"
        f"</head><body>{PASSWORD_MARKUP}</body></html>"
    )
    assert _password_style(page, "root", "border-top-color") == "rgb(1, 2, 3)"
