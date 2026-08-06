"""window.pjx.popoverPosition(): flip/clamp geometry, exercised with synthetic rects.

The function is browser code with no DOM access, so the tests run the real
file in chromium and call it directly rather than asserting on source strings.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pytest

if TYPE_CHECKING:
    from playwright.sync_api import Page

SOURCE = (
    Path(__file__).resolve().parents[4]
    / "pyjinhx"
    / "builtins"
    / "ui"
    / "pjx_popover"
    / "pjx_popover_position.js"
)


@pytest.fixture(autouse=True)
def _require_chromium(request: pytest.FixtureRequest) -> None:
    # Function-scoped so a missing browser skips only the tests that ask for
    # a page, mirroring tests/pyjinhx/client/conftest.py.
    if "position" not in set(request.fixturenames):
        return
    pytest.importorskip("playwright")
    browser_type: Any = request.getfixturevalue("browser_type")
    if not Path(browser_type.executable_path).exists():
        pytest.skip(
            "chromium is not installed (run: uv run playwright install chromium)"
        )


@pytest.fixture
def position(page: Page) -> Iterator[Callable[..., dict[str, Any]]]:
    """Call popoverPosition in the browser and hand back its plain-object result."""
    page.set_content("<body></body>")
    page.add_script_tag(content=SOURCE.read_text())

    def call(**options: Any) -> dict[str, Any]:
        return page.evaluate(f"pjx.popoverPosition({json.dumps(options)})")

    yield call


def _opts(**overrides: Any) -> dict[str, Any]:
    """A roomy, non-overflowing baseline: 100x30 trigger at (100, 100), 200x150 panel, 1000x800 viewport."""
    options: dict[str, Any] = {
        "trigger": {"top": 100, "left": 100, "width": 100, "height": 30},
        "panel": {"width": 200, "height": 150},
        "viewport": {"width": 1000, "height": 800},
        "align": "start",
    }
    options.update(overrides)
    return options


def test_no_overflow_resolves_to_the_static_css_default(position):
    assert position(**_opts()) == {
        "align": "start",
        "placement": "below",
        "left": 0,
        "top": 34,
        "adjusted": False,
    }


def test_align_end_with_no_overflow_right_aligns_the_panel(position):
    assert position(**_opts(align="end")) == {
        "align": "end",
        "placement": "below",
        "left": -100,
        "top": 34,
        "adjusted": False,
    }


def test_start_align_overflowing_the_right_edge_flips_to_end(position):
    result = position(**_opts(trigger={"top": 100, "left": 850, "width": 100, "height": 30}))
    assert result["align"] == "end"
    assert result["left"] == -100
    assert result["adjusted"] is True


def test_end_align_overflowing_the_left_edge_flips_to_start(position):
    result = position(
        **_opts(align="end", trigger={"top": 100, "left": 20, "width": 100, "height": 30})
    )
    assert result["align"] == "start"
    assert result["left"] == 0
    assert result["adjusted"] is True
