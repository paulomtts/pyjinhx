"""The modal's surface resolves from the theme, or from its light fallback without one."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from pyjinhx.client import read_pjx_theme_css

if TYPE_CHECKING:
    from playwright.sync_api import Page

MODAL_CSS = (
    Path(__file__).resolve().parents[3]
    / "pyjinhx"
    / "builtins"
    / "pjx_modal"
    / "pjx_modal.css"
)

BODY = (
    '<dialog id="m" class="pjx-modal">'
    '<div id="box" class="pjx-modal__box">x</div>'
    "</dialog>"
)


def _box_background(page: Page, head: str, html_attrs: str = "") -> str:
    page.set_content(
        f"<html {html_attrs}><head>{head}"
        f"<style>{MODAL_CSS.read_text()}</style></head>"
        f"<body>{BODY}</body></html>"
    )
    page.evaluate("document.getElementById('m').showModal()")
    return page.evaluate(
        "getComputedStyle(document.getElementById('box')).backgroundColor"
    )


def test_modal_box_uses_the_light_fallback_without_a_theme(page: Page):
    assert _box_background(page, head="") == "rgb(255, 255, 255)"


def test_modal_box_follows_the_dark_theme(page: Page):
    page.emulate_media(color_scheme="light")
    theme = f"<style>{read_pjx_theme_css()}</style>"
    background = _box_background(page, head=theme, html_attrs='data-pjx-theme="dark"')
    assert background == "rgb(24, 24, 27)"
