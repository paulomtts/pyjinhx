"""Replacing a mounted stage's root, in real chromium.

The document's MutationObserver drops the old instance and auto-boot mounts
the new root, so every stage is served from a real origin with the graph CSS
applied and the new markup is rendered by the real components and injected
with page.evaluate, as an htmx swap would. A detached root's events never
reach the document, so each test that replaces a root also records the old
root's own graph events. A document-level recorder installed before the
asset runs logs every live graph event, so tests wait on counts or ready
markers instead of sleeping.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING

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
CSS = "".join(
    (UI / name / f"{name}.css").read_text(encoding="utf-8")
    for name in ("pjx_graph", "pjx_graph_node", "pjx_graph_controls")
)
URL = "http://pjx.test/"
RECORD = "pjx-graph:flow"
IDENTITY_VIEW = {"x": 0, "y": 0, "k": 1}
GRAPH_EVENTS = "['rendered', 'move', 'wire', 'before-select', 'select', 'deselect']"

# Recorded at dispatch, from before the asset runs.
EVENTS = f"""window.__events = [];
{GRAPH_EVENTS}.forEach(
    (name) => document.addEventListener('pjx:graph:' + name, (event) => window.__events.push({{
        type: name, detail: event.detail, target: event.target.id}})));"""

# Keeps the stage's current root and instance, and records the graph events
# fired on that root itself, since once detached they never reach document.
KEEP_OLD = f"""id => {{
    window.oldRoot = document.getElementById(id);
    window.oldInstance = pjx.graph.get(window.oldRoot);
    window.__old = [];
    {GRAPH_EVENTS}.forEach((name) => window.oldRoot.addEventListener(
        'pjx:graph:' + name, () => window.__old.push(name)));
}}"""

# The inline transform of a root's own viewport.
TRANSFORM = """root => root.querySelector(
    ':scope > .pjx-graph__canvas > .pjx-graph__viewport').style.transform"""

# Whether a selectstart on document is let through, i.e. not prevented.
SELECTABLE = """() => document.dispatchEvent(
    new Event('selectstart', { bubbles: true, cancelable: true }))"""

NESTED_CSS = (
    "#g-a { width: 700px; } #in { width: 600px; }"
    " #in > .pjx-graph__canvas { min-height: 0; height: 200px; }"
)


def _node(node_id: str, x: float, y: float, stage_id: str = "g", **kw) -> PJXGraphNode:
    kw.setdefault("title", node_id.upper())
    return PJXGraphNode(id=f"{stage_id}-{node_id}", node_id=node_id, x=x, y=y, **kw)


def _trio(stage_id: str = "g") -> list[PJXGraphNode]:
    """a at (20, 40) with out-port ok; b (in-port) at (400, 40); c (in-port) at (400, 260)."""
    return [
        _node("a", 20, 40, stage_id, in_port=True, out_ports=("ok",)),
        _node("b", 400, 40, stage_id, in_port=True, out_ports=("ok",)),
        _node("c", 400, 260, stage_id, in_port=True),
    ]


def _edge(edge_id: str, src: str, dst: str, **kw: str) -> dict[str, str]:
    return {"id": edge_id, "from": src, "to": dst, **kw}


EDGES = [_edge("e1", "a", "b", port="ok")]


def _stage(session, nodes=None, stage_id: str = "g", edges=None, **graph) -> str:
    """The trio joined by EDGES unless nodes or edges say otherwise."""
    nodes = _trio(stage_id) if nodes is None else nodes
    graph["edges"] = PJXGraphEdges(
        id=f"{stage_id}-edges", edges=EDGES if edges is None else edges
    )
    layer = PJXGraphNodes(
        id=f"{stage_id}-nodes",
        nodes_html=PJXGraphNodes.join(render(node, session) for node in nodes),
    )
    return render(PJXGraph(id=stage_id, nodes=layer, **graph), session)


def _keyed(session, nodes=None, **graph) -> str:
    """A stage under the flow storage key."""
    return _stage(session, nodes, storage_key="flow", **graph)


def _nested(session) -> str:
    """Keyed stage g whose node a holds stage in (key inner), with nodes x and y."""
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
    return _keyed(
        session, [_node("a", 20, 20, icon=Markup(inner), title="Outer")], edges=[]
    )


def _seed(page: Page, record: dict, key: str = RECORD) -> None:
    """Store record under key before the page's own scripts run, on the first load only."""
    raw = json.dumps(record)
    page.add_init_script(
        f"if (!sessionStorage.getItem('seeded:' + {json.dumps(key)})) {{"
        f" localStorage.setItem({json.dumps(key)}, {json.dumps(raw)});"
        f" sessionStorage.setItem('seeded:' + {json.dumps(key)}, '1'); }}"
    )


def _serve(page: Page, body: str, css: str = "") -> None:
    """Seed an identity view for flow, record graph events, load body."""
    _seed(page, {"view": IDENTITY_VIEW})
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


def _frames(page: Page, count: int = 2) -> None:
    """Let count animation frames pass, so anything already scheduled has run."""
    page.evaluate(
        """count => new Promise((done) => {
            const tick = (left) => left ? requestAnimationFrame(() => tick(left - 1)) : done();
            tick(count);
        })""",
        count,
    )


def _events(page: Page, *kinds: str) -> list[dict]:
    events = page.evaluate("() => window.__events")
    return [e for e in events if not kinds or e["type"] in kinds]


def _rendered(page: Page, stage_id: str = "g") -> int:
    return len([e for e in _events(page, "rendered") if e["target"] == stage_id])


def _settle(page: Page, before: int, stage_id: str = "g") -> None:
    """Wait for a rendered on stage_id after before, then let two more frames pass."""
    page.wait_for_function(
        """([stage, before]) => window.__events.filter(
            (e) => e.type === 'rendered' && e.target === stage).length > before""",
        arg=[stage_id, before],
        timeout=5000,
    )
    _frames(page)


def _swap(page: Page, html: str, stage_id: str = "g") -> None:
    """Keep the stage's root and instance, replace the root with html, wait for the new mount."""
    page.evaluate(KEEP_OLD, stage_id)
    page.evaluate(
        "([id, html]) => { document.getElementById(id).outerHTML = html; }",
        [stage_id, html],
    )
    page.wait_for_function(
        """id => {
            const root = document.getElementById(id);
            return root !== window.oldRoot && pjx.graph.get(root) !== null;
        }""",
        arg=stage_id,
        timeout=5000,
    )
    _wait_ready(page)


def _old_dropped(page: Page) -> bool:
    return page.evaluate("() => pjx.graph.get(window.oldRoot) === null")


def _old_events(page: Page) -> list[str]:
    return page.evaluate("() => window.__old")


def _new_is_not_old(page: Page, stage_id: str = "g") -> bool:
    return page.evaluate(
        "id => pjx.graph.get(document.getElementById(id)) !== window.oldInstance",
        stage_id,
    )


def _transform(page: Page, root: str) -> str:
    """The viewport transform of root, a JS expression naming a stage root."""
    return page.evaluate(f"() => ({TRANSFORM})({root})")


def _position(page: Page, element_id: str) -> list[str]:
    return page.evaluate(
        """id => {
            const style = document.getElementById(id).style;
            return [style.getPropertyValue('--pjx-graph-node-x'),
                    style.getPropertyValue('--pjx-graph-node-y')];
        }""",
        element_id,
    )


def _center(page: Page, selector: str) -> tuple[int, int]:
    box = page.locator(selector).bounding_box()
    assert box is not None
    return round(box["x"] + box["width"] / 2), round(box["y"] + box["height"] / 2)


def _press(page: Page, start: tuple[int, int], end: tuple[int, int]) -> None:
    """Press at start and move to end in steps, without releasing."""
    page.mouse.move(*start)
    page.mouse.down()
    page.mouse.move(*end, steps=6)


def _reconciles(page: Page, stage_id: str = "g") -> None:
    """Swap the stage's node b for one at (400, 120); it settles with b placed there."""
    before = _rendered(page, stage_id)
    page.evaluate(
        "([id, html]) => { document.getElementById(id).outerHTML = html; }",
        [f"{stage_id}-b", render(_node("b", 400, 120, stage_id, in_port=True))],
    )
    _settle(page, before, stage_id)
    assert _position(page, f"{stage_id}-b") == ["400px", "120px"]


# Booting the replacement


def test_replaced_keyed_root_restores_view_on_new_instance(page, page_errors, session):
    _serve(page, _keyed(session))
    page.evaluate("() => pjx.graph.get(document.getElementById('g')).zoomBy(1)")
    _swap(page, _keyed(session))
    assert _new_is_not_old(page)
    saved = _transform(page, "window.oldRoot")
    assert saved.endswith("scale(1.41421)")
    assert _transform(page, "document.getElementById('g')") == saved
    assert page.evaluate(
        "() => document.getElementById('g').hasAttribute('data-pjx-graph-ready')"
    )
    assert page_errors == []


def test_replaced_unkeyed_root_boots_at_default_view(page, page_errors, session):
    _serve(page, _stage(session))
    page.evaluate("() => pjx.graph.get(document.getElementById('g')).zoomBy(1)")
    _swap(page, _stage(session))
    fresh = _transform(page, "document.getElementById('g')")
    assert fresh != _transform(page, "window.oldRoot")
    page.evaluate("() => pjx.graph.get(document.getElementById('g')).fit()")
    assert _transform(page, "document.getElementById('g')") == fresh
    assert page_errors == []


# Dropping the old instance


def test_replaced_root_drops_old_instance(page, page_errors, session):
    _serve(page, _keyed(session))
    _swap(page, _keyed(session))
    assert _old_dropped(page)
    assert page_errors == []


def test_root_replaced_before_layout_runs_no_fit_on_old(page, page_errors, session):
    _serve(page, _keyed(session))
    page.evaluate(
        """html => {
            document.body.insertAdjacentHTML('beforeend', html);
            window.oldRoot = document.getElementById('h');
            window.oldRoot.outerHTML = html;
        }""",
        _stage(session, stage_id="h"),
    )
    page.wait_for_function(
        """() => {
            const root = document.getElementById('h');
            return pjx.graph.get(root) !== null && root.hasAttribute('data-pjx-graph-ready');
        }""",
        timeout=5000,
    )
    # Past the ten frames a stage that never lays out waits before it fits.
    _frames(page, 15)
    assert _old_dropped(page)
    assert not page.evaluate(
        "() => window.oldRoot.hasAttribute('data-pjx-graph-ready')"
    )
    assert page_errors == []


def test_a_replacement_that_fails_to_mount_still_drops_the_old_instance(
    page, page_errors, console_errors, session
):
    _serve(page, _keyed(session))
    page.evaluate(KEEP_OLD, "g")
    page.evaluate(
        """() => { document.getElementById('g').outerHTML
            = '<div id="g" data-pjx-graph></div>'; }"""
    )
    page.wait_for_function("() => pjx.graph.get(window.oldRoot) === null", timeout=5000)
    assert page.evaluate("() => pjx.graph.get(document.getElementById('g'))") is None
    assert len(console_errors) == 1
    assert "missing .pjx-graph__canvas" in console_errors[0]
    # Removing a root that never mounted drops nothing and throws nothing.
    page.evaluate("() => document.getElementById('g').remove()")
    _frames(page)
    assert page_errors == []


# A moved root, and roots left alone


def test_moved_root_keeps_its_instance(page, page_errors, session):
    _serve(page, _keyed(session))
    page.evaluate(KEEP_OLD, "g")
    page.evaluate(
        """() => {
            const root = window.oldRoot;
            const parent = root.parentNode;
            const next = root.nextSibling;
            root.remove();
            parent.insertBefore(root, next);
        }"""
    )
    _frames(page)
    assert page.evaluate(
        "() => pjx.graph.get(document.getElementById('g')) === window.oldInstance"
    )
    _reconciles(page)
    assert page_errors == []


def test_root_reinserted_in_a_later_task_is_mounted_afresh(page, page_errors, session):
    _serve(page, _keyed(session))
    page.evaluate(KEEP_OLD, "g")
    page.evaluate("() => window.oldRoot.remove()")
    _frames(page)
    assert _old_dropped(page)
    page.evaluate("() => document.body.prepend(window.oldRoot)")
    page.wait_for_function("() => pjx.graph.get(window.oldRoot) !== null", timeout=5000)
    assert _new_is_not_old(page)
    _reconciles(page)
    assert page_errors == []


def test_replacing_one_root_leaves_sibling_stage_alone(page, page_errors, session):
    _serve(page, _keyed(session) + _stage(session, stage_id="h"))
    kept = "() => window.keptG === pjx.graph.get(document.getElementById('g'))"
    page.evaluate(
        "() => { window.keptG = pjx.graph.get(document.getElementById('g')); }"
    )
    _swap(page, _stage(session, stage_id="h"), "h")
    assert _old_dropped(page)
    assert page.evaluate(kept)
    _reconciles(page, "g")
    assert page.evaluate(kept)
    assert page_errors == []


def test_a_nested_stage_inside_a_replaced_root_is_dropped(page, page_errors, session):
    _seed(page, {"view": IDENTITY_VIEW}, key="pjx-graph:inner")
    _serve(page, _nested(session), NESTED_CSS)
    page.evaluate(
        """() => { window.oldInner = pjx.graph.get(document.getElementById('in'));
            window.oldInnerRoot = document.getElementById('in'); }"""
    )
    _swap(page, _nested(session))
    assert _old_dropped(page)
    assert page.evaluate("() => pjx.graph.get(window.oldInnerRoot) === null")
    assert page.evaluate(
        """() => {
            const inner = pjx.graph.get(document.getElementById('in'));
            return inner !== null && inner !== window.oldInner;
        }"""
    )
    assert page_errors == []


# A dropped instance goes quiet


def test_dropped_instance_no_longer_reconciles(page, page_errors, session):
    _serve(page, _keyed(session))
    _swap(page, _keyed(session))
    plane = "window.oldRoot.querySelector('svg.pjx-graph__edge-plane').children.length"
    drawn = page.evaluate(f"() => {plane}")
    placed = "window.oldRoot.querySelector('#g-b').style.getPropertyValue('--pjx-graph-node-x')"
    before = _rendered(page)
    # In one task with a swap on the new stage, so a live old observer would
    # reconcile in the same frame the new stage's rendered waits for.
    page.evaluate(
        """([edge, fresh]) => {
            window.oldRoot.querySelector('#g-b').setAttribute('data-x', '999');
            window.oldRoot.querySelector('#g-edges').insertAdjacentHTML('beforeend', edge);
            document.getElementById('g-c').outerHTML = fresh;
        }""",
        [
            render(PJXGraphEdges(id="tmp", edges=[_edge("e9", "a", "c")])),
            render(_node("c", 400, 260, in_port=True)),
        ],
    )
    _settle(page, before)
    assert page.evaluate(f"() => {placed}") == "400px"
    assert page.evaluate(f"() => {plane}") == drawn
    assert _old_events(page) == []
    assert page_errors == []


def test_root_mounted_by_hand_and_replaced_before_layout_never_turns_ready(
    page, page_errors, console_errors, session
):
    _serve(page, _keyed(session))
    page.evaluate(
        """html => {
            document.body.insertAdjacentHTML('beforeend', html);
            window.oldRoot = document.getElementById('h');
            pjx.graph.mount(window.oldRoot);
            window.oldRoot.outerHTML = html;
        }""",
        _stage(session, stage_id="h"),
    )
    page.wait_for_function(
        """() => {
            const root = document.getElementById('h');
            return pjx.graph.get(root) !== null && root.hasAttribute('data-pjx-graph-ready');
        }""",
        timeout=5000,
    )
    _frames(page, 15)
    assert _old_dropped(page)
    assert not page.evaluate(
        "() => window.oldRoot.hasAttribute('data-pjx-graph-ready')"
    )
    assert console_errors == []
    assert page_errors == []


def test_calling_a_kept_reference_to_a_dropped_instance_does_not_throw(
    page, page_errors, session
):
    _serve(page, _keyed(session))
    _swap(page, _keyed(session))
    page.evaluate(
        """() => {
            const old = window.oldInstance;
            old.reconcile();
            old.drawEdges();
            old.fit();
            old.zoomBy(1);
            old.deselect();
        }"""
    )
    _frames(page)
    assert page_errors == []


# Gestures cut off by the swap


def test_root_replaced_mid_drag_leaves_no_listeners(page, page_errors, session):
    _serve(page, _keyed(session))
    x, y = _center(page, "#g-b .pjx-graph__node-title")
    _press(page, (x, y), (x + 60, y + 40))
    assert not page.evaluate(SELECTABLE)
    _swap(page, _keyed(session))
    assert page.evaluate(SELECTABLE)
    page.mouse.move(x + 120, y + 80, steps=4)
    page.mouse.up()
    _frames(page)
    assert _old_events(page) == []
    assert _events(page, "move") == []
    assert page.evaluate(SELECTABLE)
    assert page_errors == []


def test_root_replaced_mid_wire_leaves_no_listeners(page, page_errors, session):
    _serve(page, _keyed(session))
    x, y = _center(page, '#g-a [data-pjx-graph-port="out"][data-port="ok"]')
    _press(page, (x, y), (x + 60, y + 40))
    assert not page.evaluate(SELECTABLE)
    _swap(page, _keyed(session))
    assert page.evaluate(SELECTABLE)
    page.mouse.move(*_center(page, "#g-c .pjx-graph__node-title"), steps=4)
    page.mouse.up()
    _frames(page)
    assert _old_events(page) == []
    assert _events(page, "wire") == []
    assert (
        page.evaluate("() => document.querySelectorAll('#g .pjx-graph__wire').length")
        == 0
    )
    assert page.evaluate(SELECTABLE)
    assert page_errors == []
