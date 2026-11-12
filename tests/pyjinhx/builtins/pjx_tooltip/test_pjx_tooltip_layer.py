"""The tooltip tip and backdrop sit on the tooltip layer, and their tokens stay overridable."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

import pytest

if TYPE_CHECKING:
    from playwright.sync_api import Page

UI = Path(__file__).resolve().parents[4] / "pyjinhx" / "builtins" / "ui"
TOOLTIP_CSS = UI / "pjx_tooltip" / "pjx_tooltip.css"
TOOLTIP_CONTENT_CSS = UI / "pjx_tooltip_content" / "pjx_tooltip_content.css"


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


def _render(page: Page, app_css: str = "", backdrop_visible: bool = True) -> None:
    # The app sheet comes after the tooltip sheets, the way an app's own CSS would.
    backdrop_class = "pjx-tooltip__backdrop"
    if backdrop_visible:
        backdrop_class += " pjx-tooltip__backdrop--visible"
    page.set_content(
        f"<html><head><style>{TOOLTIP_CSS.read_text()}</style>"
        f"<style>{TOOLTIP_CONTENT_CSS.read_text()}</style>"
        f"<style>{app_css}</style></head>"
        '<body><span class="pjx-tooltip">'
        f'<div id="b" class="{backdrop_class}"></div>'
        '<button id="t" class="pjx-tooltip__trigger">?</button>'
        '<span id="tip" class="pjx-tooltip__tip">help</span>'
        "</span></body></html>"
    )


def _z_index(page: Page, element_id: str) -> str:
    return page.evaluate(
        f"getComputedStyle(document.getElementById('{element_id}')).zIndex"
    )


def _z_indexes(page: Page, app_css: str = "") -> tuple[str, str, str]:
    """Return the (tip, backdrop, trigger) computed z-index."""
    _render(page, app_css)
    return _z_index(page, "tip"), _z_index(page, "b"), _z_index(page, "t")


def test_tooltip_defaults_to_the_tooltip_layer(page: Page):
    assert _z_indexes(page) == ("400", "390", "391")


def test_tooltip_follows_a_tooltip_layer_override(page: Page):
    app_css = ":root { --pjx-z-tooltip: 450; }"
    assert _z_indexes(page, app_css) == ("450", "440", "441")


def test_tooltip_tokens_win_over_the_tooltip_layer(page: Page):
    app_css = (
        ":root { --pjx-z-tooltip: 450; --pjx-tooltip-z: 500;"
        " --pjx-tooltip-backdrop-z: 480; }"
    )
    assert _z_indexes(page, app_css) == ("500", "480", "481")


def test_trigger_is_not_lifted_without_a_visible_backdrop(page: Page):
    _render(page, backdrop_visible=False)
    assert _z_index(page, "t") == "auto"


def test_tooltip_gap_stays_a_pixel_count(page: Page):
    # pjx_tooltip.js parses this with parseInt, so it must stay a bare px value.
    _render(page)
    gap = page.evaluate(
        "getComputedStyle(document.documentElement)"
        ".getPropertyValue('--pjx-tooltip-gap').trim()"
    )
    assert gap == "6px"
