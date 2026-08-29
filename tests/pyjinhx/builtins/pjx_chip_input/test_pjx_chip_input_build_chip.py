"""window.pjx.buildChip(): the chip DOM builder, exposed for reuse.

An app composing its own chip-shaped UI (e.g. an async ref picker) needs the
same markup PJXChipInput builds internally. The function is DOM-bound, so the
tests run the real file in real chromium rather than asserting on source
strings — same approach as test_pjx_popover_position.py.
"""

from __future__ import annotations

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
    / "pjx_chip_input"
    / "pjx_chip_input.js"
)


@pytest.fixture(autouse=True)
def _require_chromium(request: pytest.FixtureRequest) -> None:
    if "chip_page" not in set(request.fixturenames):
        return
    pytest.importorskip("playwright")
    browser_type: Any = request.getfixturevalue("browser_type")
    if not Path(browser_type.executable_path).exists():
        pytest.skip(
            "chromium is not installed (run: uv run playwright install chromium)"
        )


@pytest.fixture
def chip_page(page: Page) -> Page:
    page.set_content('<body><div data-pjx-chip-input data-name="tags"></div></body>')
    page.add_script_tag(content=SOURCE.read_text())
    return page


def test_returns_a_chip_with_the_expected_shape(chip_page: Page):
    outer = chip_page.evaluate(
        "pjx.buildChip(document.querySelector('[data-pjx-chip-input]'), 'red').outerHTML"
    )
    assert 'data-pjx-chip=""' in outer
    assert 'class="pjx-chip-input__chip"' in outer
    assert '<span class="pjx-chip-input__label">red</span>' in outer
    assert '<input type="hidden" name="tags" value="red">' in outer
    assert 'data-pjx-chip-remove=""' in outer
    assert 'aria-label="Remove"' in outer


def test_honours_the_roots_remove_label(chip_page: Page):
    chip_page.evaluate(
        "document.querySelector('[data-pjx-chip-input]')"
        ".setAttribute('data-remove-label', 'Delete')"
    )
    outer = chip_page.evaluate(
        "pjx.buildChip(document.querySelector('[data-pjx-chip-input]'), 'x').outerHTML"
    )
    assert 'aria-label="Delete"' in outer


def test_appending_it_produces_a_working_chip_in_the_dom(chip_page: Page):
    chip_page.evaluate(
        "document.querySelector('[data-pjx-chip-input]')"
        ".appendChild(pjx.buildChip(document.querySelector('[data-pjx-chip-input]'), 'blue'))"
    )
    assert chip_page.query_selector("[data-pjx-chip]") is not None
    assert (
        chip_page.eval_on_selector('input[type="hidden"]', "el => el.value") == "blue"
    )
