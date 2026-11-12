"""The confirm dialog's colours and spacing resolve from the theme, or from its light fallbacks without one."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

import pytest

from pyjinhx.client import read_pjx_theme_css

if TYPE_CHECKING:
    from playwright.sync_api import Page

CONFIRM_CSS = (
    Path(__file__).resolve().parents[4]
    / "pyjinhx"
    / "builtins"
    / "ui"
    / "pjx_confirm_dialog"
    / "pjx_confirm_dialog.css"
)

BODY = (
    '<dialog id="d" class="pjx-confirm-dialog">'
    '<div id="card" class="pjx-confirm-dialog__card">'
    '<p id="message" class="pjx-confirm-dialog__message">Sure?</p>'
    '<div class="pjx-confirm-dialog__actions">'
    '<button type="button" class="pjx-confirm-dialog__cancel">Cancel</button>'
    '<button id="ok" type="button" class="pjx-confirm-dialog__ok">Confirm</button>'
    "</div>"
    "</div>"
    "</dialog>"
)


@pytest.fixture(autouse=True)
def _require_chromium(request: pytest.FixtureRequest) -> None:
    if "page" not in set(request.fixturenames):
        return
    pytest.importorskip("playwright")
    browser_type: Any = request.getfixturevalue("browser_type")
    if not Path(browser_type.executable_path).exists():
        pytest.skip(
            "chromium is not installed (run: uv run playwright install chromium)"
        )


def _open(page: Page, head: str = "", html_attrs: str = "", after: str = "") -> None:
    page.set_content(
        f"<html {html_attrs}><head>{head}"
        f"<style>{CONFIRM_CSS.read_text()}</style>{after}</head>"
        f"<body>{BODY}</body></html>"
    )
    page.evaluate("document.getElementById('d').showModal()")


def _style(page: Page, element_id: str, prop: str) -> str:
    return page.evaluate(
        f"getComputedStyle(document.getElementById('{element_id}')).{prop}"
    )


def _theme() -> str:
    return f"<style>{read_pjx_theme_css()}</style>"


def test_confirm_dialog_uses_the_light_fallback_without_a_theme(page: Page):
    _open(page)
    assert _style(page, "d", "backgroundColor") == "rgb(255, 255, 255)"
    assert _style(page, "message", "color") == "rgb(24, 24, 27)"


def test_confirm_dialog_follows_the_dark_theme(page: Page):
    page.emulate_media(color_scheme="light")
    _open(page, head=_theme(), html_attrs='data-pjx-theme="dark"')
    assert _style(page, "d", "backgroundColor") == "rgb(24, 24, 27)"
    assert _style(page, "message", "color") == "rgb(244, 244, 245)"


def test_confirm_dialog_card_padding_uses_the_spacing_fallbacks(page: Page):
    _open(page)
    assert _style(page, "card", "padding") == "20px 24px"


def test_confirm_dialog_danger_button_keeps_its_colour(page: Page):
    _open(page)
    page.evaluate(
        "document.getElementById('ok').classList.add('pjx-confirm-dialog__ok--danger')"
    )
    assert _style(page, "ok", "backgroundColor") == "rgb(179, 38, 30)"
    assert _style(page, "ok", "color") == "rgb(255, 255, 255)"


def test_confirm_dialog_danger_button_keeps_its_colour_in_dark_theme(page: Page):
    page.emulate_media(color_scheme="light")
    _open(page, head=_theme(), html_attrs='data-pjx-theme="dark"')
    page.evaluate(
        "document.getElementById('ok').classList.add('pjx-confirm-dialog__ok--danger')"
    )
    assert _style(page, "ok", "backgroundColor") == "rgb(179, 38, 30)"
    assert _style(page, "ok", "color") == "rgb(255, 255, 255)"


def test_confirm_dialog_component_token_override_wins(page: Page):
    override = "<style>:root { --pjx-confirm-dialog-bg: rgb(1, 2, 3); }</style>"
    _open(page, head=_theme(), after=override)
    assert _style(page, "d", "backgroundColor") == "rgb(1, 2, 3)"
