"""Dragging a node of a mounted stage, and the position it keeps, in real chromium.

A drag is real pointer events over laid-out boxes, scaled by d3-zoom's
transform, and its drop persists through real localStorage across a reload,
so every stage is served from a real origin with the graph CSS applied.
Stages start from a persisted identity view unless a test says otherwise,
so the node sits at its data coordinates and a pointer pixel is a world
pixel. A document-level recorder installed before the asset runs logs every
graph event a drag could fire, which also proves they bubble.
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
RECORD = "pjx-graph:flow"
IDENTITY_VIEW = {"x": 0, "y": 0, "k": 1}

# Recorded at dispatch, from before the asset runs.
EVENTS = """window.__events = [];
['move', 'rendered', 'before-select', 'select', 'deselect'].forEach(
    (name) => document.addEventListener('pjx:graph:' + name, (event) => window.__events.push({
        type: name, detail: event.detail, target: event.target.id,
        cancelable: event.cancelable})));"""

POSITION = """id => {
    const style = document.getElementById(id).style;
    return [style.getPropertyValue('--pjx-graph-node-x'),
            style.getPropertyValue('--pjx-graph-node-y')];
}"""


def _node(
    node_id: str = "n1", x: float = 100, y: float = 100, stage_id: str = "g", **kw
):
    kw.setdefault("title", "Start")
    return PJXGraphNode(id=f"{stage_id}-{node_id}", node_id=node_id, x=x, y=y, **kw)


def _start(stage_id: str = "g", **kw) -> PJXGraphNode:
    """The default node: n1 at (100, 100) with an in-port and the out-port ok."""
    return _node(stage_id=stage_id, in_port=True, out_ports=("ok",), **kw)


def _stage(session, nodes=None, stage_id: str = "g", edges=None, **graph) -> str:
    if nodes is None:
        nodes = [_start(stage_id)]
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


def _seed(page: Page, record: dict | str, key: str = RECORD) -> None:
    """Store record under key before the page's own scripts run, on the first load only.

    sessionStorage remembers the seed, so a reload sees what the page itself stored.
    """
    raw = record if isinstance(record, str) else json.dumps(record)
    page.add_init_script(
        f"if (!sessionStorage.getItem('seeded:' + {json.dumps(key)})) {{"
        f" localStorage.setItem({json.dumps(key)}, {json.dumps(raw)});"
        f" sessionStorage.setItem('seeded:' + {json.dumps(key)}, '1'); }}"
    )


def _serve(
    page: Page,
    body: str,
    css: str = "",
    record: dict | str | None = None,
    init: str = "",
) -> None:
    """Seed record (an identity view by default), run init, record graph events, load body.

    init runs after the seed, so a script that breaks storage leaves the seed alone.
    """
    _seed(page, {"view": IDENTITY_VIEW} if record is None else record)
    if init:
        page.add_init_script(init)
    page.add_init_script(EVENTS)
    asset = ASSET.read_text(encoding="utf-8")
    html = (
        f"<html><head><style>{CSS}{css}</style></head>"
        f"<body>{body}<script>{asset}</script></body></html>"
    )
    page.route(URL, lambda route: route.fulfill(body=html, content_type="text/html"))
    page.goto(URL)
    _wait_ready(page)


def _wait_ready(page: Page) -> None:
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


def _position(page: Page, element_id: str = "g-n1") -> list[str]:
    return page.evaluate(POSITION, element_id)


def _raw(page: Page) -> str | None:
    return page.evaluate("key => localStorage.getItem(key)", RECORD)


def _record(page: Page) -> dict:
    raw = _raw(page)
    assert raw is not None
    return json.loads(raw)


def _center(page: Page, selector: str) -> tuple[int, int]:
    box = page.locator(selector).bounding_box()
    assert box is not None
    return round(box["x"] + box["width"] / 2), round(box["y"] + box["height"] / 2)


def _press(page: Page, at: tuple[int, int], dx: float = 60, dy: float = 40) -> None:
    """Press at a point and move by (dx, dy) without releasing."""
    x, y = at
    page.mouse.move(x, y)
    page.mouse.down()
    page.mouse.move(x + dx, y + dy, steps=4)


def _drag(page: Page, at: tuple[int, int], dx: float = 60, dy: float = 40) -> None:
    _press(page, at, dx, dy)
    page.mouse.up()


def _title(element_id: str = "g-n1") -> str:
    return f"#{element_id} .pjx-graph__node-title"


def _move(node_id: str, x: float, y: float, target: str = "g") -> dict:
    return {
        "type": "move",
        "detail": {"id": node_id, "x": x, "y": y},
        "target": target,
        "cancelable": False,
    }


def _reload(page: Page) -> None:
    page.reload()
    _wait_ready(page)


# Moving


def test_dragging_a_node_by_its_body_moves_it_by_the_pointer_delta(
    page, page_errors, session
):
    _serve(page, _keyed(session))
    _drag(page, _center(page, _title()))
    assert _position(page) == ["160px", "140px"]
    data = page.evaluate(
        "() => { const n = document.getElementById('g-n1');"
        " return [Number(n.dataset.x), Number(n.dataset.y)]; }"
    )
    assert data == [100, 100]
    assert page_errors == []


def test_the_node_moves_before_the_release(page, page_errors, session):
    _serve(page, _keyed(session))
    _press(page, _center(page, _title()))
    assert _position(page) == ["160px", "140px"]
    page.mouse.up()
    assert page_errors == []


def test_the_release_fires_one_move_event_that_bubbles(page, page_errors, session):
    _serve(page, _keyed(session))
    _drag(page, _center(page, _title()))
    assert _events(page, "move") == [_move("n1", 160, 140)]
    assert page_errors == []


def test_a_press_that_moves_four_pixels_or_less_is_a_click(page, page_errors, session):
    _serve(page, _keyed(session))
    _drag(page, _center(page, _title()), dx=3, dy=2)
    assert _events(page, "move", "before-select", "select") == [
        {
            "type": "before-select",
            "detail": {"id": "n1"},
            "target": "g",
            "cancelable": True,
        },
        {"type": "select", "detail": {"id": "n1"}, "target": "g", "cancelable": False},
    ]
    assert _position(page) == ["100px", "100px"]
    assert _record(page) == {"view": IDENTITY_VIEW}
    assert page_errors == []


def test_a_zoomed_stage_moves_the_node_by_the_delta_over_the_scale(
    page, page_errors, session
):
    _serve(page, _keyed(session), record={"view": {"x": 0, "y": 0, "k": 2}})
    _drag(page, _center(page, _title()))
    assert _position(page) == ["130px", "120px"]
    assert _events(page, "move") == [_move("n1", 130, 120)]
    assert page_errors == []


def test_a_drag_does_not_pan_the_stage(page, page_errors, session):
    _serve(page, _keyed(session))
    _drag(page, _center(page, _title()))
    transform = page.evaluate(
        "() => document.querySelector('#g .pjx-graph__viewport').style.transform"
    )
    assert transform == "translate(0px, 0px) scale(1)"
    assert page_errors == []


def test_a_release_outside_the_canvas_ends_the_drag_once(page, page_errors, session):
    _serve(page, _keyed(session) + "<div style='height:400px'></div>")
    canvas = page.locator("#g > .pjx-graph__canvas").bounding_box()
    assert canvas is not None
    x, y = _center(page, _title())
    below = canvas["y"] + canvas["height"] + 40
    _drag(page, (x, y), dx=0, dy=below - y)
    assert len(_events(page, "move")) == 1
    page.mouse.move(x + 200, below + 20)
    assert len(_events(page, "move")) == 1
    assert page_errors == []


def test_a_release_outside_the_canvas_leaves_the_next_click_alone(
    page, page_errors, session
):
    nodes = [_start(), _node("n2", 500, 100, title="Other")]
    _serve(page, _keyed(session, nodes) + "<div style='height:400px'></div>")
    canvas = page.locator("#g > .pjx-graph__canvas").bounding_box()
    assert canvas is not None
    x, y = _center(page, _title())
    _drag(page, (x, y), dx=0, dy=canvas["y"] + canvas["height"] + 40 - y)
    page.mouse.click(*_center(page, _title("g-n2")))
    assert [e["type"] for e in _events(page, "before-select", "select")] == [
        "before-select",
        "select",
    ]
    assert page_errors == []


def test_a_drag_swallows_only_its_own_trailing_click(page, page_errors, session):
    _serve(page, _keyed(session))
    _drag(page, _center(page, _title()))
    assert _events(page, "before-select", "select", "deselect") == []
    assert (
        page.evaluate(
            "() => document.querySelectorAll('.pjx-graph__node--selected').length"
        )
        == 0
    )
    page.mouse.click(*_center(page, _title()))
    assert [e["type"] for e in _events(page, "before-select", "select")] == [
        "before-select",
        "select",
    ]
    assert page_errors == []


def test_a_drag_keeps_the_current_selection(page, page_errors, session):
    nodes = [_start(), _node("n2", 500, 300, title="Other")]
    _serve(page, _keyed(session, nodes))
    page.click("#g-n2")
    _forget(page)
    _drag(page, _center(page, _title()))
    assert _events(page, "before-select", "select", "deselect") == []
    assert page.evaluate(
        "() => Array.from(document.querySelectorAll('.pjx-graph__node--selected'))"
        ".map((n) => n.id)"
    ) == ["g-n2"]
    assert page_errors == []


def test_a_drag_selects_no_page_text(page, page_errors, session):
    _serve(page, "<p id='words'>Some words to select</p>" + _keyed(session))
    words = page.locator("#words").bounding_box()
    assert words is not None
    x, y = _center(page, _title())
    # Up and over the paragraph above the stage, which a text drag would select.
    _drag(page, (x, y), dx=words["x"] + 2 - x, dy=words["y"] + 4 - y)
    assert page.evaluate("() => window.getSelection().toString()") == ""
    assert len(_events(page, "move")) == 1
    assert page_errors == []


# What does not drag


@pytest.mark.parametrize(
    "selector",
    ['#g-n1 [data-pjx-graph-port="in"]', '#g-n1 [data-pjx-graph-port="out"]'],
    ids=["in-port", "out-port"],
)
def test_pressing_a_port_does_not_move_the_node(page, page_errors, session, selector):
    _serve(page, _keyed(session))
    _drag(page, _center(page, selector))
    assert _position(page) == ["100px", "100px"]
    assert _events(page, "move") == []
    assert page_errors == []


@pytest.mark.parametrize(
    "control",
    [
        '<input id="ctl" value="some text here">',
        '<a id="ctl" href="#x">a link</a>',
        '<button id="ctl" type="button">Go</button>',
    ],
    ids=["input", "link", "button"],
)
def test_pressing_a_control_inside_a_node_does_not_move_it(
    page, page_errors, session, control
):
    _serve(page, _keyed(session, [_start(icon=Markup(control))]))
    _drag(page, _center(page, "#ctl"))
    assert _position(page) == ["100px", "100px"]
    assert _events(page, "move") == []
    assert page_errors == []


def test_an_input_inside_a_node_still_takes_typing(page, page_errors, session):
    _serve(page, _keyed(session, [_start(icon=Markup('<input id="ctl">'))]))
    page.click("#ctl")
    page.keyboard.type("hi")
    assert page.input_value("#ctl") == "hi"
    assert page_errors == []


@pytest.mark.parametrize("value", ["", "abc"], ids=["blank", "not-a-number"])
def test_a_node_without_a_server_position_is_not_draggable(
    page, page_errors, session, value
):
    html = _keyed(session).replace('data-x="100.0"', f'data-x="{value}"')
    assert f'data-x="{value}"' in html
    _serve(page, html)
    before = _position(page)
    _drag(page, _center(page, _title()))
    assert _position(page) == before
    assert _events(page, "move") == []
    assert _record(page) == {"view": IDENTITY_VIEW}
    page.click(_title())
    assert [e["type"] for e in _events(page, "select")] == ["select"]
    assert page_errors == []


NESTED_CSS = (
    "#g-a { width: 700px; } #in { width: 600px; }"
    " #in > .pjx-graph__canvas { min-height: 0; height: 200px; }"
)


def _nested(page: Page, session) -> str:
    """Stage g whose node a (at 20, 20) holds stage in with its node x at (10, 10).

    Both stages start from an identity view.
    """
    inner = _stage(
        session, [_node("x", 10, 10, "in", title="Inner")], "in", storage_key="inner"
    )
    _seed(page, {"view": IDENTITY_VIEW}, key="pjx-graph:inner")
    return _keyed(session, [_node("a", 20, 20, icon=Markup(inner), title="Outer")])


def test_dragging_a_nested_stage_node_moves_only_that_node(page, page_errors, session):
    _serve(page, _nested(page, session), NESTED_CSS)
    _drag(page, _center(page, _title("in-x")))
    assert _position(page, "in-x") == ["70px", "50px"]
    assert _position(page, "g-a") == ["20px", "20px"]
    assert _events(page, "move") == [_move("x", 70, 50, target="in")]
    assert page_errors == []


def test_a_press_on_a_nested_stage_background_does_not_move_the_outer_node(
    page, page_errors, session
):
    _serve(page, _nested(page, session), NESTED_CSS)
    box = page.locator("#in > .pjx-graph__canvas").bounding_box()
    assert box is not None
    _drag(page, (round(box["x"] + 400), round(box["y"] + 150)))
    assert _position(page, "g-a") == ["20px", "20px"]
    assert _events(page, "move") == []
    assert page_errors == []


# Edges

# The d of the visible path a stage's own plane draws for an edge id.
EDGE_D = """([stage, id]) => Array.from(document.querySelectorAll('#' + stage
    + ' > .pjx-graph__canvas > .pjx-graph__viewport > svg.pjx-graph__edge-plane'
    + ' > path.pjx-graph__edge'))
    .find((path) => path.getAttribute('data-edge-id') === id).getAttribute('d')"""

OUT_ANCHOR = """([stage, id, port]) =>
    pjx.graph.get(document.getElementById(stage)).outAnchor(id, port)"""

# The screen point halfway along the stage's first edge hit path.
EDGE_POINT = """() => {
    const hit = document.querySelector('#g path.pjx-graph__edge-hit');
    const mid = hit.getPointAtLength(hit.getTotalLength() / 2);
    const at = new DOMPoint(mid.x, mid.y).matrixTransform(hit.getScreenCTM());
    return [at.x, at.y];
}"""

MARKED = "() => document.querySelectorAll('#g path.pjx-graph__edge--selected').length"

NUMBER = re.compile(r"-?\d+(?:\.\d+)?(?:e[-+]?\d+)?")


def _linked(session) -> str:
    """n1 at (100, 100) wired from its ok port to n2 at (500, 100)."""
    nodes = [_start(), _node("n2", 500, 100, in_port=True, title="End")]
    edges = [{"id": "e1", "from": "n1", "to": "n2", "port": "ok"}]
    return _keyed(session, nodes, edges=edges)


def _numbers(d: str) -> list[float]:
    return [float(n) for n in NUMBER.findall(d)]


def test_an_edge_follows_the_dragged_node_without_a_rendered_event(
    page, page_errors, session
):
    _serve(page, _linked(session))
    before = page.evaluate(EDGE_D, ["g", "e1"])
    rendered = len(_events(page, "rendered"))
    _press(page, _center(page, _title()))
    during = page.evaluate(EDGE_D, ["g", "e1"])
    anchor = page.evaluate(OUT_ANCHOR, ["g", "n1", "ok"])
    assert during != before
    assert _numbers(during)[:2] == pytest.approx([anchor["x"], anchor["y"]], abs=0.01)
    page.mouse.up()
    assert len(_events(page, "rendered")) == rendered
    assert page_errors == []


def test_a_selected_edge_stays_marked_through_a_drag(page, page_errors, session):
    _serve(page, _linked(session))
    page.mouse.click(*page.evaluate(EDGE_POINT))
    assert page.evaluate(MARKED) == 1
    _press(page, _center(page, _title()))
    assert page.evaluate(MARKED) == 1
    page.mouse.up()
    assert page.evaluate(MARKED) == 1
    assert page_errors == []


# Persistence

STORED = {"x": 160, "y": 140, "base": {"x": 100, "y": 100}}


def test_a_drop_is_stored_with_the_server_position_as_its_base(
    page, page_errors, session
):
    _serve(page, _keyed(session))
    _drag(page, _center(page, _title()))
    assert _record(page) == {"view": IDENTITY_VIEW, "nodes": {"n1": STORED}}
    assert page_errors == []


def test_a_drop_keeps_the_record_other_fields(page, page_errors, session):
    other = {"x": 1, "y": 2, "base": {"x": 3, "y": 4}}
    _serve(
        page,
        _keyed(session),
        record={"view": IDENTITY_VIEW, "nodes": {"gone": other}, "extra": [1]},
    )
    _drag(page, _center(page, _title()))
    record = _record(page)
    assert record["extra"] == [1]
    assert record["view"] == IDENTITY_VIEW
    assert record["nodes"] == {"gone": other, "n1": STORED}
    assert page_errors == []


@pytest.mark.parametrize("nodes", [None, [1, 2], "n1"], ids=["null", "array", "string"])
def test_a_drop_replaces_unusable_nodes_with_an_object(
    page, page_errors, session, nodes
):
    _serve(page, _keyed(session), record={"view": IDENTITY_VIEW, "nodes": nodes})
    _drag(page, _center(page, _title()))
    assert _record(page) == {"view": IDENTITY_VIEW, "nodes": {"n1": STORED}}
    assert page_errors == []


@pytest.mark.parametrize("node_id", ["__proto__", "constructor"])
def test_a_prototype_named_id_is_stored_as_its_own_key(
    page, page_errors, session, node_id
):
    _serve(page, _keyed(session, [_node(node_id, title="Odd")]))
    _drag(page, _center(page, _title(f"g-{node_id}")))
    assert _events(page, "move") == [_move(node_id, 160, 140)]
    assert _record(page)["nodes"] == {node_id: STORED}
    assert page.evaluate("() => Object.getPrototypeOf({}) === Object.prototype")
    assert page_errors == []


def test_without_a_storage_key_a_drag_never_persists(page, page_errors, session):
    _serve(page, _stage(session), record="")
    page.evaluate("() => localStorage.clear()")
    _drag(page, _center(page, _title()))
    assert _position(page) != ["100px", "100px"]
    assert len(_events(page, "move")) == 1
    assert page.evaluate("() => localStorage.length") == 0
    _reload(page)
    assert _position(page) == ["100px", "100px"]
    assert page_errors == []


def test_broken_storage_still_drags_and_fires_move(page, page_errors, session):
    broken = (
        "Storage.prototype.setItem = () => { throw new Error('quota'); };"
        "Storage.prototype.getItem = () => { throw new Error('denied'); };"
    )
    _serve(page, _keyed(session), init=broken)
    # Nothing is readable, so the stage was fit; the delta scales by its k.
    k = page.evaluate(
        "() => new DOMMatrix(getComputedStyle("
        "document.querySelector('#g .pjx-graph__viewport')).transform).a"
    )
    _drag(page, _center(page, _title()))
    x, y = round(100 + 60 / k), round(100 + 40 / k)
    assert _position(page) == [f"{x}px", f"{y}px"]
    assert _events(page, "move") == [_move("n1", x, y)]
    assert page_errors == []


# Placing stored drops at mount


def test_a_drop_survives_a_reload(page, page_errors, session):
    _serve(page, _keyed(session))
    _drag(page, _center(page, _title()))
    _reload(page)
    assert _position(page) == ["160px", "140px"]
    assert _record(page) == {"view": IDENTITY_VIEW, "nodes": {"n1": STORED}}
    assert page_errors == []


def test_an_unchanged_server_position_keeps_the_drop(page, page_errors, session):
    seeded = json.dumps(
        {
            "view": IDENTITY_VIEW,
            "nodes": {"n1": {"x": 40, "y": 30, "base": {"x": 100, "y": 100}}},
        }
    )
    _serve(page, _keyed(session), record=seeded)
    assert _position(page) == ["40px", "30px"]
    assert _raw(page) == seeded
    assert page_errors == []


def test_a_dragged_drop_starts_from_where_it_shows(page, page_errors, session):
    nodes = {"n1": {"x": 40, "y": 30, "base": {"x": 100, "y": 100}}}
    _serve(page, _keyed(session), record={"view": IDENTITY_VIEW, "nodes": nodes})
    _drag(page, _center(page, _title()))
    assert _events(page, "move") == [_move("n1", 100, 70)]
    assert page_errors == []


def test_a_changed_server_position_discards_the_drop(page, page_errors, session):
    nodes = {
        "n1": {"x": 40, "y": 30, "base": {"x": 50, "y": 50}},
        "absent": {"x": 1, "y": 2, "base": {"x": 3, "y": 4}},
    }
    _serve(page, _keyed(session), record={"view": IDENTITY_VIEW, "nodes": nodes})
    assert _position(page) == ["100px", "100px"]
    assert _record(page) == {
        "view": IDENTITY_VIEW,
        "nodes": {"absent": nodes["absent"]},
    }
    assert page_errors == []


@pytest.mark.parametrize(
    "override",
    [
        {"x": "a"},
        {"x": 1, "y": 2},
        {"x": 1, "y": 2, "base": None},
        {"x": 1, "y": 2, "base": {"x": "100", "y": 100}},
        None,
        7,
    ],
    ids=["text-x", "no-base", "null-base", "text-base", "null", "number"],
)
def test_a_malformed_drop_is_ignored_and_discarded(
    page, page_errors, session, override
):
    _serve(
        page,
        _keyed(session),
        record={"view": IDENTITY_VIEW, "nodes": {"n1": override}},
    )
    assert _position(page) == ["100px", "100px"]
    assert _record(page) == {"view": IDENTITY_VIEW, "nodes": {}}
    assert page_errors == []


@pytest.mark.parametrize("node_id", ["__proto__", "constructor"])
def test_a_prototype_named_id_restores_across_a_reload(
    page, page_errors, session, node_id
):
    _serve(page, _keyed(session, [_node(node_id, title="Odd")]))
    _drag(page, _center(page, _title(f"g-{node_id}")))
    _reload(page)
    assert _position(page, f"g-{node_id}") == ["160px", "140px"]
    assert _record(page)["nodes"] == {node_id: STORED}
    assert page_errors == []
