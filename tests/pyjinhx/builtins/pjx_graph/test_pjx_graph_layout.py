"""Node placement, node boxes and port anchors, and fit-to-nodes, in real chromium.

All of it depends on real CSS layout, getBoundingClientRect and animation
frames, so every stage is served from a real origin with the graph CSS applied.
World coordinates are the viewport's untransformed pixels, the space data-x/y
are written in.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from markupsafe import Markup

from pyjinhx.builtins.ui.pjx_graph import PJXGraph
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
IDENTITY = {"view": {"x": 0, "y": 0, "k": 1}}

# Every node's rendered rect, relative to the canvas's inner (border-less) origin.
NODE_RECTS = """id => {
    const canvas = document.querySelector('#' + id + ' > .pjx-graph__canvas');
    const c = canvas.getBoundingClientRect();
    const left = c.left + canvas.clientLeft;
    const top = c.top + canvas.clientTop;
    return Array.from(canvas.querySelectorAll('[data-node-id]')).map(node => {
        const r = node.getBoundingClientRect();
        return {id: node.getAttribute('data-node-id'), x: r.left - left,
                y: r.top - top, right: r.right - left, bottom: r.bottom - top};
    });
}"""


def _node(node_id: str, x: float, y: float, stage_id: str = "g", **kw) -> PJXGraphNode:
    return PJXGraphNode(id=f"{stage_id}-{node_id}", node_id=node_id, x=x, y=y, **kw)


def _stage(session, nodes: list, stage_id: str = "g", **graph) -> str:
    layer = PJXGraphNodes(
        id=f"{stage_id}-nodes",
        nodes_html=PJXGraphNodes.join(render(node, session) for node in nodes),
    )
    return render(PJXGraph(id=stage_id, nodes=layer, **graph), session)


def _serve(page: Page, body: str) -> None:
    """Load body with the graph CSS and asset, then wait until every mounted stage is ready."""
    asset = ASSET.read_text(encoding="utf-8")
    html = (
        f"<html><head><style>{CSS}</style></head>"
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


def _seed(page: Page, record: dict, key: str = RECORD) -> None:
    """Store record under key before the page's own scripts run."""
    page.add_init_script(
        f"localStorage.setItem({json.dumps(key)}, {json.dumps(json.dumps(record))});"
    )


def _rects(page: Page, stage_id: str = "g") -> list[dict]:
    return page.evaluate(NODE_RECTS, stage_id)


# Placement


def test_nodes_land_at_their_data_coordinates(page, page_errors, session):
    _seed(page, IDENTITY)
    nodes = [
        _node("a", 10, 20, title="A"),
        _node("b", 300, 40, title="B"),
        _node("c", 120.5, 260, title="C"),
    ]
    _serve(page, _stage(session, nodes, storage_key="flow"))
    rects = {r["id"]: r for r in _rects(page)}
    assert {k: (r["x"], r["y"]) for k, r in rects.items()} == {
        "a": pytest.approx((10, 20), abs=0.5),
        "b": pytest.approx((300, 40), abs=0.5),
        "c": pytest.approx((120.5, 260), abs=0.5),
    }
    assert page_errors == []


def test_data_coordinates_win_over_a_stale_inline_style(page, page_errors, session):
    _seed(page, IDENTITY)
    stale = render(_node("a", 40, 60, title="A"), session).replace(
        "--pjx-graph-node-x:40.0px;--pjx-graph-node-y:60.0px;",
        "--pjx-graph-node-x:7px;--pjx-graph-node-y:9px;",
    )
    stripped = re.sub(
        r' style="[^"]*"', "", render(_node("b", 300, 80, title="B"), session)
    )
    assert "7px" in stale and "style=" not in stripped
    layer = PJXGraphNodes(id="g-nodes", nodes_html=Markup(stale + stripped))
    _serve(page, render(PJXGraph(id="g", nodes=layer, storage_key="flow"), session))
    rects = {r["id"]: (r["x"], r["y"]) for r in _rects(page)}
    assert rects == {
        "a": pytest.approx((40, 60), abs=0.5),
        "b": pytest.approx((300, 80), abs=0.5),
    }
    assert page_errors == []


@pytest.mark.parametrize(
    "bad",
    ['data-x="abc"', 'data-x=""', 'data-x=" "', 'data-x="Infinity"', ""],
    ids=["not-a-number", "empty", "blank", "infinite", "missing"],
)
def test_a_non_numeric_coordinate_is_left_to_css(
    page, page_errors, console_errors, session, bad
):
    _seed(page, IDENTITY)
    # Inline style says (100, 5); data-y says 200, so only y should move.
    html = (
        render(_node("a", 100, 200, title="A"), session)
        .replace('data-x="100.0"', bad)
        .replace("--pjx-graph-node-y:200.0px", "--pjx-graph-node-y:5px")
    )
    layer = PJXGraphNodes(id="g-nodes", nodes_html=Markup(html))
    _serve(page, render(PJXGraph(id="g", nodes=layer, storage_key="flow"), session))
    [rect] = _rects(page)
    assert (rect["x"], rect["y"]) == pytest.approx((100, 200), abs=0.5)
    assert (
        page.evaluate(
            "() => document.getElementById('g-a').style.getPropertyValue('--pjx-graph-node-x')"
        )
        == "100.0px"
    )
    assert console_errors == []
    assert page_errors == []


# Box and anchors

VIEW = """id => {
    const viewport = document.querySelector(
        '#' + id + ' > .pjx-graph__canvas > .pjx-graph__viewport');
    const m = new DOMMatrix(getComputedStyle(viewport).transform);
    return {x: m.e, y: m.f, k: m.a};
}"""

# A client point turned into world coordinates through the computed transform,
# a different route from the engine's own.
CLIENT_TO_WORLD = """([id, x, y]) => {
    const canvas = document.querySelector('#' + id + ' > .pjx-graph__canvas');
    const r = canvas.getBoundingClientRect();
    const m = new DOMMatrix(getComputedStyle(
        canvas.querySelector(':scope > .pjx-graph__viewport')).transform);
    return {x: (x - r.left - canvas.clientLeft - m.e) / m.a,
            y: (y - r.top - canvas.clientTop - m.f) / m.a};
}"""

CALL = """([id, method, args]) => {
    const instance = pjx.graph.get(document.getElementById(id));
    return instance[method](...args);
}"""


def _view(page: Page, stage_id: str = "g") -> dict[str, float]:
    return page.evaluate(VIEW, stage_id)


def _call(page: Page, method: str, *args, stage_id: str = "g"):
    return page.evaluate(CALL, [stage_id, method, list(args)])


def _ports_stage(session, stage_id: str = "g", **graph) -> str:
    graph.setdefault("storage_key", "flow")
    node = _node(
        "a", 120, 80, stage_id, title="A", in_port=True, out_ports=("ok", "fail")
    )
    other = _node("b", 500, 300, stage_id, title="B")
    return _stage(session, [node, other], stage_id, **graph)


def test_box_reports_world_position_and_size(page, page_errors, session):
    _seed(page, IDENTITY)
    _serve(page, _ports_stage(session))
    size = page.evaluate(
        "() => { const n = document.getElementById('g-a');"
        " return {width: n.offsetWidth, height: n.offsetHeight}; }"
    )
    box = _call(page, "box", "a")
    assert (box["x"], box["y"]) == pytest.approx((120, 80), abs=0.5)
    assert (box["width"], box["height"]) == (size["width"], size["height"])
    assert page_errors == []


def _measure(page: Page, stage_id: str = "g") -> list:
    return [
        _call(page, "box", "a", stage_id=stage_id),
        _call(page, "inAnchor", "a", stage_id=stage_id),
        _call(page, "outAnchor", "a", "ok", stage_id=stage_id),
        _call(page, "outAnchor", "a", "fail", stage_id=stage_id),
        _call(page, "outAnchor", "b", stage_id=stage_id),
    ]


def test_box_and_anchors_ignore_the_view(page, page_errors, session):
    # The same nodes on two stages, one at identity and one panned and zoomed.
    _seed(page, IDENTITY)
    _seed(page, {"view": {"x": 37, "y": -12, "k": 1.5}}, key="pjx-graph:moved")
    moved = _ports_stage(session, stage_id="h", storage_key="moved")
    _serve(page, _ports_stage(session) + moved)
    assert _view(page, "h") == pytest.approx({"x": 37, "y": -12, "k": 1.5}, abs=0.01)
    for before, after in zip(_measure(page), _measure(page, "h"), strict=True):
        assert after == pytest.approx(before, abs=0.5)
    assert page_errors == []


def test_in_anchor_is_the_left_edge_midpoint(page, page_errors, session):
    _seed(page, IDENTITY)
    _serve(page, _ports_stage(session))
    box = _call(page, "box", "a")
    anchor = _call(page, "inAnchor", "a")
    assert anchor == pytest.approx({"x": box["x"], "y": box["y"] + box["height"] / 2})
    assert page_errors == []


def test_out_anchor_is_the_rendered_port_centre(page, page_errors, session):
    _seed(page, {"view": {"x": 37, "y": -12, "k": 1.5}})
    _serve(page, _ports_stage(session))
    box = _call(page, "box", "a")
    anchors = {}
    for port in ("ok", "fail"):
        dot = page.locator(f'#g-a [data-pjx-graph-port="out"][data-port="{port}"]')
        b = dot.bounding_box()
        assert b is not None
        centre = page.evaluate(
            CLIENT_TO_WORLD, ["g", b["x"] + b["width"] / 2, b["y"] + b["height"] / 2]
        )
        anchors[port] = _call(page, "outAnchor", "a", port)
        assert anchors[port] == pytest.approx(centre, abs=0.5)
        # translateX(50%) puts the dot's centre on the right edge, not inside it.
        assert anchors[port]["x"] == pytest.approx(box["x"] + box["width"], abs=0.5)
    assert anchors["ok"]["y"] < anchors["fail"]["y"]
    assert page_errors == []


def test_out_anchor_without_that_port_is_the_right_edge_midpoint(
    page, page_errors, session
):
    _seed(page, IDENTITY)
    _serve(page, _ports_stage(session))
    for node_id, args in [("a", ["nope"]), ("a", []), ("b", ["ok"])]:
        box = _call(page, "box", node_id)
        edge = {"x": box["x"] + box["width"], "y": box["y"] + box["height"] / 2}
        assert _call(page, "outAnchor", node_id, *args) == pytest.approx(edge)
    assert page_errors == []


def test_unknown_node_id_gives_null(page, page_errors, session):
    _seed(page, IDENTITY)
    other = _stage(session, [_node("only-there", 10, 10, stage_id="h", title="H")], "h")
    _serve(page, _ports_stage(session) + other)
    for node_id in ("zzz", "only-there", ""):
        assert _call(page, "box", node_id) is None
        assert _call(page, "inAnchor", node_id) is None
        assert _call(page, "outAnchor", node_id, "ok") is None
    assert _call(page, "box", "only-there", stage_id="h") is not None
    assert page_errors == []


def test_ids_with_css_special_characters_resolve(page, page_errors, session):
    _seed(page, IDENTITY)
    # PJXGraphNode refuses '"' in attributes, but other markup may carry it escaped.
    odd = 'a "b" ]c'
    html = (
        render(_node("odd", 60, 70, title="Odd", out_ports=("p",)), session)
        .replace('data-node-id="odd"', 'data-node-id="a &quot;b&quot; ]c"')
        .replace('data-port="p"', 'data-port="x&quot;]"')
    )
    layer = PJXGraphNodes(id="g-nodes", nodes_html=Markup(html))
    _serve(page, render(PJXGraph(id="g", nodes=layer, storage_key="flow"), session))
    box = _call(page, "box", odd)
    assert (box["x"], box["y"]) == pytest.approx((60, 70), abs=0.5)
    assert _call(page, "inAnchor", odd) is not None
    assert _call(page, "outAnchor", odd, 'x"]')["x"] == pytest.approx(
        box["x"] + box["width"], abs=0.5
    )
    assert page_errors == []


def test_a_nested_stage_keeps_its_own_nodes(page, page_errors, session):
    _seed(page, IDENTITY)
    inner = _stage(session, [_node("deep", 10, 10, "in", title="Deep")], "in")
    outer = _node("a", 40, 40, title="A", icon=Markup(inner))
    _serve(page, _stage(session, [outer], storage_key="flow"))
    assert _call(page, "box", "deep") is None
    assert _call(page, "box", "deep", stage_id="in") is not None
    assert page_errors == []


# Fit

NOTCH = 2**0.2
PAD = 48
# A fixed canvas size, so what a fit should give is computable.
FRAME = "width:800px;--pjx-graph-min-height:400px"

INNER = """id => {
    const canvas = document.querySelector('#' + id + ' > .pjx-graph__canvas');
    return {width: canvas.clientWidth, height: canvas.clientHeight};
}"""


def _identity(view: dict[str, float]) -> bool:
    return view == pytest.approx({"x": 0, "y": 0, "k": 1}, abs=1e-6)


def _framed(html: str) -> str:
    return f'<div style="{FRAME}">{html}</div>'


def _assert_framed(
    page: Page, stage_id: str = "g", skip: frozenset[str] = frozenset()
) -> None:
    """Every node inside the canvas inset by PAD, and their union centred in it."""
    inner = page.evaluate(INNER, stage_id)
    rects = [r for r in _rects(page, stage_id) if r["id"] not in skip]
    for r in rects:
        assert r["x"] >= PAD - 1
        assert r["y"] >= PAD - 1
        assert r["right"] <= inner["width"] - PAD + 1
        assert r["bottom"] <= inner["height"] - PAD + 1
    left = min(r["x"] for r in rects)
    right = max(r["right"] for r in rects)
    top = min(r["y"] for r in rects)
    bottom = max(r["bottom"] for r in rects)
    assert (left + right) / 2 == pytest.approx(inner["width"] / 2, abs=1)
    assert (top + bottom) / 2 == pytest.approx(inner["height"] / 2, abs=1)


def _corner(page: Page, stage_id: str = "g") -> tuple[int, int]:
    """A point just inside the canvas's top-left corner, which a fit leaves empty."""
    box = page.locator(f"#{stage_id} > .pjx-graph__canvas").bounding_box()
    assert box is not None
    return round(box["x"] + 12), round(box["y"] + 12)


def _drag(page: Page, start: tuple[int, int]) -> None:
    x, y = start
    page.mouse.move(x, y)
    page.mouse.down()
    page.mouse.move(x + 60, y + 40, steps=4)
    page.mouse.up()


# Wide enough that no fit can use the default 0.2..2 range's clamp.
SPREAD = [("a", 0, 0), ("b", 900, 300), ("c", 1800, 600)]


def _spread(session, **graph) -> str:
    return _framed(
        _stage(session, [_node(n, x, y, title=n) for n, x, y in SPREAD], **graph)
    )


def test_initial_fit_frames_every_node(page, page_errors, session):
    _serve(page, _spread(session))
    k = _view(page)["k"]
    assert 0.2 <= k <= 2
    _assert_framed(page)
    assert page_errors == []


def test_initial_fit_clamps_to_the_scale_range(page, page_errors, session):
    small = _framed(_stage(session, [_node("a", 10, 10, title="A")], scale_max=1.5))
    _serve(page, small)
    assert _view(page)["k"] == pytest.approx(1.5, abs=1e-3)
    wide = [_node("a", 0, 0, title="A"), _node("b", 10000, 0, title="B")]
    page.unroute(URL)
    _serve(page, _framed(_stage(session, wide, scale_min=0.5)))
    assert _view(page)["k"] == pytest.approx(0.5, abs=1e-3)
    assert page_errors == []


def test_a_persisted_view_suppresses_the_initial_fit(page, page_errors, session):
    seeded = {"x": 30, "y": 20, "k": 1.25}
    _seed(page, {"view": seeded})
    _serve(page, _spread(session, storage_key="flow"))
    assert _view(page) == pytest.approx(seeded, abs=0.01)
    # Well past the ten frames a pending fit could take.
    page.wait_for_timeout(300)
    assert _view(page) == pytest.approx(seeded, abs=0.01)
    assert page_errors == []


@pytest.mark.parametrize(
    "record",
    [{"view": {"x": "a", "k": 0}}, {"positions": {"a": {"x": 5, "y": 6}}}],
    ids=["unusable-view", "no-view"],
)
def test_an_unusable_persisted_view_still_fits(page, page_errors, session, record):
    _seed(page, record)
    _serve(page, _spread(session, storage_key="flow"))
    assert not _identity(_view(page))
    _assert_framed(page)
    assert page_errors == []


def test_the_initial_fit_writes_nothing(page, page_errors, session):
    _serve(page, _spread(session, storage_key="flow"))
    assert not _identity(_view(page))
    assert page.evaluate("() => localStorage.length") == 0
    assert page_errors == []


def test_the_initial_fit_waits_for_the_canvas_to_settle(page, page_errors, session):
    html = _spread(session).replace(
        'class="pjx-graph__canvas"',
        'class="pjx-graph__canvas" style="height:0;min-height:0"',
    )
    grow = (
        "<script>document.addEventListener('DOMContentLoaded', () =>"
        " requestAnimationFrame(() => requestAnimationFrame(() => {"
        " document.querySelector('#g > .pjx-graph__canvas').style.height = '400px';"
        " })));</script>"
    )
    _serve(page, grow + html)
    assert page.evaluate(INNER, "g")["height"] == 400
    _assert_framed(page)
    assert page_errors == []


def test_a_stage_that_never_lays_out_fits_without_error(
    page, page_errors, console_errors, session
):
    _serve(page, f'<div style="display:none">{_spread(session)}</div>')
    assert page.evaluate(
        "() => document.getElementById('g').hasAttribute('data-pjx-graph-ready')"
    )
    assert console_errors == []
    assert page_errors == []


def test_a_stage_with_no_nodes_stays_at_identity_and_is_ready(
    page, page_errors, session
):
    _serve(page, _framed(_stage(session, [])))
    assert _identity(_view(page))
    assert (
        page.evaluate(
            "() => document.getElementById('g').getAttribute('data-pjx-graph-ready')"
        )
        == ""
    )
    assert page_errors == []


def _record(page: Page) -> dict:
    raw = page.evaluate("key => localStorage.getItem(key)", RECORD)
    assert raw is not None
    return json.loads(raw)


def test_fit_after_a_pan_reframes_and_saves(page, page_errors, session):
    positions = {"a": {"x": 5, "y": 6}}
    _seed(page, {"positions": positions})
    _serve(page, _spread(session, storage_key="flow"))
    fitted = _view(page)
    _drag(page, _corner(page))
    page.wait_for_function(
        "key => 'view' in JSON.parse(localStorage.getItem(key))", arg=RECORD
    )
    assert _view(page) == pytest.approx(
        {"x": fitted["x"] + 60, "y": fitted["y"] + 40, "k": fitted["k"]}, abs=0.01
    )
    page.evaluate("() => pjx.graph.get(document.getElementById('g')).fit()")
    assert _view(page) == pytest.approx(fitted, abs=0.01)
    record = _record(page)
    assert record["positions"] == positions
    assert record["view"] == pytest.approx(fitted, abs=0.01)
    assert page_errors == []


def test_wheel_after_the_fit_continues_from_the_fitted_view(page, page_errors, session):
    _serve(page, _spread(session))
    k = _view(page)["k"]
    page.mouse.move(*_corner(page))
    page.mouse.wheel(0, -100)
    page.wait_for_function(
        f"([id, k]) => Math.abs(({VIEW})(id).k - k) < 1e-3", arg=["g", k * NOTCH]
    )
    assert page_errors == []


def test_mounting_twice_fits_once(page, page_errors, session):
    _serve(page, _spread(session))
    fitted = _view(page)
    page.evaluate("() => pjx.graph.mount(document.getElementById('g'))")
    _drag(page, _corner(page))
    page.wait_for_timeout(300)
    assert _view(page) == pytest.approx(
        {"x": fitted["x"] + 60, "y": fitted["y"] + 40, "k": fitted["k"]}, abs=0.01
    )
    assert page_errors == []


def test_a_stage_removed_before_the_fit_lands_does_not_throw(
    page, page_errors, console_errors, session
):
    _serve(page, "")
    page.evaluate(
        """html => {
            document.body.insertAdjacentHTML('beforeend', html);
            const el = document.getElementById('g');
            pjx.graph.mount(el);
            el.remove();
            window.removed = el;
        }""",
        _spread(session),
    )
    page.wait_for_function("() => window.removed.hasAttribute('data-pjx-graph-ready')")
    assert console_errors == []
    assert page_errors == []


def test_fit_skips_a_hidden_node(page, page_errors, session):
    hidden = render(_node("h", 5000, 5000, title="H"), session).replace(
        'style="', 'style="display:none;'
    )
    visible = [render(_node(n, x, y, title=n), session) for n, x, y in SPREAD]
    layer = PJXGraphNodes(id="g-nodes", nodes_html=Markup("".join(visible) + hidden))
    _serve(page, _framed(render(PJXGraph(id="g", nodes=layer), session)))
    _assert_framed(page, skip=frozenset({"h"}))
    assert page_errors == []
