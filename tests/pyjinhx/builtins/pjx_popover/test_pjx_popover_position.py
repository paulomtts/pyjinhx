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
    result = position(
        **_opts(trigger={"top": 100, "left": 850, "width": 100, "height": 30})
    )
    assert result["align"] == "end"
    assert result["left"] == -100
    assert result["adjusted"] is True


def test_end_align_overflowing_the_left_edge_flips_to_start(position):
    result = position(
        **_opts(
            align="end", trigger={"top": 100, "left": 20, "width": 100, "height": 30}
        )
    )
    assert result["align"] == "start"
    assert result["left"] == 0
    assert result["adjusted"] is True


def test_overflowing_the_bottom_flips_above_the_trigger(position):
    result = position(
        **_opts(trigger={"top": 700, "left": 100, "width": 100, "height": 30})
    )
    assert result["placement"] == "above"
    # Panel bottom sits one gap above the trigger top: -(150 + 4).
    assert result["top"] == -154
    assert result["adjusted"] is True


def test_no_room_above_or_below_stays_below_and_clamps_to_the_viewport(position):
    result = position(
        **_opts(
            trigger={"top": 300, "left": 100, "width": 100, "height": 30},
            panel={"width": 200, "height": 400},
            viewport={"width": 1000, "height": 500},
        )
    )
    assert result["placement"] == "below"
    # Clamped so the panel bottom lands on the padded viewport edge: 500-400-8=92
    # absolute, i.e. 92-300 relative to the trigger top.
    assert result["top"] == -208
    assert result["adjusted"] is True


def test_viewport_narrower_than_the_panel_clamps_to_the_left_padding(position):
    result = position(
        **_opts(
            trigger={"top": 100, "left": 40, "width": 100, "height": 30},
            panel={"width": 300, "height": 150},
            viewport={"width": 200, "height": 800},
        )
    )
    # Both sides overflow, so the clamp pins the panel at the left padding: 8-40.
    assert result["left"] == -32
    assert result["adjusted"] is True


def test_viewport_shorter_than_the_panel_clamps_to_the_top_padding(position):
    result = position(
        **_opts(
            trigger={"top": 60, "left": 100, "width": 100, "height": 30},
            panel={"width": 200, "height": 400},
            viewport={"width": 1000, "height": 300},
        )
    )
    assert result["top"] == 8 - 60
    assert result["adjusted"] is True


def test_the_source_never_reads_or_writes_the_dom(position):
    source = SOURCE.read_text()
    for forbidden in (
        "getBoundingClientRect",
        "document.",
        "window.innerWidth",
        ".style",
    ):
        assert forbidden not in source


def test_calling_it_does_not_mutate_the_options_object(position, page):
    page.evaluate(
        "window.__opts = {"
        "  trigger: { top: 700, left: 850, width: 100, height: 30 },"
        "  panel: { width: 200, height: 150 },"
        "  viewport: { width: 1000, height: 800 },"
        "  align: 'start'"
        "};"
        "window.__before = JSON.stringify(window.__opts);"
        "pjx.popoverPosition(window.__opts);"
    )
    assert page.evaluate("JSON.stringify(window.__opts) === window.__before") is True


def test_a_custom_gap_and_padding_are_honoured(position):
    assert position(**_opts(gap=10))["top"] == 40
    result = position(
        **_opts(
            trigger={"top": 100, "left": 40, "width": 100, "height": 30},
            panel={"width": 300, "height": 150},
            viewport={"width": 200, "height": 800},
            padding=0,
        )
    )
    assert result["left"] == -40
