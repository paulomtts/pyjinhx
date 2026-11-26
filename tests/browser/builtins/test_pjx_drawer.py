"""The open drawer sits on the overlay layer, and both layer tokens stay overridable."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from playwright.sync_api import Page

DRAWER_CSS = (
    Path(__file__).resolve().parents[3]
    / "pyjinhx"
    / "builtins"
    / "pjx_drawer"
    / "pjx_drawer.css"
)


def _open_drawer_z_index(page: Page, app_css: str = "") -> str:
    # The app sheet comes after the drawer sheet, the way an app's own CSS would.
    page.set_content(
        f"<html><head><style>{DRAWER_CSS.read_text()}</style>"
        f"<style>{app_css}</style></head>"
        '<body><dialog id="d" class="pjx-drawer pjx-drawer--right">'
        '<div class="pjx-drawer__box">x</div></dialog></body></html>'
    )
    page.evaluate("document.getElementById('d').showModal()")
    return page.evaluate("getComputedStyle(document.getElementById('d')).zIndex")


def test_drawer_defaults_to_the_overlay_layer(page: Page):
    assert _open_drawer_z_index(page) == "200"


def test_drawer_follows_an_overlay_layer_override(page: Page):
    assert _open_drawer_z_index(page, ":root { --pjx-z-overlay: 210; }") == "210"


def test_drawer_token_wins_over_the_overlay_layer(page: Page):
    app_css = ":root { --pjx-z-overlay: 210; --pjx-drawer-z: 275; }"
    assert _open_drawer_z_index(page, app_css) == "275"
