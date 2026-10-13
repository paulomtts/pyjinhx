"""Reconciling a mounted stage after the app swaps its DOM, in real chromium.

Edge ends are measured anchors, swaps are seen by a MutationObserver and
coalesced into an animation frame, so every stage is served from a real
origin with the graph CSS applied. Stages start from a persisted identity
view unless a test says otherwise, so nodes sit at their data coordinates
and a pointer pixel is a world pixel. Replacement markup is rendered by the
real components and injected with page.evaluate, as an htmx swap would.
A document-level recorder installed before the asset runs logs every graph
event, so a test waits on the rendered count instead of sleeping.
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
['rendered', 'move', 'wire', 'before-select', 'select', 'deselect'].forEach(
    (name) => document.addEventListener('pjx:graph:' + name, (event) => window.__events.push({
        type: name, detail: event.detail, target: event.target.id,
        cancelable: event.cancelable})));"""

POSITION = """id => {
    const style = document.getElementById(id).style;
    return [style.getPropertyValue('--pjx-graph-node-x'),
            style.getPropertyValue('--pjx-graph-node-y')];
}"""

# What a stage's own plane holds, in DOM order.
PLANE = """id => {
    const plane = document.querySelector('#' + id
        + ' > .pjx-graph__canvas > .pjx-graph__viewport > svg.pjx-graph__edge-plane');
    return Array.from(plane.children).map(el => ({
        tag: el.tagName, cls: el.getAttribute('class'), id: el.id,
        d: el.getAttribute('d'), edge: el.getAttribute('data-edge-id'),
        from: el.getAttribute('data-from'), to: el.getAttribute('data-to'),
        state: el.getAttribute('data-state')}));
}"""

# Each label in a stage's own plane as [edge id, shown text], in DOM order.
LABELS = """id => {
    const plane = document.querySelector('#' + id
        + ' > .pjx-graph__canvas > .pjx-graph__viewport > svg.pjx-graph__edge-plane');
    return Array.from(plane.querySelectorAll('.pjx-graph__edge-label'))
        .map(t => [t.getAttribute('data-edge-id'), t.textContent]);
}"""

CALL = """([id, method, args]) => {
    const instance = pjx.graph.get(document.getElementById(id));
    return instance[method](...args);
}"""

# Calls reconcile and reports what it returned, as a JSON-safe value.
RECONCILE = """id => {
    const result = pjx.graph.get(document.getElementById(id)).reconcile();
    return result === undefined ? 'undefined' : String(result);
}"""

# Calls drawEdges once and counts the viewport's node queries it makes.
COUNT_NODE_QUERIES = """id => {
    const viewport = document.querySelector('#' + id + ' > .pjx-graph__canvas > .pjx-graph__viewport');
    let count = 0;
    viewport.querySelectorAll = function (selector) {
        if (selector === '[data-node-id]') count += 1;
        return Element.prototype.querySelectorAll.call(this, selector);
    };
    try {
        pjx.graph.get(document.getElementById(id)).drawEdges();
    } finally {
        delete viewport.querySelectorAll;
    }
    return count;
}"""

# Calls one instance method and lists the graph events it fired before returning.
FIRED_BY = """([id, method]) => {
    const from = window.__events.length;
    pjx.graph.get(document.getElementById(id))[method]();
    return window.__events.slice(from).map((e) => e.type);
}"""

# Ends the mouse's press the way a browser that takes the pointer over would.
CANCEL = """() => window.dispatchEvent(new PointerEvent('pointercancel',
    { pointerId: 1, bubbles: true }))"""

NUMBER = re.compile(r"-?\d+(?:\.\d+)?(?:e[-+]?\d+)?")
SPAN = re.compile(r"<span [^>]*data-pjx-graph-edge[^>]*></span>")


def _node(node_id: str, x: float, y: float, stage_id: str = "g", **kw) -> PJXGraphNode:
    kw.setdefault("title", node_id.upper())
    return PJXGraphNode(id=f"{stage_id}-{node_id}", node_id=node_id, x=x, y=y, **kw)


def _trio(stage_id: str = "g", b: tuple[float, float] = (400, 40)) -> list:
    """a at (20, 40) with out-ports ok and fail; b (in-port) at b; c (in-port) at (400, 260)."""
    return [
        _node("a", 20, 40, stage_id, in_port=True, out_ports=("ok", "fail")),
        _node("b", *b, stage_id, in_port=True, out_ports=("ok",)),
        _node("c", 400, 260, stage_id, in_port=True),
    ]


def _edge(edge_id: str, src: str, dst: str, **kw: str) -> dict[str, str]:
    return {"id": edge_id, "from": src, "to": dst, **kw}


# a→b on ok, a→c on fail.
EDGES = [_edge("e1", "a", "b", port="ok"), _edge("e2", "a", "c", port="fail")]


def _layer(session, nodes: list, stage_id: str = "g") -> PJXGraphNodes:
    return PJXGraphNodes(
        id=f"{stage_id}-nodes",
        nodes_html=PJXGraphNodes.join(render(node, session) for node in nodes),
    )


def _stage(session, nodes=None, stage_id: str = "g", edges=None, **graph) -> str:
    """The trio with EDGES by default; an edge layer is rendered whenever edges is a list."""
    if nodes is None:
        nodes = _trio(stage_id)
    if edges is None:
        edges = EDGES
    graph["edges"] = PJXGraphEdges(id=f"{stage_id}-edges", edges=edges)
    layer = _layer(session, nodes, stage_id)
    return render(PJXGraph(id=stage_id, nodes=layer, **graph), session)


def _keyed(session, nodes=None, **graph) -> str:
    """A stage under the flow storage key."""
    return _stage(session, nodes, storage_key="flow", **graph)


def _span(edge: dict[str, str]) -> str:
    """The hidden span PJXGraphEdges renders for one edge."""
    found = SPAN.search(render(PJXGraphEdges(id="tmp", edges=[edge])))
    assert found is not None
    return found.group(0)


def _html(session, component) -> str:
    return str(render(component, session))


def _seed(page: Page, record: dict | str, key: str = RECORD) -> None:
    """Store record under key before the page's own scripts run, on the first load only."""
    raw = record if isinstance(record, str) else json.dumps(record)
    page.add_init_script(
        f"if (!sessionStorage.getItem('seeded:' + {json.dumps(key)})) {{"
        f" localStorage.setItem({json.dumps(key)}, {json.dumps(raw)});"
        f" sessionStorage.setItem('seeded:' + {json.dumps(key)}, '1'); }}"
    )


def _serve(
    page: Page, body: str, css: str = "", record: dict | str | None = None
) -> None:
    """Seed record (an identity view by default), record graph events, load body."""
    _seed(page, {"view": IDENTITY_VIEW} if record is None else record)
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


def _rendered(page: Page, stage_id: str = "g") -> int:
    return len([e for e in _events(page, "rendered") if e["target"] == stage_id])


def _frames(page: Page, count: int = 2) -> None:
    """Let count animation frames pass, so any pending reconcile has run."""
    page.evaluate(
        """count => new Promise((done) => {
            const tick = (left) => left ? requestAnimationFrame(() => tick(left - 1)) : done();
            tick(count);
        })""",
        count,
    )


def _settle(page: Page, before: int, stage_id: str = "g") -> int:
    """Wait for a rendered after before, let two more frames pass, return the count."""
    page.wait_for_function(
        """([stage, before]) => window.__events.filter(
            (e) => e.type === 'rendered' && e.target === stage).length > before""",
        arg=[stage_id, before],
        timeout=5000,
    )
    _frames(page)
    return _rendered(page, stage_id)


def _replace(selector: str, html: str) -> str:
    return f"document.querySelector({json.dumps(selector)}).outerHTML = {json.dumps(html)};"


def _set(selector: str, name: str, value: str) -> str:
    return (
        f"document.querySelector({json.dumps(selector)})"
        f".setAttribute({json.dumps(name)}, {json.dumps(value)});"
    )


def _edge_span(edge_id: str, stage_id: str = "g") -> str:
    return f'#{stage_id}-edges [data-edge-id="{edge_id}"]'


def _append(selector: str, html: str) -> str:
    return (
        f"document.querySelector({json.dumps(selector)})"
        f".insertAdjacentHTML('beforeend', {json.dumps(html)});"
    )


def _remove(selector: str) -> str:
    return f"document.querySelector({json.dumps(selector)}).remove();"


def _mutate(page: Page, *steps: str, reconcile: str | None = None) -> None:
    """Run the DOM steps in one task; then call reconcile() on that stage, if named."""
    call = (
        f"pjx.graph.get(document.getElementById({json.dumps(reconcile)})).reconcile();"
        if reconcile
        else ""
    )
    page.evaluate("() => {" + "".join(steps) + call + "}")


def _position(page: Page, element_id: str) -> list[str]:
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


def _title(element_id: str) -> str:
    return f"#{element_id} .pjx-graph__node-title"


def _port(element_id: str, key: str = "ok") -> str:
    return f'#{element_id} [data-pjx-graph-port="out"][data-port="{key}"]'


def _press(page: Page, start: tuple[int, int], end: tuple[int, int]) -> None:
    """Press at start and move to end in steps, without releasing."""
    page.mouse.move(*start)
    page.mouse.down()
    page.mouse.move(*end, steps=6)


def _drag(page: Page, start: tuple[int, int], end: tuple[int, int]) -> None:
    _press(page, start, end)
    page.mouse.up()


def _plane(page: Page, stage_id: str = "g") -> list[dict]:
    return page.evaluate(PLANE, stage_id)


def _visible(page: Page, stage_id: str = "g") -> list[dict]:
    return [
        el
        for el in _plane(page, stage_id)
        if el["tag"] == "path" and (el["cls"] or "").split()[:1] == ["pjx-graph__edge"]
    ]


def _path(page: Page, edge_id: str, stage_id: str = "g") -> str:
    return next(el["d"] for el in _visible(page, stage_id) if el["edge"] == edge_id)


def _labels(page: Page, stage_id: str = "g") -> list[list[str]]:
    return page.evaluate(LABELS, stage_id)


def _call(page: Page, method: str, *args, stage_id: str = "g"):
    return page.evaluate(CALL, [stage_id, method, list(args)])


def _fanned(page: Page, a_id: str, b_id: str, plain: str) -> None:
    """Edges a and b, alone on plain's pair and port, bow evenly apart about it."""
    base = _numbers(plain)
    a, b = _numbers(_path(page, a_id)), _numbers(_path(page, b_id))
    assert a != b
    for path in (a, b):
        assert path[:2] == pytest.approx(base[:2], abs=0.01)
        assert path[-2:] == pytest.approx(base[-2:], abs=0.01)
    # Only the control points move, by equal offsets on either side of zero.
    middle = [(p + q) / 2 for p, q in zip(a[2:6], b[2:6], strict=True)]
    assert middle == pytest.approx(base[2:6], abs=0.01)


def _fan(page: Page) -> tuple[str, int]:
    """Add e3 beside e1 (a→b on ok); return e1's lone path and the settled rendered count."""
    plain = _path(page, "e1")
    before = _rendered(page)
    _mutate(page, _append("#g-edges", _span(_edge("e3", "a", "b", port="ok"))))
    return plain, _settle(page, before)


def _numbers(d: str) -> list[float]:
    return [float(n) for n in NUMBER.findall(d)]


def _held(page: Page, before: int, stage_id: str = "g") -> None:
    """Let pending reconciles run; check the stage fired no rendered since before."""
    _frames(page, 4)
    assert _rendered(page, stage_id) == before


def _flushed_once(page: Page, before: int, stage_id: str = "g") -> int:
    """Check exactly one rendered followed before; return the new count."""
    assert _settle(page, before, stage_id) == before + 1
    _frames(page, 4)
    assert _rendered(page, stage_id) == before + 1
    return before + 1


# Calling reconcile


def test_get_exposes_reconcile_and_it_fires_one_rendered(page, page_errors, session):
    _serve(page, _stage(session))
    _forget(page)
    assert (
        page.evaluate(
            "() => typeof pjx.graph.get(document.getElementById('g')).reconcile"
        )
        == "function"
    )
    assert page.evaluate(RECONCILE, "g") == "undefined"
    assert _events(page, "rendered") == [
        {"type": "rendered", "detail": None, "target": "g", "cancelable": False}
    ]
    assert page_errors == []


def test_mount_still_returns_the_same_instance(page, page_errors, session):
    _serve(page, _stage(session))
    same = page.evaluate(
        """() => { const root = document.getElementById('g');
            return pjx.graph.mount(root) === pjx.graph.get(root); }"""
    )
    assert same is True
    keys = page.evaluate(
        "() => Object.keys(pjx.graph.get(document.getElementById('g'))).sort()"
    )
    assert keys == sorted(
        [
            "root",
            "box",
            "inAnchor",
            "outAnchor",
            "fit",
            "zoomBy",
            "drawEdges",
            "select",
            "deselect",
            "reconcile",
        ]
    )
    assert page_errors == []


def test_reconcile_twice_draws_the_same_edges(page, page_errors, session):
    _serve(page, _stage(session))
    page.evaluate(RECONCILE, "g")
    once = _plane(page)
    _forget(page)
    for _ in range(3):
        page.evaluate(RECONCILE, "g")
    assert _plane(page) == once
    assert [e["edge"] for e in _visible(page)] == ["e1", "e2"]
    assert len(_events(page, "rendered")) == 3
    assert page_errors == []


def test_reconcile_after_a_replaced_node_redraws_its_edge_at_the_new_anchor(
    page, page_errors, session
):
    _serve(page, _stage(session))
    moved = _html(session, _node("b", 400, 120, in_port=True, out_ports=("ok",)))
    _mutate(page, _replace("#g-b", moved), reconcile="g")
    anchor = _call(page, "inAnchor", "b")
    assert _numbers(_path(page, "e1"))[-2:] == pytest.approx(
        [anchor["x"], anchor["y"]], abs=0.01
    )
    assert _position(page, "g-b") == ["400px", "120px"]
    assert page_errors == []


def test_reconcile_with_an_empty_node_layer_draws_nothing(page, page_errors, session):
    _serve(page, _stage(session))
    # Counted inside the same task, before any frame could add an observer's reconcile.
    fired = page.evaluate(
        """() => { const from = window.__events.length;
            document.getElementById('g-nodes').replaceChildren();
            pjx.graph.get(document.getElementById('g')).reconcile();
            return window.__events.slice(from).map((e) => e.type); }"""
    )
    assert fired == ["rendered"]
    assert _visible(page) == []
    assert page_errors == []


# Positions


def test_a_replaced_node_takes_its_stored_drop_while_the_server_position_is_unchanged(
    page, page_errors, session
):
    seeded = json.dumps(
        {
            "view": IDENTITY_VIEW,
            "nodes": {"b": {"x": 300, "y": 150, "base": {"x": 400, "y": 40}}},
        }
    )
    _serve(page, _keyed(session), record=seeded)
    assert _position(page, "g-b") == ["300px", "150px"]
    same = _html(session, _node("b", 400, 40, in_port=True, out_ports=("ok",)))
    _mutate(page, _replace("#g-b", same), reconcile="g")
    assert _position(page, "g-b") == ["300px", "150px"]
    assert _raw(page) == seeded
    assert page_errors == []


def test_a_replaced_node_with_a_new_server_position_discards_the_drop(
    page, page_errors, session
):
    record = {
        "view": IDENTITY_VIEW,
        "nodes": {"b": {"x": 300, "y": 150, "base": {"x": 400, "y": 40}}},
    }
    _serve(page, _keyed(session), record=record)
    moved = _html(session, _node("b", 400, 90, in_port=True, out_ports=("ok",)))
    _mutate(page, _replace("#g-b", moved), reconcile="g")
    assert _position(page, "g-b") == ["400px", "90px"]
    assert _record(page) == {"view": IDENTITY_VIEW, "nodes": {}}
    assert page_errors == []


def test_an_unrelated_swap_keeps_a_dropped_node_where_it_was_dropped(
    page, page_errors, session
):
    # No storage key: the drop lives only in the node's style.
    _serve(page, _stage(session), record="")
    x, y = _center(page, _title("g-a"))
    _drag(page, (x, y), (x + 60, y + 40))
    dropped = _position(page, "g-a")
    assert dropped != ["20px", "40px"]
    _mutate(page, _append("#g-edges", _span(_edge("e3", "b", "c"))), reconcile="g")
    assert _position(page, "g-a") == dropped
    assert page_errors == []


def test_a_duplicate_node_id_does_not_break_reconcile(page, page_errors, session):
    _serve(page, _keyed(session))
    duplicate = _html(
        session, PJXGraphNode(id="g-b2", node_id="b", x=600, y=260, title="B2")
    )
    page.evaluate(
        "() => document.getElementById('g-b').style.setProperty("
        "'--pjx-graph-node-x', '410px')"
    )
    _mutate(page, _append("#g-nodes", duplicate), reconcile="g")
    _mutate(page, reconcile="g")
    # The first b is kept, so its style is untouched; the duplicate is placed.
    assert _position(page, "g-b") == ["410px", "40px"]
    assert _position(page, "g-b2") == ["600px", "260px"]
    anchor = _call(page, "inAnchor", "b")
    # In world space: the viewport's client origin is not the page's.
    first = page.evaluate(
        """() => { const r = document.getElementById('g-b').getBoundingClientRect();
            const o = document.querySelector('#g .pjx-graph__viewport').getBoundingClientRect();
            return [r.left - o.left, r.top - o.top + r.height / 2]; }"""
    )
    assert [anchor["x"], anchor["y"]] == pytest.approx(first, abs=0.01)
    assert [e["edge"] for e in _visible(page)] == ["e1", "e2"]
    assert page_errors == []


# Noticing swaps


def test_replacing_the_whole_nodes_layer_redraws_edges_at_the_new_positions(
    page, page_errors, session
):
    _serve(page, _stage(session))
    before = _rendered(page)
    layer = _html(session, _layer(session, _trio(b=(400, 180))))
    _mutate(page, _replace("#g-nodes", layer))
    _settle(page, before)
    assert _position(page, "g-b") == ["400px", "180px"]
    anchor = _call(page, "inAnchor", "b")
    assert _numbers(_path(page, "e1"))[-2:] == pytest.approx(
        [anchor["x"], anchor["y"]], abs=0.01
    )
    assert anchor["y"] > 180
    assert page_errors == []


def test_replacing_one_node_by_id_moves_only_that_node(page, page_errors, session):
    _serve(page, _stage(session))
    page.evaluate(
        "() => ['g-a', 'g-c'].forEach((id) => { document.getElementById(id).__kept = id; })"
    )
    before = _rendered(page)
    edge = _path(page, "e1")
    moved = _html(session, _node("b", 400, 140, in_port=True, out_ports=("ok",)))
    _mutate(page, _replace("#g-b", moved))
    _settle(page, before)
    kept = page.evaluate(
        "() => ['g-a', 'g-c'].map((id) => document.getElementById(id).__kept)"
    )
    assert kept == ["g-a", "g-c"]
    assert _position(page, "g-a") == ["20px", "40px"]
    assert _position(page, "g-c") == ["400px", "260px"]
    assert _path(page, "e1") != edge
    anchor = _call(page, "inAnchor", "b")
    assert _numbers(_path(page, "e1"))[-2:] == pytest.approx(
        [anchor["x"], anchor["y"]], abs=0.01
    )
    assert page_errors == []


def test_adding_a_node_and_its_edge_draws_the_edge(page, page_errors, session):
    _serve(page, _stage(session))
    before = _rendered(page)
    added = _html(session, _node("d", 700, 40, in_port=True))
    _mutate(
        page,
        _append("#g-nodes", added),
        _append("#g-edges", _span(_edge("e3", "b", "d", port="ok"))),
    )
    assert _settle(page, before) == before + 1
    assert [e["edge"] for e in _visible(page)] == ["e1", "e2", "e3"]
    anchor = _call(page, "inAnchor", "d")
    assert _numbers(_path(page, "e3"))[-2:] == pytest.approx(
        [anchor["x"], anchor["y"]], abs=0.01
    )
    assert page_errors == []


def test_removing_a_node_drops_its_edges(page, page_errors, session):
    edges = [*EDGES, _edge("e3", "b", "c", port="ok")]
    _serve(page, _stage(session, edges=edges))
    assert [e["edge"] for e in _visible(page)] == ["e1", "e2", "e3"]
    before = _rendered(page)
    _mutate(page, _remove("#g-c"))
    _settle(page, before)
    assert [e["edge"] for e in _visible(page)] == ["e1"]
    assert page_errors == []


def test_adding_and_removing_an_edge_element_redraws_and_unfans_the_pair(
    page, page_errors, session
):
    _serve(page, _stage(session))
    plain = _path(page, "e1")
    before = _rendered(page)
    _mutate(page, _append("#g-edges", _span(_edge("e3", "a", "b", port="ok"))))
    before = _settle(page, before)
    assert [e["edge"] for e in _visible(page)] == ["e1", "e2", "e3"]
    # Two edges between a and b fan apart, so e1 bows away from its plain path.
    assert _path(page, "e1") != plain
    _mutate(
        page,
        "document.querySelector('#g-edges [data-edge-id=\"e3\"]').remove();",
    )
    _settle(page, before)
    assert [e["edge"] for e in _visible(page)] == ["e1", "e2"]
    assert _path(page, "e1") == plain
    assert page_errors == []


def test_removing_the_whole_nodes_layer_draws_nothing_and_fires_one_rendered(
    page, page_errors, session
):
    _serve(page, _stage(session))
    page.evaluate(
        "() => { window.__instance = pjx.graph.get(document.getElementById('g')); }"
    )
    before = _rendered(page)
    _mutate(page, _remove("#g-nodes"))
    assert _settle(page, before) == before + 1
    assert _visible(page) == []
    assert page.evaluate(
        "() => pjx.graph.get(document.getElementById('g')) === window.__instance"
    )
    assert page_errors == []


def test_a_node_removed_then_reinserted_keeps_its_stored_drop(
    page, page_errors, session
):
    seeded = json.dumps(
        {
            "view": IDENTITY_VIEW,
            "nodes": {"b": {"x": 300, "y": 150, "base": {"x": 400, "y": 40}}},
        }
    )
    _serve(page, _keyed(session), record=seeded)
    before = _rendered(page)
    _mutate(page, _remove("#g-b"))
    before = _settle(page, before)
    assert _raw(page) == seeded
    same = _html(session, _node("b", 400, 40, in_port=True, out_ports=("ok",)))
    _mutate(page, _append("#g-nodes", same))
    _settle(page, before)
    assert _position(page, "g-b") == ["300px", "150px"]
    assert _raw(page) == seeded
    assert page_errors == []


# Coalescing and the plane


def test_mutations_in_one_task_cause_one_reconcile(page, page_errors, session):
    _serve(page, _stage(session))
    before = _rendered(page)
    _mutate(
        page,
        _replace("#g-a", _html(session, _trio()[0])),
        _replace("#g-b", _html(session, _trio(b=(400, 100))[1])),
        _append("#g-edges", _span(_edge("e3", "b", "c", port="ok"))),
    )
    assert _settle(page, before) == before + 1
    assert page_errors == []


def test_a_reconcile_does_not_trigger_another(page, page_errors, session):
    _serve(page, _stage(session))
    before = _rendered(page)
    _mutate(page, _replace("#g-c", _html(session, _trio()[2])))
    after = _settle(page, before)
    assert after == before + 1
    _frames(page, 4)
    assert _rendered(page) == after
    assert page_errors == []


def test_calling_reconcile_by_hand_schedules_nothing(page, page_errors, session):
    _serve(page, _stage(session))
    before = _rendered(page)
    page.evaluate(RECONCILE, "g")
    _frames(page)
    assert _rendered(page) == before + 1
    assert page_errors == []


def test_selecting_a_node_fires_no_rendered(page, page_errors, session):
    _serve(page, _stage(session))
    before = _rendered(page)
    page.click(_title("g-b"))
    assert [e["type"] for e in _events(page, "select")] == ["select"]
    _frames(page)
    assert _rendered(page) == before
    assert page_errors == []


def test_dragging_a_wire_fires_no_rendered(page, page_errors, session):
    _serve(page, _stage(session))
    before = _rendered(page)
    _drag(page, _center(page, _port("g-a")), _center(page, _title("g-c")))
    assert [e["detail"] for e in _events(page, "wire")] == [
        {"from": "a", "port": "ok", "to": "c"}
    ]
    _frames(page)
    assert _rendered(page) == before
    assert page_errors == []


NESTED_CSS = (
    "#g-a { width: 700px; } #in { width: 600px; }"
    " #in > .pjx-graph__canvas { min-height: 0; height: 200px; }"
)


def _nested(page: Page, session) -> str:
    """Stage g whose node a (at 20, 20) holds stage in, with nodes x (10, 10) and y (300, 10)."""
    inner = _stage(
        session,
        [
            _node("x", 10, 10, "in", out_ports=("ok",)),
            _node("y", 300, 10, "in", in_port=True),
        ],
        "in",
        edges=[_edge("i1", "x", "y", port="ok")],
        storage_key="inner",
    )
    _seed(page, {"view": IDENTITY_VIEW}, key="pjx-graph:inner")
    return _keyed(
        session,
        [_node("a", 20, 20, icon=Markup(inner), title="Outer")],
        edges=[],
    )


def test_a_swap_inside_a_nested_stage_settles(page, page_errors, session):
    _serve(page, _nested(page, session), NESTED_CSS)
    inner, outer = _rendered(page, "in"), _rendered(page, "g")
    moved = _html(session, _node("y", 300, 60, "in", in_port=True))
    _mutate(page, _replace("#in-y", moved))
    _settle(page, inner, "in")
    counts = (_rendered(page, "in"), _rendered(page, "g"))
    assert counts[0] == inner + 1
    assert counts[1] <= outer + 1
    _frames(page, 4)
    assert (_rendered(page, "in"), _rendered(page, "g")) == counts
    anchor = _call(page, "inAnchor", "y", stage_id="in")
    assert _numbers(_path(page, "i1", "in"))[-2:] == pytest.approx(
        [anchor["x"], anchor["y"]], abs=0.01
    )
    assert page_errors == []


# Interaction after swaps


def test_handlers_are_not_double_bound_after_swaps(page, page_errors, session):
    _serve(page, _keyed(session))
    for b in [(400, 40), (400, 40)]:
        before = _rendered(page)
        _mutate(page, _replace("#g-nodes", _html(session, _layer(session, _trio(b=b)))))
        _settle(page, before)
    for _ in range(3):
        page.evaluate(RECONCILE, "g")
    _forget(page)
    page.click(_title("g-b"))
    assert [e["type"] for e in _events(page, "before-select", "select")] == [
        "before-select",
        "select",
    ]
    _forget(page)
    x, y = _center(page, _title("g-b"))
    _drag(page, (x, y), (x + 60, y + 40))
    assert [e["detail"] for e in _events(page, "move")] == [
        {"id": "b", "x": 460, "y": 80}
    ]
    assert page_errors == []


def test_a_wire_from_a_replaced_node_fires_one_wire_event(page, page_errors, session):
    _serve(page, _stage(session))
    before = _rendered(page)
    _mutate(page, _replace("#g-a", _html(session, _trio()[0])))
    _settle(page, before)
    _forget(page)
    _drag(page, _center(page, _port("g-a")), _center(page, _title("g-c")))
    assert [e["detail"] for e in _events(page, "wire")] == [
        {"from": "a", "port": "ok", "to": "c"}
    ]
    assert page_errors == []


def test_a_replaced_selected_node_stays_selected(page, page_errors, session):
    _serve(page, _stage(session))
    page.click(_title("g-b"))
    _forget(page)
    before = _rendered(page)
    _mutate(page, _replace("#g-b", _html(session, _trio()[1])))
    _settle(page, before)
    assert page.evaluate(
        "() => document.getElementById('g-b').classList.contains('pjx-graph__node--selected')"
    )
    assert _events(page, "deselect") == []
    assert page_errors == []


def test_a_reconcile_during_a_node_drag_leaves_the_dragged_node_alone(
    page, page_errors, session
):
    _serve(page, _keyed(session))
    x, y = _center(page, _title("g-a"))
    _press(page, (x, y), (x + 60, y + 40))
    assert _position(page, "g-a") == ["80px", "80px"]
    before = _rendered(page)
    _mutate(page, _replace("#g-c", _html(session, _trio()[2])), reconcile="g")
    assert page.evaluate(FIRED_BY, ["g", "reconcile"]) == []
    _held(page, before)
    assert _position(page, "g-a") == ["80px", "80px"]
    page.mouse.up()
    _flushed_once(page, before)
    assert [e["detail"] for e in _events(page, "move")] == [
        {"id": "a", "x": 80, "y": 80}
    ]
    assert _position(page, "g-a") == ["80px", "80px"]
    assert page_errors == []


# Edge changes


def test_adding_one_edge_fans_the_pair(page, page_errors, session):
    _serve(page, _stage(session))
    plain = _path(page, "e1")
    before = _rendered(page)
    _mutate(page, _append("#g-edges", _span(_edge("e3", "a", "b", port="ok"))))
    assert _settle(page, before) == before + 1
    assert [e["edge"] for e in _visible(page)] == ["e1", "e2", "e3"]
    _fanned(page, "e1", "e3", plain)
    assert page_errors == []


def test_removing_one_edge_unfans_the_pair(page, page_errors, session):
    _serve(page, _stage(session))
    plain, before = _fan(page)
    _mutate(page, _remove(_edge_span("e3")))
    assert _settle(page, before) == before + 1
    assert [e["edge"] for e in _visible(page)] == ["e1", "e2"]
    assert _path(page, "e1") == plain
    assert page_errors == []


def test_swapping_the_whole_edges_element_draws_only_the_new_list(
    page, page_errors, session
):
    _serve(page, _stage(session))
    plain = _path(page, "e1")
    before = _rendered(page)
    fresh = [
        _edge("e1", "a", "b", port="ok", state="ok"),
        _edge("e3", "a", "b", port="ok"),
        _edge("e4", "b", "c", port="ok", state="fail"),
    ]
    _mutate(
        page,
        _replace("#g-edges", _html(session, PJXGraphEdges(id="g-edges", edges=fresh))),
    )
    assert _settle(page, before) == before + 1
    visible = _visible(page)
    assert [e["edge"] for e in visible] == ["e1", "e3", "e4"]
    assert [e["state"] for e in visible] == ["ok", "", "fail"]
    assert "e2" not in {el["edge"] for el in _plane(page)}
    _fanned(page, "e1", "e3", plain)
    assert page_errors == []


def test_changing_an_edge_state_restyles_it_and_keeps_the_fan(
    page, page_errors, session
):
    edges = [_edge("e1", "a", "b", port="ok", state="ok"), EDGES[1]]
    _serve(page, _stage(session, edges=edges))
    plain, before = _fan(page)
    _mutate(page, _set(_edge_span("e1"), "data-state", "fail"))
    assert _settle(page, before) == before + 1
    e1 = next(el for el in _visible(page) if el["edge"] == "e1")
    assert e1["cls"].split() == ["pjx-graph__edge", "pjx-graph__edge--fail"]
    assert e1["state"] == "fail"
    _fanned(page, "e1", "e3", plain)
    # A state with whitespace is still the app's word, but no class.
    _mutate(page, _set(_edge_span("e1"), "data-state", "is late"))
    _settle(page, before + 1)
    e1 = next(el for el in _visible(page) if el["edge"] == "e1")
    assert e1["cls"] == "pjx-graph__edge"
    assert e1["state"] == "is late"
    assert page_errors == []


def test_changing_edge_attributes_in_one_task_causes_one_reconcile(
    page, page_errors, session
):
    _serve(page, _stage(session))
    before = _rendered(page)
    _mutate(
        page,
        _set(_edge_span("e1"), "data-state", "fail"),
        _set(_edge_span("e1"), "data-label", "retry"),
        _set(_edge_span("e2"), "data-port", "ok"),
        _append("#g-edges", _span(_edge("e3", "b", "c", port="ok"))),
    )
    assert _settle(page, before) == before + 1
    assert [e["edge"] for e in _visible(page)] == ["e1", "e2", "e3"]
    assert _labels(page) == [["e1", "retry"]]
    assert page_errors == []


def test_retargeting_an_edge_moves_it_between_pairs(page, page_errors, session):
    _serve(page, _stage(session))
    plain, before = _fan(page)
    e2_before = _path(page, "e2")
    _mutate(page, _set(_edge_span("e3"), "data-to", "c"))
    _settle(page, before)
    # a→b is down to e1 again, and a→c now holds e2 and e3, so it fans.
    assert _path(page, "e1") == plain
    assert _path(page, "e2") != e2_before
    e3 = next(el for el in _visible(page) if el["edge"] == "e3")
    assert e3["to"] == "c"
    anchor = _call(page, "inAnchor", "c")
    assert _numbers(e3["d"])[-2:] == pytest.approx([anchor["x"], anchor["y"]], abs=0.01)
    assert page_errors == []


def test_changing_an_edge_port_moves_its_start(page, page_errors, session):
    _serve(page, _stage(session))
    start = _numbers(_path(page, "e1"))[:2]
    before = _rendered(page)
    _mutate(page, _set(_edge_span("e1"), "data-port", "fail"))
    _settle(page, before)
    moved = _numbers(_path(page, "e1"))[:2]
    anchor = _call(page, "outAnchor", "a", "fail")
    assert moved == pytest.approx([anchor["x"], anchor["y"]], abs=0.01)
    assert moved != pytest.approx(start, abs=0.01)
    assert page_errors == []


def test_changing_an_edge_label_rewrites_and_removes_it(page, page_errors, session):
    _serve(page, _stage(session))
    assert _labels(page) == []
    before = _rendered(page)
    _mutate(page, _set(_edge_span("e1"), "data-label", "go"))
    before = _settle(page, before)
    assert _labels(page) == [["e1", "go"]]
    _mutate(page, _set(_edge_span("e1"), "data-label", ""))
    _settle(page, before)
    assert _labels(page) == []
    assert page_errors == []


def test_retargeting_an_edge_to_an_unknown_node_hides_it(page, page_errors, session):
    _serve(page, _stage(session))
    before = _rendered(page)
    _mutate(page, _set(_edge_span("e1"), "data-to", "zz"))
    before = _settle(page, before)
    assert [e["edge"] for e in _visible(page)] == ["e2"]
    _mutate(
        page,
        f"document.querySelector({json.dumps(_edge_span('e2'))})"
        ".removeAttribute('data-from');",
    )
    _settle(page, before)
    assert _visible(page) == []
    assert page_errors == []


def test_an_unwatched_attribute_schedules_nothing(page, page_errors, session):
    _serve(page, _stage(session))
    before = _rendered(page)
    _mutate(
        page,
        "document.getElementById('g-a').classList.add('app-flagged');",
        "document.getElementById('g-c').style.outline = '1px solid red';",
        _set("#g-b", "data-node-type", "task"),
        _set(_edge_span("e1"), "title", "first"),
        # The app's own markup inside a node, not one of the graph's elements.
        _set(_title("g-a"), "data-state", "busy"),
    )
    _frames(page, 4)
    assert _rendered(page) == before
    assert page_errors == []


def test_an_attribute_reconcile_does_not_trigger_another(page, page_errors, session):
    _serve(page, _stage(session))
    before = _rendered(page)
    _mutate(page, _set(_edge_span("e1"), "data-state", "fail"))
    after = _settle(page, before)
    assert after == before + 1
    _frames(page, 4)
    assert _rendered(page) == after
    assert page_errors == []


def test_an_edge_state_edit_inside_a_nested_stage_settles(page, page_errors, session):
    _serve(page, _nested(page, session), NESTED_CSS)
    inner, outer = _rendered(page, "in"), _rendered(page, "g")
    _mutate(page, _set(_edge_span("i1", "in"), "data-state", "fail"))
    _settle(page, inner, "in")
    counts = (_rendered(page, "in"), _rendered(page, "g"))
    assert counts[0] == inner + 1
    assert counts[1] <= outer + 1
    _frames(page, 4)
    assert (_rendered(page, "in"), _rendered(page, "g")) == counts
    i1 = next(el for el in _visible(page, "in") if el["edge"] == "i1")
    assert i1["cls"].split() == ["pjx-graph__edge", "pjx-graph__edge--fail"]
    assert page_errors == []


def test_changing_a_kept_nodes_data_x_moves_it_and_its_edges(
    page, page_errors, session
):
    _serve(page, _stage(session))
    edge = _path(page, "e1")
    before = _rendered(page)
    _mutate(page, _set("#g-b", "data-x", "460"))
    _settle(page, before)
    assert _position(page, "g-b") == ["460px", "40px"]
    assert _path(page, "e1") != edge
    anchor = _call(page, "inAnchor", "b")
    assert _numbers(_path(page, "e1"))[-2:] == pytest.approx(
        [anchor["x"], anchor["y"]], abs=0.01
    )
    assert page_errors == []


def test_a_new_server_position_on_a_kept_node_discards_its_drop(
    page, page_errors, session
):
    record = {
        "view": IDENTITY_VIEW,
        "nodes": {"b": {"x": 300, "y": 150, "base": {"x": 400, "y": 40}}},
    }
    _serve(page, _keyed(session), record=record)
    assert _position(page, "g-b") == ["300px", "150px"]
    before = _rendered(page)
    _mutate(page, _set("#g-b", "data-y", "90"))
    _settle(page, before)
    assert _position(page, "g-b") == ["400px", "90px"]
    assert _record(page) == {"view": IDENTITY_VIEW, "nodes": {}}
    assert page_errors == []


def test_a_direct_reconcile_after_set_attribute_places_the_node(
    page, page_errors, session
):
    _serve(page, _stage(session))
    before = _rendered(page)
    _mutate(page, _set("#g-b", "data-x", "460"), reconcile="g")
    assert _position(page, "g-b") == ["460px", "40px"]
    anchor = _call(page, "inAnchor", "b")
    assert _numbers(_path(page, "e1"))[-2:] == pytest.approx(
        [anchor["x"], anchor["y"]], abs=0.01
    )
    # The observer's own reconcile still follows, and moves nothing again.
    _settle(page, before + 1)
    assert _position(page, "g-b") == ["460px", "40px"]
    assert page_errors == []


def test_a_blank_data_x_keeps_the_node_where_it_was(page, page_errors, session):
    _serve(page, _stage(session))
    for value in ("", "left"):
        before = _rendered(page)
        _mutate(page, _set("#g-b", "data-x", value))
        _settle(page, before)
        assert _position(page, "g-b") == ["400px", "40px"]
    assert [e["edge"] for e in _visible(page)] == ["e1", "e2"]
    assert page_errors == []


def test_resending_the_same_position_keeps_a_dropped_node_where_it_was_dropped(
    page, page_errors, session
):
    # No storage key: the drop lives only in the node's style.
    _serve(page, _stage(session), record="")
    x, y = _center(page, _title("g-a"))
    _drag(page, (x, y), (x + 60, y + 40))
    dropped = _position(page, "g-a")
    assert dropped != ["20px", "40px"]
    before = _rendered(page)
    # A morphing swap writes the attributes back even when they are unchanged.
    _mutate(
        page,
        """for (const name of ['data-x', 'data-y']) {
            const node = document.getElementById('g-a');
            node.setAttribute(name, node.getAttribute(name));
        }""",
    )
    _settle(page, before)
    assert _position(page, "g-a") == dropped
    assert page_errors == []


def test_moving_a_nested_stages_node_by_attribute_settles(page, page_errors, session):
    _serve(page, _nested(page, session), NESTED_CSS)
    inner, outer = _rendered(page, "in"), _rendered(page, "g")
    _mutate(page, _set("#in-y", "data-y", "60"))
    _settle(page, inner, "in")
    counts = (_rendered(page, "in"), _rendered(page, "g"))
    assert counts[0] == inner + 1
    assert counts[1] <= outer + 1
    _frames(page, 4)
    assert (_rendered(page, "in"), _rendered(page, "g")) == counts
    assert _position(page, "in-y") == ["300px", "60px"]
    anchor = _call(page, "inAnchor", "y", stage_id="in")
    assert _numbers(_path(page, "i1", "in"))[-2:] == pytest.approx(
        [anchor["x"], anchor["y"]], abs=0.01
    )
    assert page_errors == []


# Node lookup


def test_a_redraw_queries_nodes_once(page, page_errors, session):
    edges = [_edge(f"e{i}", "a", "b", port="ok") for i in range(5)] + [
        _edge(f"e{i}", "a", "c", port="fail") for i in range(5, 10)
    ]
    _serve(page, _stage(session, edges=edges))
    assert len(_visible(page)) == 10
    assert page.evaluate(COUNT_NODE_QUERIES, "g") == 1
    assert len(_visible(page)) == 10
    assert page_errors == []


def test_lookups_outside_a_redraw_see_a_node_added_in_the_same_task(
    page, page_errors, session
):
    _serve(page, _stage(session))
    added = _html(session, _node("d", 700, 40, in_port=True))
    found = page.evaluate(
        """html => {
            document.getElementById('g-nodes').insertAdjacentHTML('beforeend', html);
            const instance = pjx.graph.get(document.getElementById('g'));
            return [instance.box('d') !== null, instance.select('d')];
        }""",
        added,
    )
    assert found == [True, True]
    assert page_errors == []


# Holding updates during a gesture


def test_a_node_replacement_mid_drag_is_placed_only_after_release(
    page, page_errors, session
):
    _serve(page, _keyed(session))
    bx, by = _center(page, _title("g-b"))
    _drag(page, (bx, by), (bx + 60, by + 40))
    assert _position(page, "g-b") == ["460px", "80px"]
    x, y = _center(page, _title("g-a"))
    _press(page, (x, y), (x + 60, y + 40))
    edge = _path(page, "e1")
    before = _rendered(page)
    same = _html(session, _node("b", 400, 40, in_port=True, out_ports=("ok",)))
    _mutate(page, _replace("#g-b", same))
    _held(page, before)
    # The swapped-in element shows the server position it was rendered with
    # (the component renders floats, so "400.0px", not the engine's "400px").
    assert _position(page, "g-b") == ["400.0px", "40.0px"]
    assert _path(page, "e1") == edge
    page.mouse.up()
    _flushed_once(page, before)
    assert _position(page, "g-b") == ["460px", "80px"]
    anchor = _call(page, "inAnchor", "b")
    assert _numbers(_path(page, "e1"))[-2:] == pytest.approx(
        [anchor["x"], anchor["y"]], abs=0.01
    )
    assert page_errors == []


def test_an_edge_added_mid_drag_is_drawn_only_after_release(page, page_errors, session):
    _serve(page, _keyed(session))
    x, y = _center(page, _title("g-a"))
    _press(page, (x, y), (x + 60, y + 40))
    # Drawn at the drag's last move; the pointer stays put once e3 is added.
    plain = _path(page, "e1")
    before = _rendered(page)
    _mutate(page, _append("#g-edges", _span(_edge("e3", "a", "b", port="ok"))))
    _held(page, before)
    assert [e["edge"] for e in _visible(page)] == ["e1", "e2"]
    page.mouse.up()
    _flushed_once(page, before)
    assert [e["edge"] for e in _visible(page)] == ["e1", "e2", "e3"]
    _fanned(page, "e1", "e3", plain)
    assert page_errors == []


def test_a_node_and_an_edge_change_mid_drag_flush_one_rendered(
    page, page_errors, session
):
    _serve(page, _keyed(session))
    x, y = _center(page, _title("g-a"))
    _press(page, (x, y), (x + 60, y + 40))
    e2 = _path(page, "e2")
    before = _rendered(page)
    # Separate tasks, so the observer may reconcile between any two of them.
    moved_c = _html(session, _node("c", 400, 200, in_port=True))
    _mutate(page, _replace("#g-c", moved_c))
    _mutate(page, _append("#g-edges", _span(_edge("e3", "a", "b", port="ok"))))
    _mutate(page, _set("#g-b", "data-x", "460"))
    _mutate(page, reconcile="g")
    _mutate(page, reconcile="g")
    _held(page, before)
    assert _position(page, "g-b") == ["400px", "40px"]
    assert [e["edge"] for e in _visible(page)] == ["e1", "e2"]
    assert _path(page, "e2") == e2
    page.mouse.up()
    _flushed_once(page, before)
    assert _position(page, "g-b") == ["460px", "40px"]
    assert [e["edge"] for e in _visible(page)] == ["e1", "e2", "e3"]
    for edge, node in (("e1", "b"), ("e2", "c"), ("e3", "b")):
        anchor = _call(page, "inAnchor", node)
        assert _numbers(_path(page, edge))[-2:] == pytest.approx(
            [anchor["x"], anchor["y"]], abs=0.01
        )
    assert page_errors == []


def test_a_press_without_a_drag_holds_and_flushes_once(page, page_errors, session):
    _serve(page, _keyed(session))
    page.mouse.move(*_center(page, _title("g-b")))
    page.mouse.down()
    before = _rendered(page)
    _mutate(page, _replace("#g-c", _html(session, _trio()[2])), reconcile="g")
    _held(page, before)
    page.mouse.up()
    _flushed_once(page, before)
    assert [e["detail"] for e in _events(page, "select")] == [{"id": "b"}]
    assert page_errors == []


def test_a_gesture_with_no_update_fires_no_rendered(page, page_errors, session):
    _serve(page, _keyed(session))
    before = _rendered(page)
    x, y = _center(page, _title("g-a"))
    _drag(page, (x, y), (x + 60, y + 40))
    _frames(page, 4)
    assert _rendered(page) == before
    assert [e["detail"] for e in _events(page, "move")] == [
        {"id": "a", "x": 80, "y": 80}
    ]
    assert page_errors == []


def test_a_held_stage_does_not_hold_a_nested_stage(page, page_errors, session):
    _serve(page, _nested(page, session), NESTED_CSS)
    # The outer node's own title, not one of the nested stage's.
    x, y = _center(page, "#g-a > .pjx-graph__node-body > .pjx-graph__node-title")
    _press(page, (x, y), (x + 60, y + 40))
    inner, outer = _rendered(page, "in"), _rendered(page, "g")
    moved = _html(session, _node("y", 300, 60, "in", in_port=True))
    _mutate(page, _replace("#in-y", moved))
    assert _settle(page, inner, "in") == inner + 1
    _held(page, outer, "g")
    anchor = _call(page, "inAnchor", "y", stage_id="in")
    assert _numbers(_path(page, "i1", "in"))[-2:] == pytest.approx(
        [anchor["x"], anchor["y"]], abs=0.01
    )
    page.mouse.up()
    _flushed_once(page, outer, "g")
    assert _rendered(page, "in") == inner + 1
    assert page_errors == []


def test_a_cancelled_drag_flushes_once(page, page_errors, session):
    _serve(page, _keyed(session))
    x, y = _center(page, _title("g-a"))
    _press(page, (x, y), (x + 60, y + 40))
    before = _rendered(page)
    _mutate(page, _replace("#g-c", _html(session, _trio()[2])))
    _held(page, before)
    page.evaluate(CANCEL)
    _flushed_once(page, before)
    assert [e["detail"] for e in _events(page, "move")] == [
        {"id": "a", "x": 80, "y": 80}
    ]
    page.mouse.up()
    assert len(_events(page, "move")) == 1
    assert page_errors == []


def test_reconcile_after_a_flushed_gesture_runs_normally(page, page_errors, session):
    _serve(page, _keyed(session))
    x, y = _center(page, _title("g-a"))
    _press(page, (x, y), (x + 60, y + 40))
    before = _rendered(page)
    _mutate(page, _replace("#g-c", _html(session, _trio()[2])), reconcile="g")
    _held(page, before)
    page.mouse.up()
    after = _flushed_once(page, before)
    _mutate(page, _replace("#g-c", _html(session, _trio()[2])))
    assert _settle(page, after) == after + 1
    assert page.evaluate(FIRED_BY, ["g", "reconcile"]) == ["rendered"]
    assert page_errors == []


def test_replacing_the_pressed_node_mid_drag_places_the_replacement_at_the_drop(
    page, page_errors, session
):
    _serve(page, _keyed(session))
    x, y = _center(page, _title("g-a"))
    _press(page, (x, y), (x + 60, y + 40))
    before = _rendered(page)
    _mutate(page, _replace("#g-a", _html(session, _trio()[0])))
    _held(page, before)
    page.mouse.up()
    _flushed_once(page, before)
    assert [e["detail"] for e in _events(page, "move")] == [
        {"id": "a", "x": 80, "y": 80}
    ]
    assert _record(page)["nodes"] == {
        "a": {"x": 80, "y": 80, "base": {"x": 20, "y": 40}}
    }
    assert _position(page, "g-a") == ["80px", "80px"]
    assert page_errors == []


def test_a_ctrl_press_on_a_node_holds_nothing(page, page_errors, session):
    _serve(page, _keyed(session))
    page.mouse.move(*_center(page, _title("g-b")))
    page.keyboard.down("Control")
    page.mouse.down()
    assert page.evaluate(FIRED_BY, ["g", "reconcile"]) == ["rendered"]
    page.mouse.up()
    page.keyboard.up("Control")
    assert page_errors == []


def test_draw_edges_during_a_drag_is_not_held(page, page_errors, session):
    _serve(page, _keyed(session))
    x, y = _center(page, _title("g-a"))
    _press(page, (x, y), (x + 60, y + 40))
    assert page.evaluate(FIRED_BY, ["g", "drawEdges"]) == ["rendered"]
    after = _rendered(page)
    page.mouse.up()
    _frames(page, 4)
    assert _rendered(page) == after
    assert page_errors == []


def test_a_background_pan_holds_nothing(page, page_errors, session):
    _serve(page, _keyed(session, edges=[]))
    box = page.locator("#g > .pjx-graph__canvas").bounding_box()
    assert box is not None
    # Empty canvas at identity: below node a, left of b and c.
    x, y = round(box["x"] + 150), round(box["y"] + 300)
    _press(page, (x, y), (x + 40, y + 20))
    before = _rendered(page)
    _mutate(page, _replace("#g-c", _html(session, _trio()[2])))
    assert _settle(page, before) == before + 1
    page.mouse.up()
    assert _events(page, "move") == []
    assert page_errors == []
