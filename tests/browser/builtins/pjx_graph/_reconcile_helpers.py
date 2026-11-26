"""Asset paths, JS snippets and regexes for the pjx_graph reconcile tests."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from markupsafe import Markup

from pyjinhx.builtins.pjx_graph import PJXGraph
from pyjinhx.builtins.pjx_graph_edges import PJXGraphEdges
from pyjinhx.builtins.pjx_graph_node import PJXGraphNode
from pyjinhx.builtins.pjx_graph_nodes import PJXGraphNodes
from pyjinhx.rendering.pipeline import render

if TYPE_CHECKING:
    from playwright.sync_api import Page


UI = Path(__file__).resolve().parents[4] / "pyjinhx" / "builtins"


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


CALL = """([id, method, args]) => {
    const instance = pjx.graph.get(document.getElementById(id));
    return instance[method](...args);
}"""


# Calls reconcile and reports what it returned, as a JSON-safe value.
RECONCILE = """id => {
    const result = pjx.graph.get(document.getElementById(id)).reconcile();
    return result === undefined ? 'undefined' : String(result);
}"""


# Calls one instance method and lists the graph events it fired before returning.
FIRED_BY = """([id, method]) => {
    const from = window.__events.length;
    pjx.graph.get(document.getElementById(id))[method]();
    return window.__events.slice(from).map((e) => e.type);
}"""


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
