"""The open popover panel sits on the popover layer, and both tokens stay overridable."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

import pytest

if TYPE_CHECKING:
    from playwright.sync_api import Page

POPOVER_CSS = (
    Path(__file__).resolve().parents[4]
    / "pyjinhx"
    / "builtins"
    / "ui"
    / "pjx_popover"
    / "pjx_popover.css"
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


def _panel_style(page: Page, prop: str, app_css: str = "") -> str:
    # The app sheet comes after the popover sheet, the way an app's own CSS would.
    page.set_content(
        f"<html><head><style>{POPOVER_CSS.read_text()}</style>"
        f"<style>{app_css}</style></head>"
        '<body><div class="pjx-popover">'
        '<div id="p" class="pjx-popover__panel">x</div></div></body></html>'
    )
    return page.evaluate(f"getComputedStyle(document.getElementById('p')).{prop}")


def test_popover_defaults_to_the_popover_layer(page: Page):
    assert _panel_style(page, "zIndex") == "300"


def test_popover_follows_a_popover_layer_override(page: Page):
    assert _panel_style(page, "zIndex", ":root { --pjx-z-popover: 310; }") == "310"


def test_popover_token_wins_over_the_popover_layer(page: Page):
    app_css = ":root { --pjx-z-popover: 310; --pjx-popover-z: 375; }"
    assert _panel_style(page, "zIndex", app_css) == "375"


def test_popover_panel_paints_the_light_surface_without_a_theme(page: Page):
    assert _panel_style(page, "backgroundColor") == "rgb(250, 250, 250)"
