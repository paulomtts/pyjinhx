"""The vendored d3 subset the graph engine builds on (pjx_graph/src/d3.vendor.js).

The static checks read the committed bytes. The behaviour checks evaluate the
real minified file in chromium, since string-matching minified identifiers
proves nothing about what the bundle actually defines.
"""

from __future__ import annotations

from collections.abc import Iterator
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
    / "pjx_graph"
    / "src"
    / "d3.vendor.js"
)

BUNDLED = {
    "d3-selection": "3.0.0",
    "d3-zoom": "3.0.0",
    "d3-dispatch": "3.0.1",
    "d3-drag": "3.0.0",
    "d3-interpolate": "3.0.1",
    "d3-color": "3.1.0",
    "d3-transition": "3.0.1",
    "d3-timer": "3.0.1",
    "d3-ease": "3.0.1",
}

BODY_START = "var __pjxD3="


def _header_and_body() -> tuple[str, str]:
    text = SOURCE.read_text(encoding="utf-8")
    start = text.index("\n" + BODY_START) + 1
    return text[:start], text[start:]


@pytest.fixture(autouse=True)
def _require_chromium(request: pytest.FixtureRequest) -> None:
    # Function-scoped so a missing browser skips only the tests that ask for
    # a page, mirroring tests/pyjinhx/client/conftest.py.
    if "page" not in set(request.fixturenames):
        return
    pytest.importorskip("playwright")
    browser_type: Any = request.getfixturevalue("browser_type")
    if not Path(browser_type.executable_path).exists():
        pytest.skip(
            "chromium is not installed (run: uv run playwright install chromium)"
        )


@pytest.fixture
def d3_page(page: Page) -> Iterator[Page]:
    """A blank page with the vendored file loaded as a classic script."""
    page.set_content(
        '<body><div id="canvas" style="width:400px;height:300px"></div></body>'
    )
    page.add_script_tag(content=SOURCE.read_text(encoding="utf-8"))
    yield page


def test_vendored_file_exists():
    assert SOURCE.is_file()


def test_first_line_names_pins_and_licence():
    first_line = SOURCE.read_text(encoding="utf-8").split("\n", 1)[0]
    assert first_line == (
        "/* d3-selection 3.0.0 + d3-zoom 3.0.0"
        " — vendored by scripts/vendor_d3_zoom.py (ISC) */"
    )


def test_header_lists_every_bundled_package_with_version():
    header, _ = _header_and_body()
    for name, version in BUNDLED.items():
        assert f"{name} {version}\n" in header


def test_header_carries_isc_licence_text():
    header, _ = _header_and_body()
    assert "ISC" in header
    assert "Copyright" in header
    assert "Mike Bostock" in header
    assert "Permission to use, copy, modify, and/or distribute" in header


def test_header_is_only_comments():
    header, _ = _header_and_body()
    assert header.startswith("/*")
    assert header.endswith("*/\n")
    # Between the first line and the licence block nothing but comment text.
    assert header.count("/*") == header.count("*/") == 2


def test_body_is_a_single_private_iife_binding():
    _, body = _header_and_body()
    assert body.startswith(BODY_START + "(()=>{")
    assert body.endswith("})();\n")
    assert body.count("\n") == 1


def test_body_within_size_target():
    _, body = _header_and_body()
    assert len(body.encode("utf-8")) <= 61_440


def test_no_sourcemap_umd_or_global_d3():
    text = SOURCE.read_text(encoding="utf-8")
    for forbidden in (
        "sourceMappingURL",
        "define(",
        "module.exports",
        "window.d3",
        "globalThis.d3",
    ):
        assert forbidden not in text


def test_file_is_lf_only():
    assert b"\r" not in SOURCE.read_bytes()


def test_exposes_exactly_the_engine_surface(d3_page):
    kinds = d3_page.evaluate(
        "Object.fromEntries(Object.keys(__pjxD3).map(k => [k, typeof __pjxD3[k]]))"
    )
    assert kinds == {
        "select": "function",
        "pointer": "function",
        "zoom": "function",
        "zoomIdentity": "object",
        "zoomTransform": "function",
    }


def test_does_not_define_global_d3(d3_page):
    assert d3_page.evaluate("typeof window.d3") == "undefined"


def test_zoom_identity_builds_transforms(d3_page):
    assert (
        d3_page.evaluate("__pjxD3.zoomIdentity.translate(10, 20).scale(2).toString()")
        == "translate(10,20) scale(2)"
    )


def test_zoom_installs_on_an_element_and_reads_back_identity(d3_page):
    transform = d3_page.evaluate(
        """() => {
            const el = document.getElementById("canvas");
            __pjxD3.select(el).call(__pjxD3.zoom());
            const t = __pjxD3.zoomTransform(el);
            return {k: t.k, x: t.x, y: t.y};
        }"""
    )
    assert transform == {"k": 1, "x": 0, "y": 0}


def test_selection_has_transition_side_effect(d3_page):
    assert (
        d3_page.evaluate(
            'typeof __pjxD3.select(document.getElementById("canvas")).transition'
        )
        == "function"
    )


def test_evaluating_twice_does_not_throw(d3_page):
    d3_page.add_script_tag(content=SOURCE.read_text(encoding="utf-8"))
    assert d3_page.evaluate("typeof __pjxD3.zoom") == "function"


def test_binding_stays_local_inside_a_function_wrapper(page: Page):
    page.set_content("<body></body>")
    source = SOURCE.read_text(encoding="utf-8")
    page.add_script_tag(
        content=f"window.__wrapped = (function(){{\n{source}\n;return typeof __pjxD3;}})();"
    )
    assert page.evaluate("window.__wrapped") == "object"
    assert page.evaluate("typeof window.__pjxD3") == "undefined"
