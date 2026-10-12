"""Dragging a wire from a node's out-port to another node, in real chromium.

A wire is real pointer events, a release hit-tested with elementFromPoint
over laid-out boxes, and a ghost path in d3-zoom's world space, so every
stage is served from a real origin with the graph CSS applied. Stages start
from a persisted identity view unless a test says otherwise, so a pointer
pixel is a world pixel. A document-level recorder installed before the asset
runs logs every graph event a wire could fire, which also proves they bubble.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from markupsafe import Markup

from pyjinhx.builtins.ui.pjx_graph import PJXGraph
from pyjinhx.builtins.ui.pjx_graph_edges import PJXGraphEdges
from pyjinhx.builtins.ui.pjx_graph_node import PJXGraphNode
from pyjinhx.builtins.ui.pjx_graph_nodes import PJXGraphNodes
from pyjinhx.rendering import render

if TYPE_CHECKING:
    from playwright.sync_api import Page

UI = Path(__file__).resolve().parents[4] / "pyjinhx" / "builtins" / "ui"
ASSET = UI / "pjx_graph" / "pjx_graph.js"
CSS = (UI / "pjx_graph" / "pjx_graph.css").read_text(encoding="utf-8") + (
    UI / "pjx_graph_node" / "pjx_graph_node.css"
).read_text(encoding="utf-8")
URL = "http://pjx.test/"
IDENTITY_VIEW = {"x": 0, "y": 0, "k": 1}

# Recorded at dispatch, from before the asset runs.
EVENTS = """window.__events = [];
['wire', 'move', 'rendered', 'before-select', 'select', 'deselect'].forEach(
    (name) => document.addEventListener('pjx:graph:' + name, (event) => window.__events.push({
        type: name, detail: event.detail, target: event.target.id,
        cancelable: event.cancelable})));"""

# The ghost paths in a stage's own plane, never a nested stage's.
GHOSTS = """stage => Array.from(document.querySelectorAll('#' + stage
    + ' > .pjx-graph__canvas > .pjx-graph__viewport > svg.pjx-graph__edge-plane'
    + ' > path.pjx-graph__wire'))"""

# The world point under a client point, from the viewport's box and the scale.
WORLD = """([stage, x, y, k]) => {
    const rect = document.querySelector('#' + stage + ' > .pjx-graph__canvas'
        + ' > .pjx-graph__viewport').getBoundingClientRect();
    return [(x - rect.left) / k, (y - rect.top) / k];
}"""

POSITION = """id => {
    const style = document.getElementById(id).style;
    return [style.getPropertyValue('--pjx-graph-node-x'),
            style.getPropertyValue('--pjx-graph-node-y')];
}"""

TRANSFORM = "() => document.querySelector('#g .pjx-graph__viewport').style.transform"

SELECTED = (
    "() => Array.from(document.querySelectorAll('.pjx-graph__node--selected'))"
    ".map((n) => n.id)"
)

NUMBER = re.compile(r"-?\d+(?:\.\d+)?(?:e[-+]?\d+)?")


def _node(
    node_id: str = "n1", x: float = 100, y: float = 100, stage_id: str = "g", **kw
):
    kw.setdefault("title", "Start")
    return PJXGraphNode(id=f"{stage_id}-{node_id}", node_id=node_id, x=x, y=y, **kw)


def _pair(stage_id: str = "g", ports: tuple[str, ...] = ("ok",)) -> list:
    """n1 at (100, 100) with the given out-ports, and n2 at (400, 100) with an in-port."""
    return [
        _node(stage_id=stage_id, in_port=True, out_ports=ports),
        _node("n2", 400, 100, stage_id, in_port=True, title="End"),
    ]


def _stage(session, nodes=None, stage_id: str = "g", edges=None, **graph) -> str:
    if nodes is None:
        nodes = _pair(stage_id)
    if edges is not None:
        graph["edges"] = PJXGraphEdges(id=f"{stage_id}-edges", edges=edges)
    layer = PJXGraphNodes(
        id=f"{stage_id}-nodes",
        nodes_html=PJXGraphNodes.join(render(node, session) for node in nodes),
    )
    return render(PJXGraph(id=stage_id, nodes=layer, **graph), session)


def _keyed(session, nodes=None, **graph) -> str:
    """A stage under the flow storage key."""
    return _stage(session, nodes, storage_key="flow", **graph)


def _seed(page: Page, record: dict, key: str = "pjx-graph:flow") -> None:
    """Store record under key before the page's own scripts run."""
    page.add_init_script(
        f"localStorage.setItem({json.dumps(key)}, {json.dumps(json.dumps(record))});"
    )


def _serve(page: Page, body: str, css: str = "", view: dict | None = None) -> None:
    """Seed the view (identity by default), record graph events, load body."""
    _seed(page, {"view": IDENTITY_VIEW if view is None else view})
    page.add_init_script(EVENTS)
    asset = ASSET.read_text(encoding="utf-8")
    html = (
        f"<html><head><style>{CSS}{css}</style></head>"
        f"<body>{body}<script>{asset}</script></body></html>"
    )
    page.route(URL, lambda route: route.fulfill(body=html, content_type="text/html"))
    page.goto(URL)
    page.wait_for_function(
        """() => Array.from(document.querySelectorAll('[data-pjx-graph]'))
            .every(s => !pjx.graph.get(s) || s.hasAttribute('data-pjx-graph-ready'))""",
        timeout=5000,
    )


def _events(page: Page, *kinds: str) -> list[dict]:
    events = page.evaluate("() => window.__events")
    return [e for e in events if not kinds or e["type"] in kinds]


def _forget(page: Page) -> None:
    page.evaluate("() => { window.__events = []; }")


def _ghosts(page: Page, stage: str = "g") -> int:
    return page.evaluate(f"stage => ({GHOSTS})(stage).length", stage)


def _ghost_d(page: Page, stage: str = "g") -> str:
    return page.evaluate(f"stage => ({GHOSTS})(stage)[0].getAttribute('d')", stage)


def _numbers(d: str) -> list[float]:
    return [float(n) for n in NUMBER.findall(d)]


def _assert_ghost(page: Page, pointer: tuple[float, float], k: float = 1) -> None:
    """The ghost runs from the centre of n1's ok dot to the world point under pointer."""
    box = page.locator(_port()).bounding_box()
    assert box is not None
    dot = (box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
    numbers = _numbers(_ghost_d(page))
    assert numbers[:2] == pytest.approx(page.evaluate(WORLD, ["g", *dot, k]), abs=0.01)
    assert numbers[-2:] == pytest.approx(
        page.evaluate(WORLD, ["g", *pointer, k]), abs=0.01
    )


def _center(page: Page, selector: str) -> tuple[int, int]:
    box = page.locator(selector).bounding_box()
    assert box is not None
    return round(box["x"] + box["width"] / 2), round(box["y"] + box["height"] / 2)


def _port(element_id: str = "g-n1", key: str = "ok") -> str:
    return f'#{element_id} [data-pjx-graph-port="out"][data-port="{key}"]'


def _title(element_id: str = "g-n1") -> str:
    return f"#{element_id} .pjx-graph__node-title"


def _press(page: Page, start: tuple[int, int], end: tuple[int, int]) -> None:
    """Press at start and move to end in steps, without releasing."""
    page.mouse.move(*start)
    page.mouse.down()
    page.mouse.move(*end, steps=6)


def _wire(page: Page, start: tuple[int, int], end: tuple[int, int]) -> None:
    _press(page, start, end)
    page.mouse.up()


def _below(page: Page, stage: str = "g") -> tuple[int, int]:
    """A point under the stage's canvas, outside it."""
    box = page.locator(f"#{stage} > .pjx-graph__canvas").bounding_box()
    assert box is not None
    return round(box["x"] + 100), round(box["y"] + box["height"] + 40)


def _wired(source: str, port: str, target: str, stage: str = "g") -> dict:
    return {
        "type": "wire",
        "detail": {"from": source, "port": port, "to": target},
        "target": stage,
        "cancelable": False,
    }


# Firing the wire event


def test_dropping_a_wire_on_a_node_fires_one_wire_event_with_from_port_and_to(
    page, page_errors, session
):
    _serve(page, _keyed(session))
    _wire(page, _center(page, _port()), _center(page, _title("g-n2")))
    assert _events(page, "wire") == [_wired("n1", "ok", "n2")]
    assert page_errors == []


def test_the_wire_event_names_the_out_port_the_drag_started_from(
    page, page_errors, session
):
    _serve(page, _keyed(session, _pair(ports=("ok", "err"))))
    _wire(page, _center(page, _port(key="err")), _center(page, _title("g-n2")))
    assert _events(page, "wire") == [_wired("n1", "err", "n2")]
    assert page_errors == []


@pytest.mark.parametrize(
    "part",
    [".pjx-graph__node-title", '[data-pjx-graph-port="in"]', ".pjx-graph__node-body"],
    ids=["title", "in-port", "body"],
)
def test_dropping_on_any_part_of_a_node_wires_to_that_node(
    page, page_errors, session, part
):
    _serve(page, _keyed(session))
    _wire(page, _center(page, _port()), _center(page, f"#g-n2 {part}"))
    assert _events(page, "wire") == [_wired("n1", "ok", "n2")]
    assert page_errors == []


def test_dropping_a_wire_on_the_canvas_background_fires_nothing(
    page, page_errors, session
):
    _serve(page, _keyed(session))
    x, y = _center(page, _port())
    _wire(page, (x, y), (x + 30, y + 200))
    assert _events(page, "wire") == []
    assert page_errors == []


def test_dropping_a_wire_on_its_own_source_node_fires_nothing(
    page, page_errors, session
):
    _serve(page, _keyed(session))
    _wire(page, _center(page, _port()), _center(page, _title()))
    assert _events(page, "wire") == []
    assert page_errors == []


def test_dropping_a_wire_outside_the_canvas_fires_nothing(page, page_errors, session):
    _serve(page, _keyed(session) + "<div style='height:400px'></div>")
    _wire(page, _center(page, _port()), _below(page))
    assert _events(page, "wire") == []
    assert page_errors == []


def test_a_release_off_the_window_fires_nothing(page, page_errors, session):
    _serve(page, _keyed(session))
    _press(page, _center(page, _port()), _center(page, _title("g-n2")))
    page.evaluate(
        "() => window.dispatchEvent(new PointerEvent('pointerup',"
        " { pointerId: 1, clientX: -50, clientY: -50, bubbles: true }))"
    )
    assert _ghosts(page) == 0
    assert _events(page, "wire") == []
    page.mouse.up()
    assert page_errors == []


def test_pressing_an_in_port_starts_no_wire(page, page_errors, session):
    _serve(page, _keyed(session))
    _press(
        page, _center(page, '#g-n2 [data-pjx-graph-port="in"]'), _center(page, _title())
    )
    assert _ghosts(page) == 0
    page.mouse.up()
    assert _events(page, "wire") == []
    assert page_errors == []


def test_a_wire_drag_does_not_pan_the_stage_or_move_the_node(
    page, page_errors, session
):
    _serve(page, _keyed(session))
    _wire(page, _center(page, _port()), _center(page, _title("g-n2")))
    assert page.evaluate(TRANSFORM) == "translate(0px, 0px) scale(1)"
    assert page.evaluate(POSITION, "g-n1") == ["100px", "100px"]
    assert _events(page, "move") == []
    assert page_errors == []


def test_the_engine_never_creates_the_edge_a_wire_asks_for(page, page_errors, session):
    edges = [{"id": "e1", "from": "n1", "to": "n2", "port": "ok"}]
    _serve(page, _keyed(session, edges=edges))
    count = (
        "() => [document.querySelectorAll('#g [data-pjx-graph-edge]').length,"
        " document.querySelectorAll('#g path.pjx-graph__edge').length]"
    )
    before = page.evaluate(count)
    _forget(page)
    _wire(page, _center(page, _port()), _center(page, _title("g-n2")))
    assert len(_events(page, "wire")) == 1
    assert page.evaluate(count) == before == [1, 1]
    assert _events(page, "rendered") == []
    assert page_errors == []


# Nested stages

NESTED_CSS = (
    "#g-a { width: 700px; } #in { width: 600px; }"
    " #in > .pjx-graph__canvas { min-height: 0; height: 200px; }"
)


def _nested(page: Page, session) -> str:
    """Stage g: node a at (20, 20) holding stage in, and node s at (20, 300) with out-port ok.

    Stage in holds x at (10, 10) with out-port ok and y at (300, 10). Both
    stages start from an identity view.
    """
    inner = _stage(
        session,
        [
            _node("x", 10, 10, "in", out_ports=("ok",), title="Inner"),
            _node("y", 300, 10, "in", in_port=True, title="Other"),
        ],
        "in",
        storage_key="inner",
    )
    _seed(page, {"view": IDENTITY_VIEW}, key="pjx-graph:inner")
    return _keyed(
        session,
        [
            _node("a", 20, 20, icon=Markup(inner), title="Outer"),
            _node("s", 20, 300, out_ports=("ok",), title="Source"),
        ],
    )


def test_a_nested_stage_port_wires_only_within_its_own_stage(
    page, page_errors, session
):
    _serve(page, _nested(page, session), NESTED_CSS)
    _wire(page, _center(page, _port("in-x")), _center(page, _title("in-y")))
    assert _events(page, "wire") == [_wired("x", "ok", "y", stage="in")]
    _forget(page)
    _wire(page, _center(page, _port("in-x")), _center(page, _title("g-s")))
    assert _events(page, "wire") == []
    assert page_errors == []


def test_a_nested_stage_node_is_no_target_of_the_outer_stage(
    page, page_errors, session
):
    _serve(page, _nested(page, session), NESTED_CSS)
    _wire(page, _center(page, _port("g-s")), _center(page, _title("in-x")))
    assert _events(page, "wire") == []
    assert page_errors == []


# The ghost edge


def test_the_ghost_edge_follows_the_pointer_while_dragging(page, page_errors, session):
    _serve(page, _keyed(session))
    x, y = _center(page, _port())
    page.mouse.move(x, y)
    page.mouse.down()
    for pointer in [(x + 80, y + 60), (x + 150, y - 40)]:
        page.mouse.move(*pointer, steps=4)
        assert _ghosts(page) == 1
        _assert_ghost(page, pointer)
    page.mouse.up()
    assert page_errors == []


def test_the_ghost_edge_ends_at_the_pointer_on_a_zoomed_and_panned_stage(
    page, page_errors, session
):
    _serve(page, _keyed(session), view={"x": 30, "y": 20, "k": 2})
    x, y = _center(page, _port())
    _press(page, (x, y), (x + 60, y + 40))
    _assert_ghost(page, (x + 60, y + 40), k=2)
    page.mouse.up()
    assert page_errors == []


def test_the_ghost_edge_is_no_edge(page, page_errors, session):
    _serve(page, _keyed(session))
    x, y = _center(page, _port())
    _press(page, (x, y), (x + 80, y + 60))
    ghost = page.evaluate(
        f"() => {{ const g = ({GHOSTS})('g')[0];"
        " return [g.getAttribute('class'), g.hasAttribute('data-edge-id')]; }"
    )
    assert ghost == ["pjx-graph__wire", False]
    page.mouse.up()
    assert page_errors == []


@pytest.mark.parametrize("drop", ["node", "background"])
def test_the_ghost_edge_is_removed_after_a_drop(page, page_errors, session, drop):
    _serve(page, _keyed(session))
    x, y = _center(page, _port())
    end = _center(page, _title("g-n2")) if drop == "node" else (x + 30, y + 200)
    _press(page, (x, y), end)
    assert _ghosts(page) == 1
    page.mouse.up()
    assert _ghosts(page) == 0
    assert page_errors == []


def test_a_redraw_while_wiring_keeps_the_ghost_out_of_the_edges(
    page, page_errors, session
):
    edges = [{"id": "e1", "from": "n1", "to": "n2", "port": "ok"}]
    _serve(page, _keyed(session, edges=edges))
    x, y = _center(page, _port())
    _press(page, (x, y), (x + 80, y + 60))
    page.evaluate("() => pjx.graph.get(document.getElementById('g')).drawEdges()")
    assert _ghosts(page) == 1
    assert (
        page.evaluate(
            "() => document.querySelectorAll('#g path.pjx-graph__edge').length"
        )
        == 1
    )
    page.mouse.up()
    assert _ghosts(page) == 0
    assert page_errors == []


def test_a_press_on_an_out_port_that_moves_four_pixels_or_less_draws_and_fires_nothing(
    page, page_errors, session
):
    _serve(page, _keyed(session))
    x, y = _center(page, _port())
    _press(page, (x, y), (x + 3, y))
    assert _ghosts(page) == 0
    page.mouse.up()
    assert _events(page, "wire") == []
    assert page_errors == []


def test_a_cancelled_pointer_removes_the_ghost_and_fires_nothing(
    page, page_errors, session
):
    _serve(page, _keyed(session))
    _press(page, _center(page, _port()), _center(page, _title("g-n2")))
    page.evaluate(
        "() => window.dispatchEvent(new PointerEvent('pointercancel',"
        " { pointerId: 1, bubbles: true }))"
    )
    assert _ghosts(page) == 0
    page.mouse.up()
    assert _events(page, "wire") == []
    assert page_errors == []


def test_a_source_removed_mid_drag_drops_the_ghost_and_fires_nothing(
    page, page_errors, session
):
    _serve(page, _keyed(session))
    x, y = _center(page, _port())
    target = _center(page, _title("g-n2"))
    _press(page, (x, y), (x + 60, y + 40))
    page.evaluate("() => document.getElementById('g-n1').remove()")
    page.mouse.move(*target, steps=2)
    assert _ghosts(page) == 0
    page.mouse.up()
    assert _events(page, "wire") == []
    assert page_errors == []


# Selection and page text


def test_a_wire_drop_changes_no_selection(page, page_errors, session):
    _serve(page, _keyed(session))
    page.click(_title())
    _forget(page)
    x, y = _center(page, _port())
    _wire(page, (x, y), _center(page, _title("g-n2")))
    _wire(page, (x, y), (x + 30, y + 200))
    _wire(page, (x, y), _center(page, _title()))
    assert _events(page, "before-select", "select", "deselect") == []
    assert page.evaluate(SELECTED) == ["g-n1"]
    page.mouse.click(*_center(page, _title("g-n2")))
    assert [e["type"] for e in _events(page, "before-select", "select")] == [
        "before-select",
        "select",
    ]
    assert page.evaluate(SELECTED) == ["g-n2"]
    assert page_errors == []


def test_a_wire_drag_selects_no_page_text(page, page_errors, session):
    _serve(page, "<p id='words'>Some words to select</p>" + _keyed(session))
    words = page.locator("#words").bounding_box()
    assert words is not None
    _wire(page, _center(page, _port()), (round(words["x"] + 2), round(words["y"] + 4)))
    assert page.evaluate("() => window.getSelection().toString()") == ""
    assert page_errors == []


@pytest.mark.parametrize("ending", ["release", "cancel"])
def test_page_text_selects_again_after_a_wire_ends(page, page_errors, session, ending):
    _serve(page, _keyed(session) + "<p id='words'>Some words to select</p>")
    x, y = _center(page, _port())
    _press(page, (x, y), (x + 30, y + 200))
    if ending == "cancel":
        page.evaluate(
            "() => window.dispatchEvent(new PointerEvent('pointercancel',"
            " { pointerId: 1, bubbles: true }))"
        )
    page.mouse.up()
    words = page.locator("#words").bounding_box()
    assert words is not None
    middle = round(words["y"] + words["height"] / 2)
    page.mouse.move(round(words["x"] + 1), middle)
    page.mouse.down()
    page.mouse.move(round(words["x"] + words["width"] - 1), middle, steps=4)
    page.mouse.up()
    assert page.evaluate("() => window.getSelection().toString()") != ""
    assert page_errors == []
