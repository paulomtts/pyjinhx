"""The dropdown menu sits on the popover layer, and its tokens stay overridable."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

import pytest

from pyjinhx.client import read_pjx_theme_css

if TYPE_CHECKING:
    from playwright.sync_api import Page

DROPDOWN_CSS = (
    Path(__file__).resolve().parents[4]
    / "pyjinhx"
    / "builtins"
    / "ui"
    / "pjx_dropdown"
    / "pjx_dropdown.css"
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


def _style(
    page: Page,
    element_id: str,
    prop: str,
    app_css: str = "",
    theme_css: str = "",
    html_attrs: str = "",
) -> str:
    # The theme sheet comes first and the app sheet last, as in a real page.
    page.set_content(
        f"<html {html_attrs}><head><style>{theme_css}</style>"
        f"<style>{DROPDOWN_CSS.read_text()}</style>"
        f"<style>{app_css}</style></head>"
        '<body><div class="pjx-dropdown">'
        '<button id="t" class="pjx-dropdown__trigger">Menu</button>'
        '<div id="m" class="pjx-dropdown__menu">x</div></div></body></html>'
    )
    return page.evaluate(
        f"getComputedStyle(document.getElementById('{element_id}')).{prop}"
    )


def test_dropdown_defaults_to_the_popover_layer(page: Page):
    assert _style(page, "m", "zIndex") == "300"


def test_dropdown_follows_a_popover_layer_override(page: Page):
    assert _style(page, "m", "zIndex", ":root { --pjx-z-popover: 310; }") == "310"


def test_dropdown_token_wins_over_the_popover_layer(page: Page):
    app_css = ":root { --pjx-z-popover: 310; --pjx-dropdown-z: 375; }"
    assert _style(page, "m", "zIndex", app_css) == "375"


def test_dropdown_menu_follows_the_dark_theme(page: Page):
    background = _style(
        page,
        "m",
        "backgroundColor",
        theme_css=read_pjx_theme_css(),
        html_attrs='data-pjx-theme="dark"',
    )
    assert background == "rgb(9, 9, 11)"


def test_dropdown_trigger_bg_token_still_wins(page: Page):
    app_css = ":root { --pjx-dropdown-trigger-bg: rgb(1 2 3); }"
    assert _style(page, "t", "backgroundColor", app_css) == "rgb(1, 2, 3)"
