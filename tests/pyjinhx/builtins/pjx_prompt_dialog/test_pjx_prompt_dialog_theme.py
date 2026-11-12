"""The prompt dialog's colours and spacing resolve from the theme, or from its light fallbacks without one."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

import pytest

from pyjinhx.client import read_pjx_theme_css

if TYPE_CHECKING:
    from playwright.sync_api import Page

PROMPT_CSS = (
    Path(__file__).resolve().parents[4]
    / "pyjinhx"
    / "builtins"
    / "ui"
    / "pjx_prompt_dialog"
    / "pjx_prompt_dialog.css"
)

BODY = (
    '<dialog id="d" class="pjx-prompt-dialog">'
    '<form id="card" class="pjx-prompt-dialog__card" method="dialog">'
    '<label id="label" class="pjx-prompt-dialog__label" for="input">Name</label>'
    '<input id="input" class="pjx-prompt-dialog__input" type="text">'
    '<div class="pjx-prompt-dialog__actions">'
    '<button type="button" class="pjx-prompt-dialog__cancel">Cancel</button>'
    '<button type="submit" class="pjx-prompt-dialog__ok">OK</button>'
    "</div>"
    "</form>"
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


def _open(page: Page, head: str = "", html_attrs: str = "") -> None:
    page.set_content(
        f"<html {html_attrs}><head>{head}"
        f"<style>{PROMPT_CSS.read_text()}</style></head>"
        f"<body>{BODY}</body></html>"
    )
    page.evaluate("document.getElementById('d').showModal()")


def _style(page: Page, element_id: str, prop: str) -> str:
    return page.evaluate(
        f"getComputedStyle(document.getElementById('{element_id}')).{prop}"
    )


def _theme() -> str:
    return f"<style>{read_pjx_theme_css()}</style>"


def test_prompt_dialog_uses_the_light_fallback_without_a_theme(page: Page):
    _open(page)
    assert _style(page, "d", "backgroundColor") == "rgb(255, 255, 255)"
    assert _style(page, "input", "backgroundColor") == "rgb(250, 250, 250)"


def test_prompt_dialog_follows_the_dark_theme(page: Page):
    page.emulate_media(color_scheme="light")
    _open(page, head=_theme(), html_attrs='data-pjx-theme="dark"')
    assert _style(page, "d", "backgroundColor") == "rgb(24, 24, 27)"
    assert _style(page, "input", "backgroundColor") == "rgb(9, 9, 11)"
    assert _style(page, "input", "borderTopColor") == "rgb(63, 63, 70)"
    assert _style(page, "label", "color") == "rgb(244, 244, 245)"


def test_prompt_dialog_card_spacing_uses_the_spacing_fallbacks(page: Page):
    _open(page)
    assert _style(page, "card", "padding") == "20px 24px"
    assert _style(page, "card", "rowGap") == "12px"


def test_prompt_dialog_follows_the_os_dark_preference(page: Page):
    page.emulate_media(color_scheme="dark")
    _open(page, head=_theme())
    assert _style(page, "d", "backgroundColor") == "rgb(24, 24, 27)"
    assert _style(page, "input", "backgroundColor") == "rgb(9, 9, 11)"


def test_prompt_dialog_forced_light_beats_the_os_dark_preference(page: Page):
    page.emulate_media(color_scheme="dark")
    _open(page, head=_theme(), html_attrs='data-pjx-theme="light"')
    assert _style(page, "d", "backgroundColor") == "rgb(255, 255, 255)"
    assert _style(page, "input", "backgroundColor") == "rgb(250, 250, 250)"
