"""The graph stylesheets follow the theme tokens, with light fallbacks, in real chromium.

Every stage is served with the four graph sheets and, where a test asks for
it, the theme sheet ahead of them. Values are read back with getComputedStyle,
so the tests see the real cascade: the light fallbacks with no theme sheet,
the theme's values with it, and app overrides on top of both.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from pyjinhx.builtins.ui.pjx_graph import PJXGraph
from pyjinhx.builtins.ui.pjx_graph_controls import PJXGraphControls
from pyjinhx.builtins.ui.pjx_graph_node import PJXGraphNode
from pyjinhx.builtins.ui.pjx_graph_nodes import PJXGraphNodes
from pyjinhx.builtins.ui.pjx_graph_side_panel import PJXGraphSidePanel
from pyjinhx.client import read_pjx_theme_css
from pyjinhx.rendering import render

if TYPE_CHECKING:
    from playwright.sync_api import Page

UI = Path(__file__).resolve().parents[4] / "pyjinhx" / "builtins" / "ui"
ASSET = UI / "pjx_graph" / "pjx_graph.js"
GRAPH_CSS = "".join(
    (UI / name / f"{name}.css").read_text(encoding="utf-8")
    for name in (
        "pjx_graph",
        "pjx_graph_node",
        "pjx_graph_controls",
        "pjx_graph_side_panel",
    )
)
URL = "http://pjx.test/"

CANVAS = "#g > .pjx-graph__canvas"
NODE = "#g-a"
CONTROLS = "#g-controls"
PANEL = "#g-panel"

WHITE = "rgb(255, 255, 255)"
BORDER = "rgb(228, 228, 231)"
TEXT = "rgb(24, 24, 27)"
MUTED = "rgb(82, 82, 91)"
DARK_SURFACE = "rgb(24, 24, 27)"
DARK_BORDER = "rgb(63, 63, 70)"
DARK_TEXT = "rgb(244, 244, 245)"
DARK_MUTED = "rgb(161, 161, 170)"

# Computed longhands of the first element matching the selector.
STYLE = """([selector, names]) => {
    const style = getComputedStyle(document.querySelector(selector));
    return Object.fromEntries(names.map((name) => [name, style.getPropertyValue(name)]));
}"""

# Whether the topmost element at the controls' centre is inside the panel.
PANEL_ON_TOP = """() => {
    const box = document.getElementById('g-controls').getBoundingClientRect();
    const hit = document.elementFromPoint(box.left + box.width / 2, box.top + box.height / 2);
    return hit !== null && hit.closest('.pjx-graph__panel') === document.getElementById('g-panel');
}"""


def _stage(session) -> str:
    """Stage g with one node (eyebrow, summary, in-port), the controls and an open panel."""
    node = PJXGraphNode(
        id="g-a",
        node_id="a",
        x=10,
        y=10,
        title="Start",
        eyebrow="Step",
        summary="First",
        in_port=True,
    )
    layer = PJXGraphNodes(id="g-nodes", nodes_html=node)
    controls = PJXGraphControls(id="g-controls")
    panel = PJXGraphSidePanel(id="g-panel", title="Details", open=True)
    return render(
        PJXGraph(id="g", nodes=layer, controls=controls, panel=panel), session
    )


def _serve(
    page: Page, body: str, *, theme: bool = False, root: str = "", css: str = ""
) -> None:
    """Load body with the graph sheets (the theme sheet first when asked) and wait.

    root is raw attribute text for the <html> element, such as
    ' data-pjx-theme="dark"'; css is appended after the graph sheets.
    """
    sheets = (read_pjx_theme_css() if theme else "") + GRAPH_CSS + css
    asset = ASSET.read_text(encoding="utf-8")
    html = (
        f"<html{root}><head><style>{sheets}</style></head>"
        f"<body>{body}<script>{asset}</script></body></html>"
    )
    page.route(URL, lambda route: route.fulfill(body=html, content_type="text/html"))
    page.goto(URL)
    page.wait_for_function(
        """() => Array.from(document.querySelectorAll('[data-pjx-graph]'))
            .every(s => !pjx.graph.get(s) || s.hasAttribute('data-pjx-graph-ready'))""",
        timeout=5000,
    )


def _style(page: Page, selector: str, *names: str) -> dict[str, str]:
    return page.evaluate(STYLE, [selector, list(names)])


def test_without_the_theme_sheet_the_graph_takes_the_light_values(
    page, page_errors, session
):
    _serve(page, _stage(session))

    assert _style(
        page,
        CANVAS,
        "background-color",
        "border-top-color",
        "border-top-left-radius",
    ) == {
        "background-color": WHITE,
        "border-top-color": BORDER,
        "border-top-left-radius": "8px",
    }
    assert BORDER in _style(page, CANVAS, "background-image")["background-image"]
    assert _style(
        page,
        NODE,
        "color",
        "background-color",
        "border-top-color",
        "border-top-left-radius",
        "column-gap",
        "padding-top",
        "padding-right",
    ) == {
        "color": TEXT,
        "background-color": WHITE,
        "border-top-color": BORDER,
        "border-top-left-radius": "8px",
        "column-gap": "8px",
        "padding-top": "10px",
        "padding-right": "12px",
    }
    assert _style(page, f"{NODE} .pjx-graph__node-body", "row-gap") == {
        "row-gap": "2px"
    }
    assert _style(page, f"{NODE} .pjx-graph__node-eyebrow", "font-size", "color") == {
        "font-size": "12px",
        "color": MUTED,
    }
    assert _style(
        page, f"{NODE} .pjx-graph__node-title", "font-size", "font-weight"
    ) == {"font-size": "14px", "font-weight": "600"}
    assert _style(page, f"{NODE} .pjx-graph__node-summary", "font-size") == {
        "font-size": "12px"
    }
    assert _style(page, f"{NODE} .pjx-graph__port", "background-color") == {
        "background-color": WHITE
    }
    assert _style(page, CONTROLS, "z-index", "row-gap", "right", "bottom") == {
        "z-index": "10",
        "row-gap": "4px",
        "right": "12px",
        "bottom": "12px",
    }
    assert _style(
        page,
        f"{CONTROLS} .pjx-graph__control",
        "padding-top",
        "padding-left",
        "font-size",
        "color",
        "background-color",
        "border-top-color",
        "border-top-left-radius",
    ) == {
        "padding-top": "4px",
        "padding-left": "8px",
        "font-size": "12px",
        "color": MUTED,
        "background-color": WHITE,
        "border-top-color": BORDER,
        "border-top-left-radius": "8px",
    }
    assert _style(
        page,
        PANEL,
        "z-index",
        "top",
        "right",
        "color",
        "background-color",
        "border-top-color",
        "border-top-left-radius",
        "animation-duration",
        "animation-timing-function",
    ) == {
        "z-index": "11",
        "top": "12px",
        "right": "12px",
        "color": TEXT,
        "background-color": WHITE,
        "border-top-color": BORDER,
        "border-top-left-radius": "8px",
        "animation-duration": "0.15s",
        "animation-timing-function": "cubic-bezier(0.2, 0, 0, 1)",
    }
    assert _style(
        page, f"{PANEL} .pjx-graph__panel-head", "column-gap", "padding-top"
    ) == {"column-gap": "8px", "padding-top": "12px"}
    assert _style(page, f"{PANEL} .pjx-graph__panel-title", "font-size") == {
        "font-size": "14px"
    }
    assert _style(page, f"{PANEL} .pjx-graph__panel-control", "font-size", "color") == {
        "font-size": "12px",
        "color": MUTED,
    }
    assert page_errors == []


def test_the_dark_theme_on_the_root_reaches_the_graph(page, page_errors, session):
    _serve(page, _stage(session), theme=True, root=' data-pjx-theme="dark"')

    assert _style(page, CANVAS, "background-color", "border-top-color") == {
        "background-color": DARK_SURFACE,
        "border-top-color": DARK_BORDER,
    }
    assert _style(page, NODE, "color", "background-color") == {
        "color": DARK_TEXT,
        "background-color": DARK_SURFACE,
    }
    assert _style(page, f"{CONTROLS} .pjx-graph__control", "color") == {
        "color": DARK_MUTED
    }
    assert _style(page, PANEL, "background-color", "color", "z-index") == {
        "background-color": DARK_SURFACE,
        "color": DARK_TEXT,
        "z-index": "11",
    }
    assert _style(page, CONTROLS, "z-index") == {"z-index": "10"}
    assert page_errors == []


def test_dark_os_preference_reaches_the_graph(page, page_errors, session):
    page.emulate_media(color_scheme="dark")
    _serve(page, _stage(session), theme=True)

    assert _style(page, CANVAS, "background-color") == {
        "background-color": DARK_SURFACE
    }
    assert _style(page, NODE, "color") == {"color": DARK_TEXT}
    assert page_errors == []


def test_a_theme_token_override_reaches_the_graph_without_the_sheet(
    page, page_errors, session
):
    _serve(page, _stage(session), css=":root { --pjx-color-surface: rgb(1, 2, 3); }")

    assert _style(page, CANVAS, "background-color") == {
        "background-color": "rgb(1, 2, 3)"
    }
    assert _style(page, NODE, "background-color") == {
        "background-color": "rgb(1, 2, 3)"
    }
    assert page_errors == []


def test_a_component_token_override_beats_the_theme_token(page, page_errors, session):
    css = (
        ":root { --pjx-color-surface: rgb(1, 2, 3); }"
        ".pjx-graph { --pjx-graph-bg: rgb(4, 5, 6); }"
    )
    _serve(page, _stage(session), css=css)

    assert _style(page, CANVAS, "background-color") == {
        "background-color": "rgb(4, 5, 6)"
    }
    # Only the canvas token was overridden; the node still follows the theme token.
    assert _style(page, NODE, "background-color") == {
        "background-color": "rgb(1, 2, 3)"
    }
    assert page_errors == []


def test_an_open_panel_covers_the_controls_where_they_overlap(
    page, page_errors, session
):
    css = "#g-panel { top: 0; bottom: 0; max-height: none; }"
    _serve(page, _stage(session), css=css)

    assert page.evaluate(PANEL_ON_TOP) is True
    assert page_errors == []


def test_reduced_motion_still_clamps_the_open_animation(page, page_errors, session):
    page.emulate_media(reduced_motion="reduce")
    _serve(page, _stage(session))

    assert _style(page, PANEL, "animation-duration") == {"animation-duration": "1e-05s"}
    assert page_errors == []
