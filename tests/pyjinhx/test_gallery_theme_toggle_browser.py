"""The gallery's theme control in real chromium.

Each demo page carries a System/Light/Dark select that sets or removes
data-pjx-theme on <html>, remembers the choice in localStorage and passes it
to the other open demo pages. Only a browser resolves the theme cascade,
prefers-color-scheme, the storage event and a throwing localStorage.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pytest

import pyjinhx.builtins  # noqa: F401

DOCS = Path(__file__).resolve().parents[2] / "docs"
sys.path.insert(0, str(DOCS))

import hooks

if TYPE_CHECKING:
    from playwright.sync_api import BrowserContext, Page, Route

URL = "http://pjx.test/"
KEY = "pjx-gallery-theme"
SELECT = "select[data-pjx-demo-theme]"
ATTR = 'document.documentElement.getAttribute("data-pjx-theme")'
SURFACE = (
    "getComputedStyle(document.documentElement)"
    '.getPropertyValue("--pjx-color-surface").trim()'
)
BODY_BACKGROUND = "getComputedStyle(document.body).backgroundColor"
LIGHT_SURFACE = "#ffffff"
DARK_SURFACE = "#18181b"


# Copied from tests/pyjinhx/builtins/pjx_chart/conftest.py: that conftest only
# covers its own directory, and the tests tree has no __init__.py files, so
# test modules cannot import each other reliably.
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


@pytest.fixture
def page_errors(page: Page) -> list[str]:
    """Every uncaught error the page throws from here on."""
    errors: list[str] = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    return errors


@pytest.fixture(scope="module")
def demos(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """One gallery build, shared by every test here."""
    site = tmp_path_factory.mktemp("site")
    hooks.on_post_build({"site_dir": str(site)})
    return site / "demos"


def _serve(target: Page | BrowserContext, demos: Path) -> None:
    """Answer URL + <name> with demos/<name>, as the built site would."""

    def fulfill(route: Route) -> None:
        name = route.request.url.removeprefix(URL)
        path = demos / name
        if not path.is_file():
            route.fulfill(status=404, body="")
            return
        content_type = "text/css" if name.endswith(".css") else "text/html"
        route.fulfill(content_type=content_type, body=path.read_text("utf-8"))

    target.route(URL + "**", fulfill)


def test_toggling_flips_a_token_value(
    page: Page, page_errors: list[str], demos: Path
) -> None:
    page.emulate_media(color_scheme="light")
    _serve(page, demos)
    page.goto(URL + "pjx-button.html")
    assert page.evaluate(ATTR) is None
    assert page.evaluate(SURFACE) == LIGHT_SURFACE

    page.select_option(SELECT, "dark")
    assert page.evaluate(ATTR) == "dark"
    assert page.evaluate(SURFACE) == DARK_SURFACE
    assert page.evaluate(BODY_BACKGROUND) == "rgb(24, 24, 27)"

    page.select_option(SELECT, "light")
    assert page.evaluate(ATTR) == "light"
    assert page.evaluate(SURFACE) == LIGHT_SURFACE

    page.select_option(SELECT, "system")
    assert page.evaluate(ATTR) is None  # removed, never set to "system"
    assert page.evaluate(SURFACE) == LIGHT_SURFACE
    assert page_errors == []


def test_system_follows_the_os_and_light_overrides_it(
    page: Page, page_errors: list[str], demos: Path
) -> None:
    page.emulate_media(color_scheme="dark")
    _serve(page, demos)
    # A runtime page: its assets sit at the end of <body>, not in <head>.
    page.goto(URL + "pjx-graph.html")
    assert page.evaluate(ATTR) is None
    assert page.evaluate(SURFACE) == DARK_SURFACE

    page.select_option(SELECT, "light")
    assert page.evaluate(SURFACE) == LIGHT_SURFACE

    page.select_option(SELECT, "system")
    assert page.evaluate(ATTR) is None
    assert page.evaluate(SURFACE) == DARK_SURFACE
    assert page_errors == []


def test_choice_survives_reload(
    page: Page, page_errors: list[str], demos: Path
) -> None:
    _serve(page, demos)
    page.goto(URL + "pjx-button.html")
    page.select_option(SELECT, "dark")
    page.reload()
    assert page.evaluate(ATTR) == "dark"
    assert page.input_value(SELECT) == "dark"

    page.select_option(SELECT, "system")
    page.reload()
    assert page.evaluate(ATTR) is None
    assert page.input_value(SELECT) == "system"
    assert page.evaluate(f'localStorage.getItem("{KEY}")') is None
    assert page_errors == []


def test_choice_syncs_to_other_open_pages(page: Page, demos: Path) -> None:
    _serve(page.context, demos)
    page.goto(URL + "pjx-button.html")
    other = page.context.new_page()
    other.goto(URL + "pjx-badge.html")

    page.select_option(SELECT, "dark")
    other.wait_for_function(f'{ATTR} === "dark"')
    assert other.input_value(SELECT) == "dark"

    # localStorage.clear() fires a storage event whose key is null.
    page.evaluate("localStorage.clear()")
    other.wait_for_function(f"{ATTR} === null")
    assert other.input_value(SELECT) == "system"


def test_unknown_stored_value_means_system(
    page: Page, page_errors: list[str], demos: Path
) -> None:
    page.add_init_script(f'localStorage.setItem("{KEY}", "blue")')
    _serve(page, demos)
    page.goto(URL + "pjx-button.html")
    assert page.evaluate(ATTR) is None
    assert page.input_value(SELECT) == "system"
    assert page_errors == []


def test_toggle_works_when_storage_throws(
    page: Page, page_errors: list[str], demos: Path
) -> None:
    page.add_init_script(
        'Object.defineProperty(window, "localStorage", {get() {'
        ' throw new DOMException("denied", "SecurityError"); }})'
    )
    _serve(page, demos)
    page.goto(URL + "pjx-button.html")
    # The stand-in really throws, so the toggle is exercised against it.
    thrown = page.evaluate(
        "(() => { try { localStorage; return null; }"
        " catch (error) { return error.name; } })()"
    )
    assert thrown == "SecurityError"

    page.select_option(SELECT, "dark")
    assert page.evaluate(ATTR) == "dark"
    assert page_errors == []


def test_control_is_pinned_inside_the_smallest_frame(page: Page, demos: Path) -> None:
    # The gallery's shortest iframe is 120px tall.
    page.set_viewport_size({"width": 400, "height": 120})
    _serve(page, demos)
    page.goto(URL + "pjx-button.html")
    position = page.evaluate(
        f'getComputedStyle(document.querySelector("{SELECT}")).position'
    )
    assert position == "fixed"  # out of the body grid, so the stage stays centred
    box = page.locator(SELECT).bounding_box()
    assert box is not None
    assert box["y"] >= 0 and box["y"] + box["height"] <= 120
    assert box["x"] >= 0 and box["x"] + box["width"] <= 400
    # Pinned top-right: closer to the right edge than the left.
    assert 400 - (box["x"] + box["width"]) < box["x"]
