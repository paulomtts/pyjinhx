"""PJXButton — v0.x field/markup parity on the v2 engine.

Port of tests/unit/test_button.py. v0.x's golden snapshots
(tests/unit/golden/button_default.html, button_loading.html) do not carry
over: v2 builtins assert on rendered substrings, like every sibling port.
"""

from pyjinhx.builtins.pjx_button import PJXButton

BUTTON_CSS = PJXButton.__pjx_descriptor__.css_paths[0].read_text(encoding="utf-8")


def _button_style(page, prop: str) -> str:
    return page.evaluate(
        f"getComputedStyle(document.getElementById('b')).getPropertyValue('{prop}')"
    )


def test_button_defaults_follow_radius_and_spacing_tokens(page):
    page.set_content(
        f"<html><head><style>{BUTTON_CSS}</style></head><body>"
        '<button id="b" class="pjx-button">Save</button>'
        "</body></html>"
    )
    # No theme loaded: the literal light fallbacks apply.
    assert _button_style(page, "border-top-left-radius") == "8px"
    assert _button_style(page, "padding-top") == "8px"
    assert _button_style(page, "padding-left") == "12px"
    assert _button_style(page, "column-gap") == "8px"

    page.add_style_tag(content=":root { --pjx-radius-md: 2px; --pjx-space-3: 20px; }")
    assert _button_style(page, "border-top-left-radius") == "2px"
    assert _button_style(page, "padding-left") == "20px"

    page.add_style_tag(content="#b { --pjx-button-radius: 0px; }")
    assert _button_style(page, "border-top-left-radius") == "0px"
